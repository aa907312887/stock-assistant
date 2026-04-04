"""历史日线同步服务：`pro_bar` 前复权与 `daily_basic` 合并写入 stock_daily_bar。"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Iterator

from sqlalchemy.orm import Session

from app.models import StockDailyBar
from app.services.stock_hist_extrema_service import apply_cum_extrema_after_daily_upsert
from app.services.stock_pe_percentile_service import apply_pe_percentile_after_daily_upsert
from app.services.stock_sync_utils import safe_decimal
from app.services.tushare_client import (
    TushareClientError,
    fetch_pro_bar_qfq_daily,
    get_daily_basic_by_trade_date,
    get_open_trade_dates,
    get_pro_bar_qfq_for_trade_date,
    normalize_bar,
)

logger = logging.getLogger(__name__)

# 全市场逐标的请求 pro_bar，每 N 只打一次进度，避免刷屏
DAILY_QFQ_PROGRESS_EVERY = 200

# backfill：每段约一个自然年（365 个自然日），每标的该段一次 pro_bar 拉满该年窗口内全部交易日 K 线
BACKFILL_CHUNK_CALENDAR_DAYS = 365
# Tushare pro_bar 单次返回行数上限（一年内交易日通常 <300，留足余量）
BACKFILL_PRO_BAR_LIMIT = 8000


def _cap_to_yuan(value: Any) -> Decimal | None:
    dec = safe_decimal(value)
    if dec is None:
        return None
    return dec * Decimal("10000")


def _iter_calendar_chunks(
    start: date, end: date, *, chunk_days: int = BACKFILL_CHUNK_CALENDAR_DAYS
) -> Iterator[tuple[date, date]]:
    """按自然日切分 [start, end]，每段最多 chunk_days 天（含首尾）。"""
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=chunk_days - 1), end)
        yield (cur, chunk_end)
        cur = chunk_end + timedelta(days=1)


def _row_to_trade_date(row: dict[str, Any]) -> date | None:
    td = row.get("trade_date")
    if td is None:
        return None
    if hasattr(td, "year") and hasattr(td, "month") and hasattr(td, "day"):
        try:
            return date(td.year, td.month, td.day)  # type: ignore[arg-type]
        except Exception:
            pass
    s = str(td).replace("-", "").strip()
    if len(s) >= 8:
        try:
            return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            return None
    return None


def _upsert_daily_bar(
    db: Session,
    *,
    code: str,
    trade_date: date,
    raw_bar: dict[str, Any] | None,
    raw_basic: dict[str, Any],
    batch_id: str,
) -> bool:
    """写入一行日线；若 raw_bar 与 raw_basic 皆空则跳过。返回是否产生一行有效写入。"""
    if not raw_bar and not raw_basic:
        return False
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
    return True


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
        if _upsert_daily_bar(
            db,
            code=code,
            trade_date=trade_date,
            raw_bar=raw_bar,
            raw_basic=raw_basic,
            batch_id=batch_id,
        ):
            written += 1
            db.flush()
            apply_cum_extrema_after_daily_upsert(db, code, trade_date)
            apply_pe_percentile_after_daily_upsert(db, code, trade_date)
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


def sync_daily_bars_backfill_range(
    db: Session,
    *,
    codes: list[str],
    start_date: date,
    end_date: date,
    batch_id: str,
    chunk_calendar_days: int = BACKFILL_CHUNK_CALENDAR_DAYS,
) -> dict[str, int]:
    """
    backfill 专用：按自然日切分（默认每段约一年 365 日），每段内先拉取该段全部交易日的 `daily_basic`，
    再对每只股票**一次** `pro_bar` 拉取该年窗口内全部日线；每只股票处理完即 `commit` 落库。
    """
    n = len(codes)
    total_written = 0
    chunk_no = 0
    total_windows = sum(1 for _ in _iter_calendar_chunks(start_date, end_date, chunk_days=chunk_calendar_days))

    for cs, ce in _iter_calendar_chunks(start_date, end_date, chunk_days=chunk_calendar_days):
        chunk_no += 1
        natural_span = (ce - cs).days + 1
        t_prefetch = time.perf_counter()
        tds = get_open_trade_dates(start=cs.strftime("%Y%m%d"), end=ce.strftime("%Y%m%d"))
        basic_by_td: dict[date, dict[str, dict[str, Any]]] = {}
        for td in tds:
            basic_by_td[td] = get_daily_basic_by_trade_date(td)
        prefetch_sec = time.perf_counter() - t_prefetch

        logger.info(
            "日线回灌 | 年窗口 [%s/%s] | 自然区间=%s..%s（跨度 %s 天）| 段内交易日=%s | 标的数=%s | "
            "预拉 daily_basic 耗时=%.2fs | batch_id=%s",
            chunk_no,
            total_windows,
            cs,
            ce,
            natural_span,
            len(tds),
            n,
            prefetch_sec,
            batch_id,
        )

        for idx, code in enumerate(codes, start=1):
            t_one = time.perf_counter()
            try:
                rows = fetch_pro_bar_qfq_daily(
                    code,
                    cs,
                    ce,
                    limit=BACKFILL_PRO_BAR_LIMIT,
                )
            except TushareClientError as e:
                logger.warning(
                    "日线回灌 | 年窗口 [%s/%s] | [%s/%s] ts_code=%s | 区间=%s..%s | pro_bar 失败 err=%s",
                    chunk_no,
                    total_windows,
                    idx,
                    n,
                    code,
                    cs,
                    ce,
                    e,
                )
                continue

            stock_written = 0
            skipped_out_of_range = 0
            parsed: list[tuple[date, dict[str, Any]]] = []
            for r in rows:
                td = _row_to_trade_date(r)
                if td is None or td < start_date or td > end_date:
                    skipped_out_of_range += 1
                    continue
                parsed.append((td, r))
            parsed.sort(key=lambda x: x[0])

            for td, r in parsed:
                if td not in basic_by_td:
                    basic_by_td[td] = get_daily_basic_by_trade_date(td)
                raw_basic = basic_by_td[td].get(code, {})
                if _upsert_daily_bar(
                    db,
                    code=code,
                    trade_date=td,
                    raw_bar=r,
                    raw_basic=raw_basic,
                    batch_id=batch_id,
                ):
                    stock_written += 1
                    total_written += 1
                    db.flush()
                    apply_cum_extrema_after_daily_upsert(db, code, td)
                    apply_pe_percentile_after_daily_upsert(db, code, td)

            db.commit()
            db.expire_all()
            elapsed = time.perf_counter() - t_one

            logger.info(
                "日线回灌 | 年窗口 [%s/%s] | [%s/%s] ts_code=%s | 区间=%s..%s | pro_bar 行数=%s | 写入行数=%s | "
                "丢弃（日期越界）=%s | 本段耗时=%.2fs | 已 commit | 累计写入=%s | batch_id=%s",
                chunk_no,
                total_windows,
                idx,
                n,
                code,
                cs,
                ce,
                len(rows),
                stock_written,
                skipped_out_of_range,
                elapsed,
                total_written,
                batch_id,
            )

        logger.info(
            "日线回灌 | 年窗口 [%s/%s] 结束 | 区间=%s..%s | 截至本窗口累计写入=%s | batch_id=%s",
            chunk_no,
            total_windows,
            cs,
            ce,
            total_written,
            batch_id,
        )

    if total_written == 0 and codes:
        logger.warning(
            "日线回灌 0 行：请核对 stock_basic.code 是否为 ts_code、区间是否有交易日、Tushare 是否返回空数据",
        )
    return {"daily_rows": total_written}


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
