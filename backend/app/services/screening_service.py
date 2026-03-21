"""综合选股：从 stock_basic、stock_daily_quote、利润表关联筛选。"""
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models import (
    StockBasic,
    StockDailyQuote,
    StockFinancialReport,
)


def get_latest_trade_date(db: Session) -> date | None:
    """返回 stock_daily_quote 中最大 trade_date。"""
    return db.query(func.max(StockDailyQuote.trade_date)).scalar()


def list_screening(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    code: str | None = None,
    pct_min: float | None = None,
    pct_max: float | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    gpm_min: float | None = None,
    gpm_max: float | None = None,
    revenue_min: float | None = None,
    revenue_max: float | None = None,
    net_profit_min: float | None = None,
    net_profit_max: float | None = None,
    data_date: date | None = None,
) -> tuple[list[dict[str, Any]], int, date | None]:
    """
    选股列表：当日行情 JOIN 股票基础，LEFT JOIN 最近利润表，筛选后分页。
    返回 (items, total, data_date)。
    """
    data_date = data_date or get_latest_trade_date(db)
    if not data_date:
        return [], 0, None

    sub_rep = (
        db.query(
            StockFinancialReport.stock_code.label("r_code"),
            func.max(StockFinancialReport.report_date).label("r_date"),
        )
        .filter(StockFinancialReport.report_date <= data_date)
        .group_by(StockFinancialReport.stock_code)
        .subquery()
    )

    base = (
        db.query(StockDailyQuote, StockBasic, StockFinancialReport)
        .join(StockBasic, StockDailyQuote.stock_code == StockBasic.code)
        .outerjoin(sub_rep, StockDailyQuote.stock_code == sub_rep.c.r_code)
        .outerjoin(
            StockFinancialReport,
            and_(
                StockFinancialReport.stock_code == sub_rep.c.r_code,
                StockFinancialReport.report_date == sub_rep.c.r_date,
            ),
        )
        .filter(StockDailyQuote.trade_date == data_date)
    )

    if code and code.strip():
        base = base.filter(StockBasic.code.like(f"%{code.strip()}%"))
    if pct_min is not None:
        base = base.filter(StockDailyQuote.pct_change >= Decimal(str(pct_min)))
    if pct_max is not None:
        base = base.filter(StockDailyQuote.pct_change <= Decimal(str(pct_max)))
    if price_min is not None:
        base = base.filter(StockDailyQuote.close >= Decimal(str(price_min)))
    if price_max is not None:
        base = base.filter(StockDailyQuote.close <= Decimal(str(price_max)))
    gpm_expr = StockFinancialReport.gross_margin
    if gpm_min is not None:
        base = base.filter(gpm_expr >= Decimal(str(gpm_min)))
    if gpm_max is not None:
        base = base.filter(gpm_expr <= Decimal(str(gpm_max)))
    if revenue_min is not None:
        base = base.filter(StockFinancialReport.revenue >= Decimal(str(revenue_min)))
    if revenue_max is not None:
        base = base.filter(StockFinancialReport.revenue <= Decimal(str(revenue_max)))
    if net_profit_min is not None:
        base = base.filter(StockFinancialReport.net_profit >= Decimal(str(net_profit_min)))
    if net_profit_max is not None:
        base = base.filter(StockFinancialReport.net_profit <= Decimal(str(net_profit_max)))

    total = base.count()
    rows = (
        base.order_by(StockDailyQuote.stock_code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for quote, basic, report in rows:
        items.append(
            {
                "code": basic.code,
                "name": basic.name,
                "exchange": basic.market,
                "trade_date": quote.trade_date,
                "open": quote.open,
                "high": quote.high,
                "low": quote.low,
                "close": quote.close,
                "price": quote.close,
                "prev_close": quote.prev_close,
                "change_amount": quote.change_amount,
                "pct_change": quote.pct_change,
                "volume": quote.volume,
                "amount": quote.amount,
                "amplitude": quote.amplitude,
                "turnover_rate": quote.turnover_rate,
                "report_date": report.report_date if report else None,
                "revenue": report.revenue if report else None,
                "net_profit": report.net_profit if report else None,
                "eps": report.eps if report else None,
                "gross_profit_margin": report.gross_margin if report else None,
                "updated_at": quote.updated_at,
            }
        )
    return items, total, data_date
