"""历史月线同步服务（stk_weekly_monthly 全市场批量，避免逐标的请求）。"""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from datetime import date

from sqlalchemy.orm import Session

from app.models import StockDailyBar, StockMonthlyBar
from app.services.stock_sync_utils import (
    enumerate_month_batch_trade_dates,
    get_month_last_open_date,
    safe_date,
)
from app.services.tushare_client import (
    get_stk_weekly_monthly_by_trade_date,
    get_stk_weekly_monthly_latest_by_anchor,
    normalize_bar,
)

logger = logging.getLogger(__name__)

STK_WM_BACKFILL_EXTRA_PAUSE_SEC = 0.35


def _upsert_monthly_rows(db: Session, rows: list[dict], batch_id: str) -> int:
    written = 0
    for row in rows:
        ts_code = (row.get("ts_code") or row.get("TS_CODE") or "").strip()
        if not ts_code:
            continue
        trade_end = safe_date(row.get("trade_date")) or safe_date(row.get("end_date"))
        if trade_end is None:
            continue
        bar = normalize_bar(row) or {}
        existing = (
            db.query(StockMonthlyBar)
            .filter(StockMonthlyBar.stock_code == ts_code, StockMonthlyBar.trade_month_end == trade_end)
            .first()
        )
        payload = {
            "open": bar.get("o"),
            "high": bar.get("h"),
            "low": bar.get("l"),
            "close": bar.get("c"),
            "change_amount": bar.get("change"),
            "pct_change": bar.get("pct_chg"),
            "volume": bar.get("v"),
            "amount": bar.get("a"),
            "sync_batch_id": batch_id,
            "data_source": "tushare",
        }
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
        else:
            db.add(StockMonthlyBar(stock_code=ts_code, trade_month_end=trade_end, **payload))
        written += 1
    return written


def _safe_pct(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator in (None, Decimal("0")):
        return None
    try:
        return (numerator / denominator) * Decimal("100")
    except Exception:
        return None


def _supplement_monthly_from_daily(db: Session, *, anchor_date: date, batch_id: str) -> int:
    """
    以日线补充“当月未完结月K”：
    - trade_month_end 固定写为当月最后开市日
    - 以 [月初..anchor] 的日线聚合 open/high/low/close/volume/amount
    """
    month_end = get_month_last_open_date(anchor_date)
    if month_end is None:
        return 0
    month_start = date(anchor_date.year, anchor_date.month, 1)
    rows = (
        db.query(StockDailyBar)
        .filter(
            StockDailyBar.trade_date >= month_start,
            StockDailyBar.trade_date <= anchor_date,
        )
        .order_by(StockDailyBar.stock_code.asc(), StockDailyBar.trade_date.asc())
        .all()
    )
    grouped: dict[str, list[StockDailyBar]] = {}
    for r in rows:
        grouped.setdefault(r.stock_code, []).append(r)
    written = 0
    for code, ds in grouped.items():
        if not ds:
            continue
        first = ds[0]
        last = ds[-1]
        high_vals = [x.high for x in ds if x.high is not None]
        low_vals = [x.low for x in ds if x.low is not None]
        vol_vals = [x.volume for x in ds if x.volume is not None]
        amt_vals = [x.amount for x in ds if x.amount is not None]
        open_v = first.open
        close_v = last.close
        prev_close = first.prev_close
        change_amt = (close_v - prev_close) if close_v is not None and prev_close is not None else None
        pct_chg = _safe_pct(change_amt, prev_close)
        existing = (
            db.query(StockMonthlyBar)
            .filter(StockMonthlyBar.stock_code == code, StockMonthlyBar.trade_month_end == month_end)
            .first()
        )
        payload = {
            "open": open_v,
            "high": max(high_vals) if high_vals else None,
            "low": min(low_vals) if low_vals else None,
            "close": close_v,
            "change_amount": change_amt,
            "pct_change": pct_chg,
            "volume": sum(vol_vals, Decimal("0")) if vol_vals else None,
            "amount": sum(amt_vals, Decimal("0")) if amt_vals else None,
            "sync_batch_id": batch_id,
            "data_source": "tushare",
        }
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
        else:
            db.add(StockMonthlyBar(stock_code=code, trade_month_end=month_end, **payload))
        written += 1
    db.commit()
    logger.info(
        "月线日线补充完成 anchor=%s month_end=%s 写入行数=%s",
        anchor_date,
        month_end,
        written,
    )
    return written


def sync_monthly_bars_batch(db: Session, *, trade_date: date, batch_id: str) -> dict[str, int]:
    """
    按交易日期全市场拉月线（stk_weekly_monthly，freq=month）。
    每个交易日均调用，以支持当月「未完成」月线（与规格 FR-007 补充一致）。
    """
    rows = get_stk_weekly_monthly_latest_by_anchor(trade_date, "month")
    written = _upsert_monthly_rows(db, rows, batch_id)
    supplemented = _supplement_monthly_from_daily(db, anchor_date=trade_date, batch_id=batch_id)
    db.commit()
    logger.info(
        "月线批量同步完成 anchor_date=%s rows=%s written=%s 日线补充=%s",
        trade_date,
        len(rows),
        written,
        supplemented,
    )
    rows_for_report = supplemented if supplemented > 0 else written
    return {"monthly_rows": rows_for_report}


def sync_monthly_bars_backfill_batch(
    db: Session, *, start_date: date, end_date: date, batch_id: str
) -> dict[str, int]:
    """按自然月枚举每月最后一个开市日，逐日批量拉取。"""
    logger.info(
        "月线回灌：正在枚举各月最后开市日（每月一次 trade_cal，耗时可到数分钟）start=%s end=%s",
        start_date,
        end_date,
    )
    batch_dates = enumerate_month_batch_trade_dates(start_date, end_date)
    n = len(batch_dates)
    logger.info("月线回灌：共 %s 个月末批次，开始逐批请求 Tushare stk_weekly_monthly(freq=month)", n)
    total = 0
    for i, td in enumerate(batch_dates, start=1):
        rows = get_stk_weekly_monthly_by_trade_date(td, "month")
        total += _upsert_monthly_rows(db, rows, batch_id)
        db.commit()
        time.sleep(STK_WM_BACKFILL_EXTRA_PAUSE_SEC)
        if i == 1 or i == n or i % 5 == 0:
            msg = (
                f"[月线回灌] {i}/{n} trade_date={td} "
                f"本批行数={len(rows)} 累计写入={total} batch_id={batch_id}"
            )
            logger.info(msg)
            print(msg, flush=True)
    logger.info(
        "月线回灌完成 start=%s end=%s batch_dates=%s total_rows=%s",
        start_date,
        end_date,
        len(batch_dates),
        total,
    )
    return {"monthly_rows": total}


def sync_monthly_bars(
    db: Session,
    *,
    codes: list[str],
    end_date: date,
    batch_id: str,
    mode: str,
    start_date: date | None = None,
) -> dict[str, int]:
    """编排器入口：codes 保留兼容，全市场批量。"""
    _ = codes
    if mode == "backfill":
        if start_date is None or end_date is None:
            raise ValueError("backfill 模式下 monthly 模块必须提供 start_date 和 end_date")
        return sync_monthly_bars_backfill_batch(db, start_date=start_date, end_date=end_date, batch_id=batch_id)
    return sync_monthly_bars_batch(db, trade_date=end_date, batch_id=batch_id)
