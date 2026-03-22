"""历史周线同步服务（stk_weekly_monthly 全市场批量，避免逐标的请求）。"""

from __future__ import annotations

import logging
import time
from datetime import date

from sqlalchemy.orm import Session

from app.models import StockWeeklyBar
from app.services.stock_sync_utils import enumerate_week_batch_trade_dates, safe_date
from app.services.tushare_client import get_stk_weekly_monthly_by_trade_date, normalize_bar

logger = logging.getLogger(__name__)

# 回灌时两次批量请求之间的额外间隔，配合 tushare_client.RATE_PAUSE_SEC 降低触发限流概率
STK_WM_BACKFILL_EXTRA_PAUSE_SEC = 0.35


def _upsert_weekly_rows(db: Session, rows: list[dict], batch_id: str) -> int:
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
            db.query(StockWeeklyBar)
            .filter(StockWeeklyBar.stock_code == ts_code, StockWeeklyBar.trade_week_end == trade_end)
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
            db.add(StockWeeklyBar(stock_code=ts_code, trade_week_end=trade_end, **payload))
        written += 1
    return written


def sync_weekly_bars_batch(db: Session, *, trade_date: date, batch_id: str) -> dict[str, int]:
    """按交易日期全市场拉取一周 K（stk_weekly_monthly，freq=week）。"""
    rows = get_stk_weekly_monthly_by_trade_date(trade_date, "week")
    written = _upsert_weekly_rows(db, rows, batch_id)
    db.commit()
    logger.info(
        "周线批量同步完成 trade_date=%s Tushare返回行数=%s 写入行数=%s",
        trade_date,
        len(rows),
        written,
    )
    if written == 0:
        logger.warning(
            "周线写入 0 行：请核对 stk_weekly_monthly 积分权限、trade_date 是否为接口要求的"
            "「周/月 K 线对应交易日」；若仅用默认 sync_stock（仅 basic+daily）则从未跑过周线模块。"
        )
    return {"weekly_rows": written}


def sync_weekly_bars_backfill_batch(
    db: Session, *, start_date: date, end_date: date, batch_id: str
) -> dict[str, int]:
    """按自然周枚举每周最后一个开市日，逐日批量拉取，避免逐标的循环。"""
    batch_dates = enumerate_week_batch_trade_dates(start_date, end_date)
    total = 0
    for td in batch_dates:
        rows = get_stk_weekly_monthly_by_trade_date(td, "week")
        total += _upsert_weekly_rows(db, rows, batch_id)
        db.commit()
        time.sleep(STK_WM_BACKFILL_EXTRA_PAUSE_SEC)
    logger.info(
        "周线回灌完成 start=%s end=%s batch_dates=%s total_rows=%s",
        start_date,
        end_date,
        len(batch_dates),
        total,
    )
    return {"weekly_rows": total}


def sync_weekly_bars(
    db: Session,
    *,
    codes: list[str],
    end_date: date,
    batch_id: str,
    mode: str,
    start_date: date | None = None,
) -> dict[str, int]:
    """
    编排器入口：全市场批量接口，codes 参数保留仅为兼容旧签名，不再使用。
    incremental：对 end_date（通常为最近交易日）拉一次全市场周线。
    backfill：在 [start_date, end_date] 内按周界日期批量拉取。
    """
    _ = codes
    if mode == "backfill":
        if start_date is None or end_date is None:
            raise ValueError("backfill 模式下 weekly 模块必须提供 start_date 和 end_date")
        return sync_weekly_bars_backfill_batch(db, start_date=start_date, end_date=end_date, batch_id=batch_id)
    return sync_weekly_bars_batch(db, trade_date=end_date, batch_id=batch_id)
