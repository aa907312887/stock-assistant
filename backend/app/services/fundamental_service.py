"""基本面分析查询服务。"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Literal

from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.models import StockBasic, StockFinancialReport

logger = logging.getLogger(__name__)

SORTABLE_COLUMNS = {
    "roe": StockFinancialReport.roe,
    "roe_dt": StockFinancialReport.roe_dt,
    "roa": StockFinancialReport.roa,
    "debt_to_assets": StockFinancialReport.debt_to_assets,
    "current_ratio": StockFinancialReport.current_ratio,
    "net_margin": StockFinancialReport.net_margin,
    "eps": StockFinancialReport.eps,
    "revenue": StockFinancialReport.revenue,
    "net_profit": StockFinancialReport.net_profit,
    "report_date": StockFinancialReport.report_date,
}


def list_fundamentals(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    code: str | None = None,
    name: str | None = None,
    min_roe: float | None = None,
    max_roe: float | None = None,
    min_debt_to_assets: float | None = None,
    max_debt_to_assets: float | None = None,
    sort_by: str | None = None,
    sort_order: Literal["asc", "desc"] = "desc",
) -> tuple[list[dict[str, Any]], int]:
    """查询每只股票最新一期财报的基本面数据，支持筛选和排序。"""

    # 子查询：每只股票最新的 report_date
    sub = (
        db.query(
            StockFinancialReport.stock_code.label("sc"),
            func.max(StockFinancialReport.report_date).label("max_rd"),
        )
        .group_by(StockFinancialReport.stock_code)
        .subquery()
    )

    q = (
        db.query(StockFinancialReport, StockBasic)
        .join(StockBasic, StockBasic.code == StockFinancialReport.stock_code)
        .join(
            sub,
            and_(
                StockFinancialReport.stock_code == sub.c.sc,
                StockFinancialReport.report_date == sub.c.max_rd,
            ),
        )
    )

    # 模糊搜索
    if code:
        q = q.filter(StockFinancialReport.stock_code.contains(code))
    if name:
        q = q.filter(StockBasic.name.contains(name))

    # 范围筛选
    if min_roe is not None:
        q = q.filter(StockFinancialReport.roe >= min_roe)
    if max_roe is not None:
        q = q.filter(StockFinancialReport.roe <= max_roe)
    if min_debt_to_assets is not None:
        q = q.filter(StockFinancialReport.debt_to_assets >= min_debt_to_assets)
    if max_debt_to_assets is not None:
        q = q.filter(StockFinancialReport.debt_to_assets <= max_debt_to_assets)

    total = q.count()

    # 排序（MySQL 不支持 NULLS LAST，用 CASE 将 NULL 排到末尾）
    sort_col = SORTABLE_COLUMNS.get(sort_by or "roe", StockFinancialReport.roe)
    null_flag = case((sort_col.is_(None), 1), else_=0)
    if sort_order == "asc":
        q = q.order_by(null_flag, sort_col.asc())
    else:
        q = q.order_by(null_flag, sort_col.desc())

    # 分页
    offset = (page - 1) * page_size
    rows = q.offset(offset).limit(page_size).all()

    items: list[dict[str, Any]] = []
    for report, basic in rows:
        items.append({
            "code": basic.code,
            "name": basic.name,
            "exchange": basic.exchange,
            "market": basic.market,
            "report_date": report.report_date,
            "ann_date": report.ann_date,
            "revenue": report.revenue,
            "net_profit": report.net_profit,
            "eps": report.eps,
            "bps": report.bps,
            "roe": report.roe,
            "roe_dt": report.roe_dt,
            "roe_waa": report.roe_waa,
            "roa": report.roa,
            "gross_margin": report.gross_margin,
            "net_margin": report.net_margin,
            "debt_to_assets": report.debt_to_assets,
            "current_ratio": report.current_ratio,
            "quick_ratio": report.quick_ratio,
            "cfps": report.cfps,
            "ebit": report.ebit,
            "ocf_to_profit": report.ocf_to_profit,
        })

    return items, total
