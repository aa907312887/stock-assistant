"""股票累计历史最高/最低：写入 stock_daily_bar（按交易日），不回写 stock_basic。

口径（与 specs/013-历史高低价 一致，存储位置已迁至日线）：
- 对某股票按 trade_date 升序遍历日线，维护扩展最大/最小：
  ``cum_hist_high`` = 截至当日（含）所有已遍历日中 ``high`` 的最大值（跳过 high 为 NULL 的参与比较，
  且该行 cum 继承上一有效扩展值）；``cum_hist_low`` 同理对 ``low`` 取扩展最小。
- 回测在日期 T 只能读取 ``trade_date=T`` 行的 cum 列，等价于「当时已知的历史极值」，不会混入 T 之后的价格。
- 全量任务：对 ``stock_daily_bar`` 中出现的每个 ``stock_code`` 重算并更新该股全部日线行。
- **日常增量**：在 ``stock_daily_bar_sync_service`` 每次成功 upsert 一行日线后调用
  ``apply_cum_extrema_after_daily_upsert``：若该股**不存在**更晚 ``trade_date``，则用**上一交易日**
  行的 ``cum_hist_*`` 与当日 ``high``/``low`` 做 O(1) 递推；若存在更晚行（中间改数/补洞），则对该 code
  **整股**重算。无单独 Cron。
- 不在本服务内改复权口径；与 ``high``/``low`` 已存语义一致。

全量 CLI：``python -m app.scripts.recompute_hist_extrema_full``
"""

from __future__ import annotations

import logging
import time
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import StockDailyBar

logger = logging.getLogger(__name__)

_COMMIT_EVERY_CODES = 80


def _recompute_cumulative_for_code(db: Session, stock_code: str) -> int:
    """按时间顺序写回该股所有日线的 cum_hist_*；返回更新的行数。"""
    bars = (
        db.query(StockDailyBar)
        .filter(StockDailyBar.stock_code == stock_code)
        .order_by(StockDailyBar.trade_date.asc())
        .all()
    )
    max_h: Decimal | None = None
    min_l: Decimal | None = None
    n = 0
    for b in bars:
        if b.high is not None:
            max_h = b.high if max_h is None else max(max_h, b.high)
        if b.low is not None:
            min_l = b.low if min_l is None else min(min_l, b.low)
        b.cum_hist_high = max_h
        b.cum_hist_low = min_l
        n += 1
    return n


def apply_cum_extrema_after_daily_upsert(db: Session, stock_code: str, trade_date: date) -> None:
    """在成功写入/更新某交易日日线后，维护该行 ``cum_hist_*``。

    纯尾部追加：取上一交易日行的累计值与当日 high/low 递推（O(1)）。
    若库中已存在更晚交易日、或上一行累计未回填而存在更早日线，则整股重算以保证与全序递推一致。
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
        _recompute_cumulative_for_code(db, stock_code)
        return

    prev = (
        db.query(StockDailyBar)
        .filter(
            StockDailyBar.stock_code == stock_code,
            StockDailyBar.trade_date < trade_date,
        )
        .order_by(StockDailyBar.trade_date.desc())
        .first()
    )
    if prev is not None and prev.cum_hist_high is None and prev.cum_hist_low is None:
        older = (
            db.query(StockDailyBar)
            .filter(
                StockDailyBar.stock_code == stock_code,
                StockDailyBar.trade_date < prev.trade_date,
            )
            .limit(1)
            .first()
        )
        if older is not None:
            _recompute_cumulative_for_code(db, stock_code)
            return

    max_h = prev.cum_hist_high if prev else None
    min_l = prev.cum_hist_low if prev else None
    if row.high is not None:
        max_h = row.high if max_h is None else max(max_h, row.high)
    if row.low is not None:
        min_l = row.low if min_l is None else min(min_l, row.low)
    row.cum_hist_high = max_h
    row.cum_hist_low = min_l


def run_full_recompute(db: Session) -> dict[str, Any]:
    """全量：对每个有日线的 stock_code 重算累计极值并写回日线表。"""
    t0 = time.perf_counter()
    codes = [c[0] for c in db.query(StockDailyBar.stock_code).distinct().all()]
    total_rows = 0
    for i, code in enumerate(codes, start=1):
        total_rows += _recompute_cumulative_for_code(db, code)
        if i % _COMMIT_EVERY_CODES == 0:
            db.commit()
            logger.info("历史极值全量进度 codes=%s/%s daily_rows_so_far=%s", i, len(codes), total_rows)
    db.commit()
    elapsed = time.perf_counter() - t0
    logger.info(
        "历史极值全量完成（日线累计列）codes=%s daily_rows=%s elapsed_sec=%.2f",
        len(codes),
        total_rows,
        elapsed,
    )
    return {
        "ok": True,
        "updated_codes": len(codes),
        "updated_daily_rows": total_rows,
        "elapsed_sec": round(elapsed, 3),
    }
