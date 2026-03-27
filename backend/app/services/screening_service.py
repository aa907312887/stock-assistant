"""综合选股：从 stock_basic、各周期 bar 表、利润表关联筛选。"""
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import and_, func, not_, or_
from sqlalchemy.orm import Session, aliased

from app.models import (
    StockBasic,
    StockDailyBar,
    StockFinancialReport,
    StockMonthlyBar,
    StockWeeklyBar,
)

Timeframe = Literal["daily", "weekly", "monthly"]


def get_latest_bar_date(db: Session, timeframe: Timeframe = "daily") -> date | None:
    """返回指定周期 K 线表中的最大日期列。"""
    if timeframe == "daily":
        return db.query(func.max(StockDailyBar.trade_date)).scalar()
    if timeframe == "weekly":
        return db.query(func.max(StockWeeklyBar.trade_week_end)).scalar()
    if timeframe == "monthly":
        return db.query(func.max(StockMonthlyBar.trade_month_end)).scalar()
    return None


def get_latest_snapshot_date(db: Session, timeframe: Timeframe = "daily") -> date | None:
    """
    返回各周期“最新同步快照日期”（按 updated_at 取最大日期）。

    - daily：沿用交易日口径（trade_date）
    - weekly/monthly：返回最近一次更新发生的自然日，用于前端展示“今天是否已更新”
    """
    if timeframe == "daily":
        return get_latest_bar_date(db, "daily")
    if timeframe == "weekly":
        dt = db.query(func.max(StockWeeklyBar.updated_at)).scalar()
        return dt.date() if dt else None
    if timeframe == "monthly":
        dt = db.query(func.max(StockMonthlyBar.updated_at)).scalar()
        return dt.date() if dt else None
    return None


def get_latest_trade_date(db: Session) -> date | None:
    """兼容旧调用：等价于 get_latest_bar_date(daily)。"""
    return get_latest_bar_date(db, "daily")


def _ma_bull_alignment_expr(bar: Any) -> Any:
    """均线多头排列：MA5>MA10>MA20>MA60 且四者均非空（各周期 bar 表列名一致）。"""
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
    """MA5 上穿 MA10：上一根 ma5<=ma10，当前根 ma5>ma10，四值均有。"""
    return and_(
        Prev.stock_code.isnot(None),
        Prev.ma5.isnot(None),
        Prev.ma10.isnot(None),
        Curr.ma5.isnot(None),
        Curr.ma10.isnot(None),
        Prev.ma5 <= Prev.ma10,
        Curr.ma5 > Curr.ma10,
    )


def _expr_macd_cross(Curr: Any, Prev: Any) -> Any:
    """MACD 金叉：DIF 上穿 DEA。"""
    return and_(
        Prev.stock_code.isnot(None),
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
    """金叉：是=本根相对紧邻上一根满足穿越；否=不满足（含无上一根）。"""
    if ma_cross is True:
        base = base.filter(_expr_ma5_cross_5_10(Curr, Prev))
    elif ma_cross is False:
        base = base.filter(or_(Prev.stock_code.is_(None), not_(_expr_ma5_cross_5_10(Curr, Prev))))

    if macd_cross is True:
        base = base.filter(_expr_macd_cross(Curr, Prev))
    elif macd_cross is False:
        base = base.filter(or_(Prev.stock_code.is_(None), not_(_expr_macd_cross(Curr, Prev))))
    return base


def list_screening(
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
    """
    选股列表：指定周期 K 线 JOIN 股票基础，LEFT JOIN 最近利润表，筛选后分页。
    金叉类筛选需关联上一根同周期 K 线。
    """
    if timeframe == "daily":
        return _list_screening_daily(
            db,
            page=page,
            page_size=page_size,
            code=code,
            name=name,
            ma_bull=ma_bull,
            macd_red=macd_red,
            ma_cross=ma_cross,
            macd_cross=macd_cross,
            data_date=data_date,
        )
    if timeframe == "weekly":
        return _list_screening_weekly(
            db,
            page=page,
            page_size=page_size,
            code=code,
            name=name,
            ma_bull=ma_bull,
            macd_red=macd_red,
            ma_cross=ma_cross,
            macd_cross=macd_cross,
            data_date=data_date,
        )
    return _list_screening_monthly(
        db,
        page=page,
        page_size=page_size,
        code=code,
        name=name,
        ma_bull=ma_bull,
        macd_red=macd_red,
        ma_cross=ma_cross,
        macd_cross=macd_cross,
        data_date=data_date,
    )


def _financial_subquery(db: Session, data_date: date) -> Any:
    return (
        db.query(
            StockFinancialReport.stock_code.label("r_code"),
            func.max(StockFinancialReport.report_date).label("r_date"),
        )
        .filter(StockFinancialReport.report_date <= data_date)
        .group_by(StockFinancialReport.stock_code)
        .subquery()
    )


def _apply_common_filters(base: Any, bar: Any, code: str | None, name: str | None, ma_bull: bool | None, macd_red: bool | None) -> Any:
    if code and code.strip():
        base = base.filter(StockBasic.code.like(f"%{code.strip()}%"))
    if name and name.strip():
        base = base.filter(StockBasic.name.like(f"%{name.strip()}%"))

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
        db.query(
            bar_model.stock_code.label("sc"),
            func.max(date_col).label("pd"),
        )
        .filter(date_col < data_date)
        .group_by(bar_model.stock_code)
        .subquery()
    )


def _query_screening(
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
    row_mapper: Callable[[Any, StockBasic, StockFinancialReport | None], dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, date]:
    """统一构建日/周/月列表查询。"""
    date_col = getattr(bar_model, date_col_name)
    need_cross = ma_cross is not None or macd_cross is not None
    sub_rep = _financial_subquery(db, data_date)

    if not need_cross:
        base = (
            db.query(bar_model, StockBasic, StockFinancialReport)
            .join(StockBasic, bar_model.stock_code == StockBasic.code)
            .outerjoin(sub_rep, bar_model.stock_code == sub_rep.c.r_code)
            .outerjoin(
                StockFinancialReport,
                and_(
                    StockFinancialReport.stock_code == sub_rep.c.r_code,
                    StockFinancialReport.report_date == sub_rep.c.r_date,
                ),
            )
            .filter(date_col == data_date)
        )
        base = _apply_common_filters(base, bar_model, code, name, ma_bull, macd_red)
    else:
        Curr = aliased(bar_model, name="curr_bar")
        Prev = aliased(bar_model, name="prev_bar")
        prev_sub = _prev_bar_subquery(db, bar_model, date_col, data_date)
        curr_dc = getattr(Curr, date_col_name)
        prev_dc = getattr(Prev, date_col_name)
        base = (
            db.query(Curr, StockBasic, StockFinancialReport)
            .join(StockBasic, Curr.stock_code == StockBasic.code)
            .outerjoin(sub_rep, Curr.stock_code == sub_rep.c.r_code)
            .outerjoin(
                StockFinancialReport,
                and_(
                    StockFinancialReport.stock_code == sub_rep.c.r_code,
                    StockFinancialReport.report_date == sub_rep.c.r_date,
                ),
            )
            .outerjoin(prev_sub, Curr.stock_code == prev_sub.c.sc)
            .outerjoin(
                Prev,
                and_(Prev.stock_code == prev_sub.c.sc, prev_dc == prev_sub.c.pd),
            )
            .filter(curr_dc == data_date)
        )
        base = _apply_common_filters(base, Curr, code, name, ma_bull, macd_red)
        base = _apply_cross_filters(base, Curr, Prev, ma_cross, macd_cross)

    order_col = Curr.stock_code if need_cross else bar_model.stock_code
    total = base.count()
    rows = base.order_by(order_col).offset((page - 1) * page_size).limit(page_size).all()
    items = [row_mapper(q, b, r) for q, b, r in rows]
    return items, total, data_date


def _list_screening_daily(
    db: Session,
    *,
    page: int,
    page_size: int,
    code: str | None,
    name: str | None,
    ma_bull: bool | None,
    macd_red: bool | None,
    ma_cross: bool | None,
    macd_cross: bool | None,
    data_date: date | None,
) -> tuple[list[dict[str, Any]], int, date | None]:
    data_date = data_date or get_latest_bar_date(db, "daily")
    if not data_date:
        return [], 0, None
    items, total, dd = _query_screening(
        db,
        bar_model=StockDailyBar,
        date_col_name="trade_date",
        data_date=data_date,
        page=page,
        page_size=page_size,
        code=code,
        name=name,
        ma_bull=ma_bull,
        macd_red=macd_red,
        ma_cross=ma_cross,
        macd_cross=macd_cross,
        row_mapper=_row_to_item_daily,
    )
    return items, total, dd


def _list_screening_weekly(
    db: Session,
    *,
    page: int,
    page_size: int,
    code: str | None,
    name: str | None,
    ma_bull: bool | None,
    macd_red: bool | None,
    ma_cross: bool | None,
    macd_cross: bool | None,
    data_date: date | None,
) -> tuple[list[dict[str, Any]], int, date | None]:
    data_date = data_date or get_latest_bar_date(db, "weekly")
    if not data_date:
        return [], 0, None
    items, total, dd = _query_screening(
        db,
        bar_model=StockWeeklyBar,
        date_col_name="trade_week_end",
        data_date=data_date,
        page=page,
        page_size=page_size,
        code=code,
        name=name,
        ma_bull=ma_bull,
        macd_red=macd_red,
        ma_cross=ma_cross,
        macd_cross=macd_cross,
        row_mapper=_row_to_item_weekly_monthly,
    )
    return items, total, dd


def _list_screening_monthly(
    db: Session,
    *,
    page: int,
    page_size: int,
    code: str | None,
    name: str | None,
    ma_bull: bool | None,
    macd_red: bool | None,
    ma_cross: bool | None,
    macd_cross: bool | None,
    data_date: date | None,
) -> tuple[list[dict[str, Any]], int, date | None]:
    data_date = data_date or get_latest_bar_date(db, "monthly")
    if not data_date:
        return [], 0, None
    items, total, dd = _query_screening(
        db,
        bar_model=StockMonthlyBar,
        date_col_name="trade_month_end",
        data_date=data_date,
        page=page,
        page_size=page_size,
        code=code,
        name=name,
        ma_bull=ma_bull,
        macd_red=macd_red,
        ma_cross=ma_cross,
        macd_cross=macd_cross,
        row_mapper=_row_to_item_weekly_monthly,
    )
    return items, total, dd


def _row_to_item_daily(quote: StockDailyBar, basic: StockBasic, report: StockFinancialReport | None) -> dict[str, Any]:
    return {
        "code": basic.code,
        "name": basic.name,
        "exchange": basic.exchange or basic.market,
        "trade_date": quote.trade_date,
        "open": quote.open,
        "high": quote.high,
        "low": quote.low,
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
        "turnover_rate": quote.turnover_rate,
        "pe": quote.pe,
        "pe_ttm": quote.pe_ttm,
        "pb": quote.pb,
        "dv_ratio": quote.dv_ratio,
        "report_date": report.report_date if report else None,
        "revenue": report.revenue if report else None,
        "net_profit": report.net_profit if report else None,
        "eps": report.eps if report else None,
        "gross_profit_margin": report.gross_margin if report else None,
        "updated_at": quote.updated_at,
    }


def _row_to_item_weekly_monthly(
    quote: StockWeeklyBar | StockMonthlyBar, basic: StockBasic, report: StockFinancialReport | None
) -> dict[str, Any]:
    end_date = getattr(quote, "trade_week_end", None) or getattr(quote, "trade_month_end")
    return {
        "code": basic.code,
        "name": basic.name,
        "exchange": basic.exchange or basic.market,
        "trade_date": end_date,
        "open": quote.open,
        "high": quote.high,
        "low": quote.low,
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
        "pb": None,
        "dv_ratio": None,
        "report_date": report.report_date if report else None,
        "revenue": report.revenue if report else None,
        "net_profit": report.net_profit if report else None,
        "eps": report.eps if report else None,
        "gross_profit_margin": report.gross_margin if report else None,
        "updated_at": quote.updated_at,
    }
