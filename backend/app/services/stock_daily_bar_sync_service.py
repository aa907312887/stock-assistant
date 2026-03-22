"""历史日线同步服务：合并 daily 与 daily_basic 写入 stock_daily_bar。"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import StockDailyBar
from app.services.stock_sync_utils import safe_decimal
from app.services.tushare_client import get_daily_basic_by_trade_date, get_daily_by_trade_date, normalize_bar

logger = logging.getLogger(__name__)


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
    daily_map = get_daily_by_trade_date(trade_date)
    basic_map = get_daily_basic_by_trade_date(trade_date)
    logger.info(
        "Tushare 全市场日线 trade_date=%s：daily 行数=%s daily_basic 行数=%s 待匹配标的数=%s",
        trade_date,
        len(daily_map),
        len(basic_map),
        len(codes),
    )
    written = 0

    for code in codes:
        raw_bar = daily_map.get(code)
        raw_basic = basic_map.get(code, {})
        if not raw_bar and not raw_basic:
            continue
        bar = normalize_bar(raw_bar) or {}
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
    db.commit()
    logger.info("历史日线同步完成 trade_date=%s written=%s", trade_date, written)
    if written == 0 and codes:
        sample_code = codes[:3]
        sample_dm = list(daily_map.keys())[:3]
        logger.warning(
            "日线写入 0 行：请核对 (1) Tushare daily 是否对该日有数据（非交易日/未来日会为空）"
            "(2) stock_basic.code 是否为 ts_code（如 000001.SZ），与 Tushare 返回键一致；"
            "示例 stock_basic.code=%s 示例 Tushare 键=%s",
            sample_code,
            sample_dm,
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
