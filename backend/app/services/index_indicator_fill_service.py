"""指数 K 线均线/MACD 填充（依赖 index_*_bar 已写入 close）。"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from app.services.index_pe_percentile_service import normalize_ts_code

import pandas as pd
from sqlalchemy.orm import Session

from app.models.index_daily_bar import IndexDailyBar
from app.models.index_monthly_bar import IndexMonthlyBar
from app.models.index_weekly_bar import IndexWeeklyBar
from app.services.technical_indicator import compute_ma_macd_from_close

logger = logging.getLogger(__name__)

Timeframe = Literal["daily", "weekly", "monthly"]
INCREMENTAL_TAIL_BARS = 400

_TF_MODEL = {
    "daily": (IndexDailyBar, "trade_date", "index_code"),
    "weekly": (IndexWeeklyBar, "trade_week_end", "index_code"),
    "monthly": (IndexMonthlyBar, "trade_month_end", "index_code"),
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


def _rows_to_series(rows: list[Any]) -> pd.Series:
    vals = []
    for row in rows:
        c = row.close
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


def _fill_one_index(
    db: Session,
    model: type,
    date_attr: str,
    code_attr: str,
    index_code: str,
    *,
    trade_date_max: date | None,
    date_start: date | None,
    date_end: date | None,
    mode: Literal["incremental", "backfill", "full"],
) -> int:
    col = getattr(model, date_attr)
    code_col = getattr(model, code_attr)

    if mode == "full":
        rows = db.query(model).filter(code_col == index_code).order_by(col.asc()).all()
        if not rows:
            return 0
        ser = _rows_to_series(rows)
        df = compute_ma_macd_from_close(ser)
        for i, row in enumerate(rows):
            _apply_row_from_df(row, df, i)
        return len(rows)

    if mode == "incremental":
        q = db.query(model).filter(code_col == index_code)
        if trade_date_max is not None:
            q = q.filter(col <= trade_date_max)
        rows = q.order_by(col.asc()).all()
        if len(rows) > INCREMENTAL_TAIL_BARS:
            rows = rows[-INCREMENTAL_TAIL_BARS:]
        if not rows:
            return 0
        ser = _rows_to_series(rows)
        df = compute_ma_macd_from_close(ser)
        for i, row in enumerate(rows):
            _apply_row_from_df(row, df, i)
        return len(rows)

    if date_start is None or date_end is None:
        return 0
    range_rows = (
        db.query(model)
        .filter(code_col == index_code, col >= date_start, col <= date_end)
        .order_by(col.asc())
        .all()
    )
    if not range_rows:
        return 0
    d_first = getattr(range_rows[0], date_attr)
    before = (
        db.query(model)
        .filter(code_col == index_code, col < d_first)
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
    return len(range_rows)


def fill_index_indicators_for_timeframe(
    db: Session,
    timeframe: Timeframe,
    *,
    mode: Literal["incremental", "backfill", "full"] = "incremental",
    trade_date_anchor: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int | None = None,
    only_index_codes: frozenset[str] | None = None,
) -> dict[str, Any]:
    """全市场指数标的填充均线/MACD。"""
    model, date_attr, code_attr = _TF_MODEL[timeframe]
    code_column = getattr(model, code_attr)
    q = db.query(code_column).distinct().order_by(code_column)
    codes = [c for (c,) in q.all() if c]
    if only_index_codes is not None:
        allowed = {normalize_ts_code(x) for x in only_index_codes}
        codes = sorted(c for c in codes if normalize_ts_code(c) in allowed)
    elif limit is not None:
        codes = codes[:limit]

    if mode == "incremental" and trade_date_anchor is None:
        raise ValueError("incremental 模式必须提供 trade_date_anchor")
    if mode == "backfill" and (start_date is None or end_date is None):
        raise ValueError("backfill 模式必须提供 start_date 与 end_date")

    rows_updated = 0
    failed: list[str] = []
    for idx, ic in enumerate(codes, start=1):
        try:
            n = _fill_one_index(
                db,
                model,
                date_attr,
                code_attr,
                ic,
                trade_date_max=trade_date_anchor,
                date_start=start_date,
                date_end=end_date,
                mode=mode,
            )
            rows_updated += n
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.exception("指数指标填充失败 index=%s timeframe=%s", ic, timeframe)
            failed.append(f"{ic}: {exc}")
    return {
        "rows_updated": rows_updated,
        "failed": failed,
        "timeframe": timeframe,
        "mode": mode,
    }


def fill_index_after_daily_sync(
    db: Session,
    *,
    anchor_date: date,
    limit: int | None = None,
    only_index_codes: frozenset[str] | None = None,
) -> dict[str, Any]:
    """日线写入成功后增量填充指标。"""
    return fill_index_indicators_for_timeframe(
        db,
        "daily",
        mode="incremental",
        trade_date_anchor=anchor_date,
        limit=limit,
        only_index_codes=only_index_codes,
    )
