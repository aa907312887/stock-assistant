"""指数基金专题列表：数据源为 index_*_bar JOIN index_basic。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import and_, func, not_, or_
from sqlalchemy.orm import Session, aliased

from app.models.index_basic import IndexBasic
from app.models.index_daily_bar import IndexDailyBar
from app.models.index_monthly_bar import IndexMonthlyBar
from app.models.index_weekly_bar import IndexWeeklyBar

Timeframe = Literal["daily", "weekly", "monthly"]


def get_latest_bar_date(db: Session, timeframe: Timeframe = "daily") -> date | None:
    """指数 K 线表中的最大日期。"""
    if timeframe == "daily":
        return db.query(func.max(IndexDailyBar.trade_date)).scalar()
    if timeframe == "weekly":
        return db.query(func.max(IndexWeeklyBar.trade_week_end)).scalar()
    if timeframe == "monthly":
        return db.query(func.max(IndexMonthlyBar.trade_month_end)).scalar()
    return None


def get_latest_snapshot_date(db: Session, timeframe: Timeframe = "daily") -> date | None:
    """与个股 screening 一致：周/月取最近一次更新自然日。"""
    if timeframe == "daily":
        return get_latest_bar_date(db, "daily")
    if timeframe == "weekly":
        dt = db.query(func.max(IndexWeeklyBar.updated_at)).scalar()
        return dt.date() if dt else None
    if timeframe == "monthly":
        dt = db.query(func.max(IndexMonthlyBar.updated_at)).scalar()
        return dt.date() if dt else None
    return None


def _ma_bull_alignment_expr(bar: Any) -> Any:
    return and_(
        bar.ma5.isnot(None),
        bar.ma10.isnot(None),
        bar.ma20.isnot(None),
        bar.ma60.isnot(None),
        bar.ma5 > bar.ma10,
        bar.ma10 > bar.ma20,
        bar.ma20 > bar.ma60,
    )


def _expr_ma5_cross_5_10(Curr: Any, Prev: Any) -> Any:
    return and_(
        Prev.index_code.isnot(None),
        Prev.ma5.isnot(None),
        Prev.ma10.isnot(None),
        Curr.ma5.isnot(None),
        Curr.ma10.isnot(None),
        Prev.ma5 <= Prev.ma10,
        Curr.ma5 > Curr.ma10,
    )


def _expr_macd_cross(Curr: Any, Prev: Any) -> Any:
    return and_(
        Prev.index_code.isnot(None),
        Prev.macd_dif.isnot(None),
        Prev.macd_dea.isnot(None),
        Curr.macd_dif.isnot(None),
        Curr.macd_dea.isnot(None),
        Prev.macd_dif <= Prev.macd_dea,
        Curr.macd_dif > Curr.macd_dea,
    )


def _apply_cross_filters(
    base: Any,
    Curr: Any,
    Prev: Any,
    ma_cross: bool | None,
    macd_cross: bool | None,
) -> Any:
    if ma_cross is True:
        base = base.filter(_expr_ma5_cross_5_10(Curr, Prev))
    elif ma_cross is False:
        base = base.filter(or_(Prev.index_code.is_(None), not_(_expr_ma5_cross_5_10(Curr, Prev))))

    if macd_cross is True:
        base = base.filter(_expr_macd_cross(Curr, Prev))
    elif macd_cross is False:
        base = base.filter(or_(Prev.index_code.is_(None), not_(_expr_macd_cross(Curr, Prev))))
    return base


def _apply_index_common_filters(
    base: Any,
    bar: Any,
    code: str | None,
    name: str | None,
    ma_bull: bool | None,
    macd_red: bool | None,
) -> Any:
    if code and code.strip():
        base = base.filter(IndexBasic.ts_code.like(f"%{code.strip()}%"))
    if name and name.strip():
        base = base.filter(IndexBasic.name.like(f"%{name.strip()}%"))

    if ma_bull is True:
        base = base.filter(_ma_bull_alignment_expr(bar))
    elif ma_bull is False:
        base = base.filter(not_(_ma_bull_alignment_expr(bar)))

    if macd_red is True:
        base = base.filter(bar.macd_hist > Decimal("0"))
    elif macd_red is False:
        base = base.filter(or_(bar.macd_hist.is_(None), bar.macd_hist <= Decimal("0")))
    return base


def _prev_bar_subquery(db: Session, bar_model: Any, date_col: Any, data_date: date) -> Any:
    return (
        db.query(bar_model.index_code.label("ic"), func.max(date_col).label("pd"))
        .filter(date_col < data_date)
        .group_by(bar_model.index_code)
        .subquery()
    )


def _query_index_screening(
    db: Session,
    *,
    bar_model: Any,
    date_col_name: str,
    data_date: date,
    page: int,
    page_size: int,
    code: str | None,
    name: str | None,
    ma_bull: bool | None,
    macd_red: bool | None,
    ma_cross: bool | None,
    macd_cross: bool | None,
    row_mapper: Callable[..., dict[str, Any]],
    join_daily_on_end: bool,
) -> tuple[list[dict[str, Any]], int, date]:
    """统一构建指数日/周/月列表（无财务表）。"""
    date_col = getattr(bar_model, date_col_name)
    need_cross = ma_cross is not None or macd_cross is not None
    daily_alias: Any = None
    if join_daily_on_end:
        daily_alias = aliased(IndexDailyBar, name="index_screening_daily")

    if not need_cross:
        entities: list[Any] = [bar_model, IndexBasic]
        if daily_alias is not None:
            entities.append(daily_alias)
        base = db.query(*entities).join(IndexBasic, bar_model.index_code == IndexBasic.ts_code)
        if daily_alias is not None:
            base = base.outerjoin(
                daily_alias,
                and_(bar_model.index_code == daily_alias.index_code, date_col == daily_alias.trade_date),
            )
        base = base.filter(date_col == data_date)
        base = _apply_index_common_filters(base, bar_model, code, name, ma_bull, macd_red)
    else:
        Curr = aliased(bar_model, name="curr_ibar")
        Prev = aliased(bar_model, name="prev_ibar")
        prev_sub = _prev_bar_subquery(db, bar_model, date_col, data_date)
        curr_dc = getattr(Curr, date_col_name)
        prev_dc = getattr(Prev, date_col_name)
        entities_c: list[Any] = [Curr, IndexBasic]
        if daily_alias is not None:
            entities_c.append(daily_alias)
        base = (
            db.query(*entities_c)
            .join(IndexBasic, Curr.index_code == IndexBasic.ts_code)
            .outerjoin(prev_sub, Curr.index_code == prev_sub.c.ic)
            .outerjoin(Prev, and_(Prev.index_code == prev_sub.c.ic, prev_dc == prev_sub.c.pd))
        )
        if daily_alias is not None:
            base = base.outerjoin(
                daily_alias,
                and_(Curr.index_code == daily_alias.index_code, curr_dc == daily_alias.trade_date),
            )
        base = base.filter(curr_dc == data_date)
        base = _apply_index_common_filters(base, Curr, code, name, ma_bull, macd_red)
        base = _apply_cross_filters(base, Curr, Prev, ma_cross, macd_cross)

    order_col = Curr.index_code if need_cross else bar_model.index_code
    total = base.count()
    base = base.order_by(order_col)
    rows = base.offset((page - 1) * page_size).limit(page_size).all()
    if daily_alias is not None:
        items = [row_mapper(q, b, d) for q, b, d in rows]
    else:
        items = [row_mapper(q, b, None) for q, b in rows]
    return items, total, data_date


def _row_daily(quote: IndexDailyBar, basic: IndexBasic, daily_ext: IndexDailyBar | None = None) -> dict[str, Any]:
    _ = daily_ext
    return {
        "instrument_type": "index",
        "code": basic.ts_code,
        "name": basic.name,
        "exchange": basic.market,
        "trade_date": quote.trade_date,
        "open": quote.open,
        "high": quote.high,
        "low": quote.low,
        "hist_high": None,
        "hist_low": None,
        "close": quote.close,
        "price": quote.close,
        "prev_close": quote.prev_close,
        "change_amount": quote.change_amount,
        "pct_change": quote.pct_change,
        "ma5": quote.ma5,
        "ma10": quote.ma10,
        "ma20": quote.ma20,
        "ma60": quote.ma60,
        "macd_dif": quote.macd_dif,
        "macd_dea": quote.macd_dea,
        "macd_hist": quote.macd_hist,
        "volume": quote.volume,
        "amount": quote.amount,
        "amplitude": quote.amplitude,
        "turnover_rate": None,
        "pe": None,
        "pe_ttm": None,
        "pe_percentile": None,
        "pb": None,
        "dv_ratio": None,
        "report_date": None,
        "revenue": None,
        "net_profit": None,
        "eps": None,
        "gross_profit_margin": None,
        "roe": None,
        "bps": None,
        "net_margin": None,
        "debt_to_assets": None,
        "updated_at": quote.updated_at,
    }


def _row_wm(
    quote: IndexWeeklyBar | IndexMonthlyBar,
    basic: IndexBasic,
    daily_ext: IndexDailyBar | None,
) -> dict[str, Any]:
    end_date = getattr(quote, "trade_week_end", None) or getattr(quote, "trade_month_end")
    return {
        "instrument_type": "index",
        "code": basic.ts_code,
        "name": basic.name,
        "exchange": basic.market,
        "trade_date": end_date,
        "open": quote.open,
        "high": quote.high,
        "low": quote.low,
        "hist_high": daily_ext.high if daily_ext is not None else None,
        "hist_low": daily_ext.low if daily_ext is not None else None,
        "close": quote.close,
        "price": quote.close,
        "prev_close": None,
        "change_amount": quote.change_amount,
        "pct_change": quote.pct_change,
        "ma5": quote.ma5,
        "ma10": quote.ma10,
        "ma20": quote.ma20,
        "ma60": quote.ma60,
        "macd_dif": quote.macd_dif,
        "macd_dea": quote.macd_dea,
        "macd_hist": quote.macd_hist,
        "volume": quote.volume,
        "amount": quote.amount,
        "amplitude": None,
        "turnover_rate": None,
        "pe": None,
        "pe_ttm": None,
        "pe_percentile": None,
        "pb": None,
        "dv_ratio": None,
        "report_date": None,
        "revenue": None,
        "net_profit": None,
        "eps": None,
        "gross_profit_margin": None,
        "roe": None,
        "bps": None,
        "net_margin": None,
        "debt_to_assets": None,
        "updated_at": quote.updated_at,
    }


def list_index_screening(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    timeframe: Timeframe = "daily",
    code: str | None = None,
    name: str | None = None,
    ma_bull: bool | None = None,
    macd_red: bool | None = None,
    ma_cross: bool | None = None,
    macd_cross: bool | None = None,
    data_date: date | None = None,
) -> tuple[list[dict[str, Any]], int, date | None]:
    if timeframe == "daily":
        dd = data_date or get_latest_bar_date(db, "daily")
        if not dd:
            return [], 0, None
        items, total, out = _query_index_screening(
            db,
            bar_model=IndexDailyBar,
            date_col_name="trade_date",
            data_date=dd,
            page=page,
            page_size=page_size,
            code=code,
            name=name,
            ma_bull=ma_bull,
            macd_red=macd_red,
            ma_cross=ma_cross,
            macd_cross=macd_cross,
            row_mapper=_row_daily,
            join_daily_on_end=False,
        )
        return items, total, out

    if timeframe == "weekly":
        dd = data_date or get_latest_bar_date(db, "weekly")
        if not dd:
            return [], 0, None
        items, total, out = _query_index_screening(
            db,
            bar_model=IndexWeeklyBar,
            date_col_name="trade_week_end",
            data_date=dd,
            page=page,
            page_size=page_size,
            code=code,
            name=name,
            ma_bull=ma_bull,
            macd_red=macd_red,
            ma_cross=ma_cross,
            macd_cross=macd_cross,
            row_mapper=_row_wm,
            join_daily_on_end=True,
        )
        return items, total, out

    dd = data_date or get_latest_bar_date(db, "monthly")
    if not dd:
        return [], 0, None
    items, total, out = _query_index_screening(
        db,
        bar_model=IndexMonthlyBar,
        date_col_name="trade_month_end",
        data_date=dd,
        page=page,
        page_size=page_size,
        code=code,
        name=name,
        ma_bull=ma_bull,
        macd_red=macd_red,
        ma_cross=ma_cross,
        macd_cross=macd_cross,
        row_mapper=_row_wm,
        join_daily_on_end=True,
    )
    return items, total, out
