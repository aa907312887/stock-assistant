"""历史月线同步服务（stk_weekly_monthly 全市场批量，避免逐标的请求）。"""

from __future__ import annotations

import logging
import time
from datetime import date

from sqlalchemy.orm import Session

from app.models import StockMonthlyBar
from app.services.stock_sync_utils import enumerate_month_batch_trade_dates, safe_date
from app.services.tushare_client import get_stk_weekly_monthly_by_trade_date, normalize_bar

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


def sync_monthly_bars_batch(db: Session, *, trade_date: date, batch_id: str) -> dict[str, int]:
    """
    按交易日期全市场拉月线（stk_weekly_monthly，freq=month）。
    每个交易日均调用，以支持当月「未完成」月线（与规格 FR-007 补充一致）。
    """
    rows = get_stk_weekly_monthly_by_trade_date(trade_date, "month")
    written = _upsert_monthly_rows(db, rows, batch_id)
    db.commit()
    logger.info("月线批量同步完成 trade_date=%s written=%s", trade_date, written)
    return {"monthly_rows": written}


def sync_monthly_bars_backfill_batch(
    db: Session, *, start_date: date, end_date: date, batch_id: str
) -> dict[str, int]:
    """按自然月枚举每月最后一个开市日，逐日批量拉取。"""
    batch_dates = enumerate_month_batch_trade_dates(start_date, end_date)
    total = 0
    for td in batch_dates:
        rows = get_stk_weekly_monthly_by_trade_date(td, "month")
        total += _upsert_monthly_rows(db, rows, batch_id)
        db.commit()
        time.sleep(STK_WM_BACKFILL_EXTRA_PAUSE_SEC)
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
