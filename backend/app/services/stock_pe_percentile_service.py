"""PE 历史百分位计算服务。

口径：
- 对某股票按 trade_date 升序遍历日线（>= 2019-01-01），维护 running min/max PE：
  pe_percentile = clamp((当日PE - hist_min) / (hist_max - hist_min) * 100, 0, 100)
  其中 hist_min/hist_max 仅使用 **严格早于当日** 的非空 PE 值。
- 历史 PE 不足 2 条 或 hist_max == hist_min → pe_percentile = NULL。
- 当日 PE 为空 → pe_percentile = NULL。
- 不使用未来数据，模拟真实投资场景。

全量 CLI：python scripts/backfill_pe_percentile.py
日常增量：在 stock_daily_bar_sync_service 每次成功 upsert 一行日线后调用
         apply_pe_percentile_after_daily_upsert（与 cum_hist_high/low 同模式）。
"""

from __future__ import annotations

import logging
import time
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.models import StockDailyBar

logger = logging.getLogger(__name__)

PE_HISTORY_START = date(2019, 1, 1)
MIN_PRIOR_PE_COUNT = 2
_COMMIT_EVERY_CODES = 80


def _recompute_pe_percentile_for_code(db: Session, stock_code: str) -> int:
    """全量重算该股所有日线（>= 2019）的 pe_percentile；返回更新行数。"""
    bars = (
        db.query(StockDailyBar)
        .filter(
            StockDailyBar.stock_code == stock_code,
            StockDailyBar.trade_date >= PE_HISTORY_START,
        )
        .order_by(StockDailyBar.trade_date.asc())
        .all()
    )
    if not bars:
        return 0

    running_min: Decimal | None = None
    running_max: Decimal | None = None
    prior_count = 0
    updated = 0

    for b in bars:
        if b.pe is None:
            b.pe_percentile = None
        elif prior_count < MIN_PRIOR_PE_COUNT or running_min is None or running_max is None:
            b.pe_percentile = None
        elif running_max == running_min:
            b.pe_percentile = None
        else:
            pct = float(b.pe - running_min) / float(running_max - running_min) * 100
            pct = max(0.0, min(100.0, pct))
            b.pe_percentile = Decimal(str(round(pct, 2)))

        updated += 1

        # 将当日 PE 加入 running min/max（供后续行使用）
        if b.pe is not None:
            if running_min is None:
                running_min = b.pe
                running_max = b.pe
            else:
                running_min = min(running_min, b.pe)
                running_max = max(running_max, b.pe)
            prior_count += 1

    return updated


def apply_pe_percentile_after_daily_upsert(
    db: Session, stock_code: str, trade_date: date
) -> None:
    """在成功写入/更新某交易日日线后，维护该行 pe_percentile。

    纯尾部追加：用 SQL 聚合取 MIN/MAX/COUNT，O(1) 内存。
    若存在更晚日线（中间改数/补洞）→ 整股重算。
    """
    row = (
        db.query(StockDailyBar)
        .filter(
            StockDailyBar.stock_code == stock_code,
            StockDailyBar.trade_date == trade_date,
        )
        .one_or_none()
    )
    if row is None:
        return

    # 当日 PE 为空则直接置 NULL
    if row.pe is None:
        row.pe_percentile = None
        return

    # 是否存在更晚日线 → 需要整股重算
    later = (
        db.query(StockDailyBar)
        .filter(
            StockDailyBar.stock_code == stock_code,
            StockDailyBar.trade_date > trade_date,
        )
        .limit(1)
        .first()
    )
    if later is not None:
        _recompute_pe_percentile_for_code(db, stock_code)
        return

    # 纯尾部追加：SQL 聚合 MIN/MAX/COUNT
    agg = (
        db.query(
            sa_func.min(StockDailyBar.pe),
            sa_func.max(StockDailyBar.pe),
            sa_func.count(StockDailyBar.pe),
        )
        .filter(
            StockDailyBar.stock_code == stock_code,
            StockDailyBar.trade_date >= PE_HISTORY_START,
            StockDailyBar.trade_date < trade_date,
            StockDailyBar.pe.isnot(None),
        )
        .one()
    )
    hist_min, hist_max, cnt = agg

    if cnt < MIN_PRIOR_PE_COUNT or hist_min is None or hist_max is None:
        row.pe_percentile = None
        return

    if hist_max == hist_min:
        row.pe_percentile = None
        return

    pct = float(row.pe - hist_min) / float(hist_max - hist_min) * 100
    pct = max(0.0, min(100.0, pct))
    row.pe_percentile = Decimal(str(round(pct, 2)))


def run_full_pe_percentile_recompute(db: Session) -> dict[str, Any]:
    """全量：对每个有日线的 stock_code 重算 pe_percentile。"""
    t0 = time.perf_counter()
    codes = [c[0] for c in db.query(StockDailyBar.stock_code).distinct().all()]
    total_rows = 0
    for i, code in enumerate(codes, start=1):
        total_rows += _recompute_pe_percentile_for_code(db, code)
        if i % _COMMIT_EVERY_CODES == 0:
            db.commit()
            logger.info("PE百分位全量进度 codes=%s/%s rows_so_far=%s", i, len(codes), total_rows)
    db.commit()
    elapsed = time.perf_counter() - t0
    logger.info(
        "PE百分位全量完成 codes=%s rows=%s elapsed_sec=%.2f",
        len(codes),
        total_rows,
        elapsed,
    )
    return {
        "ok": True,
        "updated_codes": len(codes),
        "updated_rows": total_rows,
        "elapsed_sec": round(elapsed, 3),
    }
