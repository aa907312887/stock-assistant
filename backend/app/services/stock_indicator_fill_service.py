"""将均线与 MACD 写入日/周/月 bar 表（行情同步后或手工回填）。

本库 K 线 OHLC 为**前复权**口径（日线 `pro_bar` qfq，周/月 `stk_week_month_adj`），
指标计算仅依赖已落库的 `close` 序列与 `technical_indicator` 公式，无单独「未复权」分支。
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import pandas as pd
from sqlalchemy.orm import Session

from app.models import StockDailyBar, StockMonthlyBar, StockWeeklyBar
from app.services.technical_indicator import compute_ma_macd_from_close

logger = logging.getLogger(__name__)

Timeframe = Literal["daily", "weekly", "monthly"]

# 增量：仅取最近若干根 K 线重算，需覆盖 MA60 与 MACD 预热
INCREMENTAL_TAIL_BARS = 400

# 全市场循环时每处理 N 只打一条进度日志（避免刷屏）
PROGRESS_LOG_EVERY = 50

_TIMEFRAME_MODEL = {
    "daily": (StockDailyBar, "trade_date"),
    "weekly": (StockWeeklyBar, "trade_week_end"),
    "monthly": (StockMonthlyBar, "trade_month_end"),
}


def _to_decimal(x: Any) -> Decimal | None:
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except TypeError:
        pass
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if pd.isna(v) or v != v:
        return None
    return Decimal(str(round(v, 8)))


def _rows_to_series(rows: list[Any], close_attr: str = "close") -> pd.Series:
    vals = []
    for row in rows:
        c = getattr(row, close_attr)
        vals.append(float(c) if c is not None else float("nan"))
    return pd.Series(vals)


def _apply_row_from_df(row: Any, df: pd.DataFrame, index: int) -> None:
    if index >= len(df):
        return
    r = df.iloc[index]
    row.ma5 = _to_decimal(r["ma5"])
    row.ma10 = _to_decimal(r["ma10"])
    row.ma20 = _to_decimal(r["ma20"])
    row.ma60 = _to_decimal(r["ma60"])
    row.macd_dif = _to_decimal(r["macd_dif"])
    row.macd_dea = _to_decimal(r["macd_dea"])
    row.macd_hist = _to_decimal(r["macd_hist"])


def _fill_one_stock(
    db: Session,
    model: type,
    date_attr: str,
    stock_code: str,
    *,
    trade_date_max: date | None,
    date_start: date | None,
    date_end: date | None,
    mode: Literal["incremental", "backfill", "full"],
    verbose: bool = False,
) -> int:
    col = getattr(model, date_attr)
    if mode == "full":
        rows = db.query(model).filter(model.stock_code == stock_code).order_by(col.asc()).all()
        if not rows:
            if verbose:
                logger.info("明细[full] stock=%s 全表0根 表=%s", stock_code, model.__tablename__)
            return 0
        ser = _rows_to_series(rows)
        df = compute_ma_macd_from_close(ser)
        for i, row in enumerate(rows):
            _apply_row_from_df(row, df, i)
        if verbose:
            first_r, last_r = rows[0], rows[-1]
            logger.info(
                "明细[full] stock=%s 全表K线=%s根 日期[%s..%s] 末根close=%s ma5=%s macd_dif=%s",
                stock_code,
                len(rows),
                getattr(first_r, date_attr),
                getattr(last_r, date_attr),
                last_r.close,
                last_r.ma5,
                last_r.macd_dif,
            )
        return len(rows)

    if mode == "incremental":
        q = db.query(model).filter(model.stock_code == stock_code)
        if trade_date_max is not None:
            q = q.filter(col <= trade_date_max)
        rows = q.order_by(col.asc()).all()
        n_before_tail = len(rows)
        if len(rows) > INCREMENTAL_TAIL_BARS:
            rows = rows[-INCREMENTAL_TAIL_BARS:]
        if not rows:
            if verbose:
                cnt_any = db.query(model).filter(model.stock_code == stock_code).count()
                logger.info(
                    "明细[incremental] stock=%s 锚点=%s 过滤后0根 | 该标的全表K线数=%s",
                    stock_code,
                    trade_date_max,
                    cnt_any,
                )
            return 0
        ser = _rows_to_series(rows)
        df = compute_ma_macd_from_close(ser)
        for i, row in enumerate(rows):
            _apply_row_from_df(row, df, i)
        if verbose:
            first_r, last_r = rows[0], rows[-1]
            logger.info(
                "明细[incremental] stock=%s 截断前根数=%s 参与计算=%s 日期[%s..%s] "
                "末根close=%s ma5=%s macd_dif=%s macd_hist=%s",
                stock_code,
                n_before_tail,
                len(rows),
                getattr(first_r, date_attr),
                getattr(last_r, date_attr),
                last_r.close,
                last_r.ma5,
                last_r.macd_dif,
                last_r.macd_hist,
            )
        return len(rows)

    # backfill：重算 [date_start, date_end] 内各行，前缀带历史 K 线
    if date_start is None or date_end is None:
        return 0
    range_rows = (
        db.query(model)
        .filter(model.stock_code == stock_code, col >= date_start, col <= date_end)
        .order_by(col.asc())
        .all()
    )
    if not range_rows:
        if verbose:
            cnt_any = db.query(model).filter(model.stock_code == stock_code).count()
            logger.info(
                "明细[backfill] stock=%s 区间[%s..%s]内0根K线 | 该标的全表任意日期K线数=%s 表=%s",
                stock_code,
                date_start,
                date_end,
                cnt_any,
                model.__tablename__,
            )
        return 0
    d_first = getattr(range_rows[0], date_attr)
    d_last = getattr(range_rows[-1], date_attr)
    before = (
        db.query(model)
        .filter(model.stock_code == stock_code, col < d_first)
        .order_by(col.desc())
        .limit(INCREMENTAL_TAIL_BARS)
    )
    before_rows = list(reversed(before.all()))
    all_rows = before_rows + range_rows
    ser = _rows_to_series(all_rows)
    df = compute_ma_macd_from_close(ser)
    offset = len(before_rows)
    for j, row in enumerate(range_rows):
        _apply_row_from_df(row, df, offset + j)
    if verbose:
        last_r = range_rows[-1]
        logger.info(
            "明细[backfill] stock=%s 区间内K线=%s根 前缀历史=%s根 区间日期[%s..%s] "
            "末根close=%s ma5=%s macd_dif=%s macd_hist=%s 本标的提交行数=%s",
            stock_code,
            len(range_rows),
            len(before_rows),
            d_first,
            d_last,
            last_r.close,
            last_r.ma5,
            last_r.macd_dif,
            last_r.macd_hist,
            len(range_rows),
        )
    return len(range_rows)


def fill_indicators_for_timeframe(
    db: Session,
    timeframe: Timeframe,
    *,
    mode: Literal["incremental", "backfill", "full"] = "incremental",
    trade_date_anchor: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    全市场或抽样填充指标。

    - incremental：需 trade_date_anchor；每只股票取最近至多 INCREMENTAL_TAIL_BARS 根（且 date<=anchor）重算。
    - backfill：需 start_date、end_date；重算区间内各行（带历史前缀）。
    - full：每只股票加载该周期表内**全部** K 线重算并写回（用于一次性全表对齐）。
    """
    model, date_attr = _TIMEFRAME_MODEL[timeframe]
    # 必须从「该 K 线表」取 distinct stock_code，不能只用 stock_basic：
    # 否则 basic 缺失、与 bar 代码格式不一致时，会出现「日线有数据但指标一行都不更新」。
    codes = _list_codes_from_bar_table(db, model, limit=limit)
    if not codes:
        logger.warning(
            "指标填充跳过：表 %s 中 distinct stock_code 为空，请确认已同步 K 线",
            model.__tablename__,
        )
    elif verbose:
        preview = codes[: min(5, len(codes))]
        logger.info(
            "明细 表=%s 本次标的数=%s limit=%s 预览前若干code=%s",
            model.__tablename__,
            len(codes),
            limit,
            preview,
        )
    rows_updated = 0
    failed: list[str] = []
    if mode == "incremental" and trade_date_anchor is None:
        raise ValueError("incremental 模式必须提供 trade_date_anchor")
    if mode == "backfill" and (start_date is None or end_date is None):
        raise ValueError("backfill 模式必须提供 start_date 与 end_date")

    total_codes = len(codes)
    logger.info(
        "指标填充开始 timeframe=%s mode=%s 标的数=%s anchor=%s start=%s end=%s",
        timeframe,
        mode,
        total_codes,
        trade_date_anchor,
        start_date,
        end_date,
    )
    for idx, code in enumerate(codes, start=1):
        try:
            n = _fill_one_stock(
                db,
                model,
                date_attr,
                code,
                trade_date_max=trade_date_anchor,
                date_start=start_date,
                date_end=end_date,
                mode=mode,
                verbose=verbose,
            )
            rows_updated += n
            db.commit()
            if idx == 1 or idx % PROGRESS_LOG_EVERY == 0 or idx == total_codes:
                logger.info(
                    "指标填充进度 %s/%s 当前=%s 累计更新行数=%s 失败数=%s",
                    idx,
                    total_codes,
                    code,
                    rows_updated,
                    len(failed),
                )
        except Exception as exc:
            db.rollback()
            logger.exception("指标填充失败 stock=%s timeframe=%s", code, timeframe)
            failed.append(f"{code}: {exc}")
    logger.info(
        "指标填充结束 timeframe=%s 累计更新行数=%s 失败标的数=%s",
        timeframe,
        rows_updated,
        len(failed),
    )
    return {
        "rows_updated": rows_updated,
        "failed_stocks": failed,
        "timeframe": timeframe,
        "mode": mode,
    }


def fill_after_sync(
    db: Session,
    timeframe: Timeframe,
    *,
    anchor_date: date,
    limit: int | None = None,
) -> dict[str, Any]:
    """行情子任务成功写入后调用（增量）。"""
    return fill_indicators_for_timeframe(
        db,
        timeframe,
        mode="incremental",
        trade_date_anchor=anchor_date,
        limit=limit,
    )


def _list_codes_from_bar_table(db: Session, model: type, *, limit: int | None) -> list[str]:
    """从目标 bar 表取实际存在行情的 stock_code，保证与日线/周线/月线数据一致。"""
    q = db.query(model.stock_code).distinct().order_by(model.stock_code)
    rows = [c for (c,) in q.all() if c]
    if limit is not None:
        rows = rows[:limit]
    return rows
