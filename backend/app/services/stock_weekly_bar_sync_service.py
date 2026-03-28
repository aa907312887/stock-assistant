"""历史周线同步服务（stk_weekly_monthly 全市场批量，避免逐标的请求）。"""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from datetime import date

from sqlalchemy.orm import Session

from app.models import StockDailyBar, StockWeeklyBar
from app.services.stock_sync_utils import (
    enumerate_week_batch_trade_dates,
    get_week_last_open_date,
    safe_date,
)
from app.services.tushare_client import (
    get_stk_weekly_monthly_by_trade_date,
    get_stk_weekly_monthly_latest_by_anchor,
    normalize_bar,
)

logger = logging.getLogger(__name__)

# 回灌时两次批量请求之间的额外间隔，配合 tushare_client._rate_pause 降低触发限流概率
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


def _safe_pct(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator in (None, Decimal("0")):
        return None
    try:
        return (numerator / denominator) * Decimal("100")
    except Exception:
        return None


def _supplement_weekly_from_daily(db: Session, *, anchor_date: date, batch_id: str) -> int:
    """
    以日线补充“当周未完结周K”：
    - trade_week_end 固定写为本周最后开市日（通常周五）
    - 以 [周一..anchor] 的日线聚合 open/high/low/close/volume/amount
    """
    week_end = get_week_last_open_date(anchor_date)
    if week_end is None:
        return 0
    week_start = week_end.fromordinal(week_end.toordinal() - week_end.weekday())
    rows = (
        db.query(StockDailyBar)
        .filter(
            StockDailyBar.trade_date >= week_start,
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
            db.query(StockWeeklyBar)
            .filter(StockWeeklyBar.stock_code == code, StockWeeklyBar.trade_week_end == week_end)
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
            db.add(StockWeeklyBar(stock_code=code, trade_week_end=week_end, **payload))
        written += 1
    db.commit()
    logger.info(
        "周线日线补充完成 anchor=%s week_end=%s 写入行数=%s",
        anchor_date,
        week_end,
        written,
    )
    return written


def sync_weekly_bars_batch(db: Session, *, trade_date: date, batch_id: str) -> dict[str, int]:
    """按锚点日期拉取当周最新周 K 快照（stk_weekly_monthly，freq=week）。"""
    rows = get_stk_weekly_monthly_latest_by_anchor(trade_date, "week")
    written = _upsert_weekly_rows(db, rows, batch_id)
    supplemented = _supplement_weekly_from_daily(db, anchor_date=trade_date, batch_id=batch_id)
    db.commit()
    logger.info(
        "周线批量同步完成 anchor_date=%s Tushare返回行数=%s 写入行数=%s 日线补充=%s",
        trade_date,
        len(rows),
        written,
        supplemented,
    )
    # 显示口径按“当前周期快照行数”为主，避免和已完成周期的刷新行数叠加后看起来翻倍。
    rows_for_report = supplemented if supplemented > 0 else written
    if rows_for_report == 0:
        logger.warning(
            "周线写入 0 行：请核对 stk_weekly_monthly 积分权限、交易日历与代码映射。"
        )
    return {"weekly_rows": rows_for_report}


def sync_weekly_bars_backfill_batch(
    db: Session, *, start_date: date, end_date: date, batch_id: str
) -> dict[str, int]:
    """按自然周枚举每周最后一个开市日，逐日批量拉取，避免逐标的循环。"""
    logger.info(
        "周线回灌：正在枚举周界交易日（一次 trade_cal + 本地分组）start=%s end=%s",
        start_date,
        end_date,
    )
    batch_dates = enumerate_week_batch_trade_dates(start_date, end_date)
    n = len(batch_dates)
    logger.info("周线回灌：共 %s 个周界日，开始逐批请求 Tushare stk_weekly_monthly(freq=week)", n)
    total = 0
    for i, td in enumerate(batch_dates, start=1):
        rows = get_stk_weekly_monthly_by_trade_date(td, "week")
        total += _upsert_weekly_rows(db, rows, batch_id)
        db.commit()
        time.sleep(STK_WM_BACKFILL_EXTRA_PAUSE_SEC)
        if i == 1 or i == n or i % 10 == 0:
            msg = (
                f"[周线回灌] {i}/{n} trade_date={td} "
                f"本批行数={len(rows)} 累计写入={total} batch_id={batch_id}"
            )
            logger.info(msg)
            print(msg, flush=True)
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
