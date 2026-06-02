"""日/周/月 MACD 红柱（macd_hist > 0）对齐筛选工具。

用于历史模拟交易自定义筛选等场景：在 as_of 交易日，取周线 trade_week_end、
月线 trade_month_end 均 ≤ as_of 的最近一根 K 线，要求三根 MACD 柱均为正。
"""

from __future__ import annotations

import bisect
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.stock_daily_bar import StockDailyBar
from app.models.stock_monthly_bar import StockMonthlyBar
from app.models.stock_weekly_bar import StockWeeklyBar


def _hist_val(row: Any) -> float | None:
    h = getattr(row, "macd_hist", None)
    if h is None:
        return None
    return float(h)


def _is_red(h: float | None) -> bool:
    return h is not None and h > 0


def build_period_hist_index(
    rows: list[Any],
    *,
    end_attr: str,
) -> dict[str, list[tuple[date, float]]]:
    """按 stock_code 分组，(周期末端, macd_hist) 按日期升序。"""
    out: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for row in rows:
        code = row.stock_code
        end_d = getattr(row, end_attr)
        h = _hist_val(row)
        if end_d is None or h is None:
            continue
        out[code].append((end_d, h))
    for code in out:
        out[code].sort(key=lambda x: x[0])
    return out


def latest_hist_leq(series: list[tuple[date, float]], as_of: date) -> float | None:
    if not series:
        return None
    ends = [t[0] for t in series]
    idx = bisect.bisect_right(ends, as_of) - 1
    if idx < 0:
        return None
    return series[idx][1]


def codes_with_multi_tf_macd_red(
    weekly_by_code: dict[str, list[tuple[date, float]]],
    monthly_by_code: dict[str, list[tuple[date, float]]],
    codes: Iterable[str],
    as_of: date,
) -> set[str]:
    """返回周、月线 MACD 柱均在 as_of 对齐下为红柱的代码集合（不含日线校验）。"""
    ok: set[str] = set()
    for code in codes:
        wh = latest_hist_leq(weekly_by_code.get(code, []), as_of)
        mh = latest_hist_leq(monthly_by_code.get(code, []), as_of)
        if _is_red(wh) and _is_red(mh):
            ok.add(code)
    return ok


def load_weekly_monthly_hist_indices(
    db: Session,
    trade_date: date,
    stock_codes: list[str],
) -> tuple[dict[str, list[tuple[date, float]]], dict[str, list[tuple[date, float]]]]:
    """批量加载指定代码在 trade_date 及之前的周/月 MACD 柱序列索引。"""
    if not stock_codes:
        return {}, {}
    weekly_rows = (
        db.query(StockWeeklyBar)
        .filter(
            StockWeeklyBar.stock_code.in_(stock_codes),
            StockWeeklyBar.trade_week_end <= trade_date,
        )
        .all()
    )
    monthly_rows = (
        db.query(StockMonthlyBar)
        .filter(
            StockMonthlyBar.stock_code.in_(stock_codes),
            StockMonthlyBar.trade_month_end <= trade_date,
        )
        .all()
    )
    return (
        build_period_hist_index(weekly_rows, end_attr="trade_week_end"),
        build_period_hist_index(monthly_rows, end_attr="trade_month_end"),
    )


def _to_hist_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def macd_red_streak_days(daily_series_asc: list[tuple[date, float | None]], as_of: date) -> int:
    """
    自最近一次 MACD 绿柱（macd_hist ≤ 0 或缺失）之后，截止 as_of 的连续红柱交易日数。

    daily_series_asc：单股 (trade_date, macd_hist) 按日期升序；须含 as_of 当日 K 线。
    """
    if not daily_series_asc or daily_series_asc[-1][0] != as_of:
        return 0
    streak = 0
    for i in range(len(daily_series_asc) - 1, -1, -1):
        h = daily_series_asc[i][1]
        if h is None or h <= 0:
            break
        streak += 1
    return streak


def load_daily_macd_hist_by_code(
    db: Session,
    stock_codes: list[str],
    as_of: date,
    *,
    lookback_calendar_days: int = 400,
) -> dict[str, list[tuple[date, float | None]]]:
    """批量加载各股 as_of 及之前一段日历窗口内的 (trade_date, macd_hist)。"""
    if not stock_codes:
        return {}
    start = as_of - timedelta(days=lookback_calendar_days)
    rows = db.execute(
        select(
            StockDailyBar.stock_code,
            StockDailyBar.trade_date,
            StockDailyBar.macd_hist,
        )
        .where(
            StockDailyBar.stock_code.in_(stock_codes),
            StockDailyBar.trade_date >= start,
            StockDailyBar.trade_date <= as_of,
        )
        .order_by(StockDailyBar.stock_code, StockDailyBar.trade_date)
    ).all()
    out: dict[str, list[tuple[date, float | None]]] = defaultdict(list)
    for code, trade_date, macd_hist in rows:
        out[code].append((trade_date, _to_hist_float(macd_hist)))
    return dict(out)


def macd_red_streak_days_by_code(
    daily_by_code: dict[str, list[tuple[date, float | None]]],
    codes: Iterable[str],
    as_of: date,
) -> dict[str, int]:
    """批量计算各股截止 as_of 的 MACD 红柱持续交易日数。"""
    return {
        code: macd_red_streak_days(daily_by_code.get(code, []), as_of)
        for code in codes
    }
