"""股票历史最高价/最低价：从 stock_daily_bar 聚合写入 stock_basic。

口径（与 specs/013-历史高低价 一致）：
- 对给定股票代码，hist_high = 该股在 stock_daily_bar 中全部交易日的 MAX(high)；
  hist_low = MIN(low)。high/low 为 NULL 的行在 SQL 聚合中自动忽略。
- 不在本服务内做复权转换；与日线表已存字段语义一致。
- 全量任务：覆盖所有 stock_basic 行；在日线中有记录的代码写聚合结果，无日线记录的代码将
  hist_high/hist_low 置为 NULL，并更新 hist_extrema_computed_at。
- 增量任务：仅处理「指定 trade_date 当日存在日线」的股票代码，对该代码仍按**全历史**
  重算 MAX/MIN 后写回；其它股票行不修改。若单日任务失败，不批量清空已有极值（按行更新，
  已成功的行保留；异常向上抛出由调用方记录日志）。
- 若历史日线发生大面积修订，仅靠增量无法保证与全库一致，须在本机执行全量 CLI
 （app.scripts.recompute_hist_extrema_full）纠偏。

本模块不包含随机或非确定性写库逻辑；相同数据库快照下重复执行全量应得到相同极值结果。
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import StockBasic, StockDailyBar

logger = logging.getLogger(__name__)


def _aggregate_all_by_code(db: Session) -> dict[str, tuple[Decimal | None, Decimal | None]]:
    """返回 {stock_code: (max_high, min_low)}，仅包含有日线记录的代码。"""
    rows = (
        db.query(
            StockDailyBar.stock_code,
            func.max(StockDailyBar.high).label("mh"),
            func.min(StockDailyBar.low).label("ml"),
        )
        .group_by(StockDailyBar.stock_code)
        .all()
    )
    out: dict[str, tuple[Decimal | None, Decimal | None]] = {}
    for code, mh, ml in rows:
        out[code] = (mh, ml)
    return out


def _aggregate_one_code(
    db: Session, stock_code: str
) -> tuple[Decimal | None, Decimal | None]:
    row = (
        db.query(
            func.max(StockDailyBar.high).label("mh"),
            func.min(StockDailyBar.low).label("ml"),
        )
        .filter(StockDailyBar.stock_code == stock_code)
        .one()
    )
    return row.mh, row.ml


def run_full_recompute(db: Session) -> dict[str, Any]:
    """全量重算：所有 stock_basic 行根据日线聚合更新极值字段。

    Returns:
        摘要 dict，含 updated_rows、with_bar_codes、elapsed_sec、ok。
    """
    import time

    t0 = time.perf_counter()
    agg = _aggregate_all_by_code(db)
    now = datetime.now()
    basics = db.query(StockBasic).all()
    updated = 0
    for row in basics:
        if row.code in agg:
            mh, ml = agg[row.code]
            row.hist_high = mh
            row.hist_low = ml
        else:
            row.hist_high = None
            row.hist_low = None
        row.hist_extrema_computed_at = now
        updated += 1
    db.commit()
    elapsed = time.perf_counter() - t0
    logger.info(
        "历史极值全量重算完成 rows=%s codes_with_bar=%s elapsed_sec=%.2f",
        updated,
        len(agg),
        elapsed,
    )
    return {
        "ok": True,
        "updated_rows": updated,
        "codes_with_daily": len(agg),
        "elapsed_sec": round(elapsed, 3),
    }


def run_incremental_for_trade_date(db: Session, trade_date: date) -> dict[str, Any]:
    """增量：仅处理在 trade_date 当日有日线的股票，按全历史重算该股极值并写回 stock_basic。

    不在集合内的 stock_basic 行不修改。
    """
    import time

    t0 = time.perf_counter()
    codes = (
        db.query(StockDailyBar.stock_code)
        .filter(StockDailyBar.trade_date == trade_date)
        .distinct()
        .all()
    )
    code_list = [c[0] for c in codes]
    if not code_list:
        logger.info("历史极值增量跳过：trade_date=%s 无日线记录", trade_date)
        return {
            "ok": True,
            "skipped": True,
            "reason": "no_daily_for_date",
            "trade_date": trade_date.isoformat(),
            "updated_codes": 0,
            "elapsed_sec": round(time.perf_counter() - t0, 3),
        }

    now = datetime.now()
    updated = 0
    for code in code_list:
        basic = db.query(StockBasic).filter(StockBasic.code == code).one_or_none()
        if basic is None:
            continue
        mh, ml = _aggregate_one_code(db, code)
        basic.hist_high = mh
        basic.hist_low = ml
        basic.hist_extrema_computed_at = now
        updated += 1
    db.commit()
    elapsed = time.perf_counter() - t0
    logger.info(
        "历史极值增量完成 trade_date=%s updated_codes=%s elapsed_sec=%.2f",
        trade_date,
        updated,
        elapsed,
    )
    return {
        "ok": True,
        "skipped": False,
        "trade_date": trade_date.isoformat(),
        "updated_codes": updated,
        "elapsed_sec": round(elapsed, 3),
    }
