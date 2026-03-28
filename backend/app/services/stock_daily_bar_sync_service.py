"""历史日线同步服务：`pro_bar` 前复权与 `daily_basic` 合并写入 stock_daily_bar。"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import StockDailyBar
from app.services.stock_sync_utils import safe_decimal
from app.services.tushare_client import (
    TushareClientError,
    get_daily_basic_by_trade_date,
    get_pro_bar_qfq_for_trade_date,
    normalize_bar,
)

logger = logging.getLogger(__name__)

# 全市场逐标的请求 pro_bar，每 N 只打一次进度，避免刷屏
DAILY_QFQ_PROGRESS_EVERY = 200


def _cap_to_yuan(value: Any) -> Decimal | None:
    dec = safe_decimal(value)
    if dec is None:
        return None
    return dec * Decimal("10000")


def sync_daily_bars(
    db: Session,
    *,
    codes: list[str],
    trade_date: date,
    batch_id: str,
) -> dict[str, int]:
    """
    按标的调用 Tushare `pro_bar`（`adj='qfq'`）写入**前复权** OHLCV；
    换手率、市值、估值等仍来自当日全市场 `daily_basic`。
    """
    basic_map = get_daily_basic_by_trade_date(trade_date)
    n = len(codes)
    logger.info(
        "Tushare 日线前复权 trade_date=%s：daily_basic 行数=%s 待请求标的数=%s（逐只 pro_bar qfq）",
        trade_date,
        len(basic_map),
        n,
    )
    written = 0

    for idx, code in enumerate(codes, start=1):
        try:
            raw_bar = get_pro_bar_qfq_for_trade_date(code, trade_date)
        except TushareClientError as e:
            logger.warning(
                "标的 pro_bar(qfq) 失败 ts_code=%s trade_date=%s err=%s",
                code,
                trade_date,
                e,
            )
            continue
        raw_basic = basic_map.get(code, {})
        if not raw_bar and not raw_basic:
            continue
        bar = normalize_bar(raw_bar) if raw_bar else {}
        existing = (
            db.query(StockDailyBar)
            .filter(StockDailyBar.stock_code == code, StockDailyBar.trade_date == trade_date)
            .first()
        )
        payload = {
            "open": bar.get("o"),
            "high": bar.get("h"),
            "low": bar.get("l"),
            "close": bar.get("c"),
            "prev_close": bar.get("pc"),
            "change_amount": bar.get("change"),
            "pct_change": bar.get("pct_chg"),
            "volume": bar.get("v"),
            "amount": bar.get("a"),
            "amplitude": _calc_amplitude(bar),
            "turnover_rate": safe_decimal(raw_basic.get("turnover_rate")),
            "volume_ratio": safe_decimal(raw_basic.get("volume_ratio")),
            "total_market_cap": _cap_to_yuan(raw_basic.get("total_mv")),
            "float_market_cap": _cap_to_yuan(raw_basic.get("circ_mv")),
            "pe": safe_decimal(raw_basic.get("pe")),
            "pe_ttm": safe_decimal(raw_basic.get("pe_ttm")),
            "pb": safe_decimal(raw_basic.get("pb")),
            "ps": safe_decimal(raw_basic.get("ps")),
            "dv_ratio": safe_decimal(raw_basic.get("dv_ratio")),
            "dv_ttm": safe_decimal(raw_basic.get("dv_ttm")),
            "sync_batch_id": batch_id,
            "data_source": "tushare",
        }
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
        else:
            db.add(
                StockDailyBar(
                    stock_code=code,
                    trade_date=trade_date,
                    **payload,
                )
            )
        written += 1
        if idx == 1 or idx == n or idx % DAILY_QFQ_PROGRESS_EVERY == 0:
            logger.info(
                "日线前复权进度 %s/%s trade_date=%s 已写入=%s",
                idx,
                n,
                trade_date,
                written,
            )

    db.commit()
    logger.info("历史日线同步完成 trade_date=%s written=%s", trade_date, written)
    if written == 0 and codes:
        sample_code = codes[:3]
        logger.warning(
            "日线写入 0 行：请核对 (1) 是否非交易日/无 pro_bar 数据 (2) stock_basic.code 是否为 ts_code（如 000001.SZ）；"
            "示例 code=%s",
            sample_code,
        )
    return {"daily_rows": written}


def _calc_amplitude(bar: dict[str, Any]) -> Decimal | None:
    high = bar.get("h")
    low = bar.get("l")
    prev_close = bar.get("pc")
    if high is None or low is None or prev_close in (None, Decimal("0")):
        return None
    try:
        return ((high - low) / prev_close) * Decimal("100")
    except Exception:
        return None
