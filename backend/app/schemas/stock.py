"""选股列表请求与响应 Schema，与 contracts/api-stock-screening.md 一致。"""
from datetime import date as dt_date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ScreeningQueryParams(BaseModel):
    """GET /api/stock/screening 的 query 参数（由 FastAPI 自动从 query 解析）。"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")
    code: str | None = Field(default=None, description="股票代码模糊")
    pct_min: float | None = None
    pct_max: float | None = None
    price_min: float | None = None
    price_max: float | None = None
    gpm_min: float | None = None
    gpm_max: float | None = None
    revenue_min: float | None = None
    revenue_max: float | None = None
    net_profit_min: float | None = None
    net_profit_max: float | None = None
    data_date: dt_date | None = Field(default=None, description="数据日期 YYYY-MM-DD")


class ScreeningItem(BaseModel):
    """列表单条。"""
    code: str
    name: str | None = None
    exchange: str | None = None
    trade_date: dt_date | None = None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    price: Decimal | None = None
    prev_close: Decimal | None = None
    change_amount: Decimal | None = None
    pct_change: Decimal | None = None
    volume: Decimal | None = None
    amount: Decimal | None = None
    amplitude: Decimal | None = None
    turnover_rate: Decimal | None = None
    report_date: dt_date | None = None
    revenue: Decimal | None = None
    net_profit: Decimal | None = None
    eps: Decimal | None = None
    gross_profit_margin: Decimal | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ScreeningResponse(BaseModel):
    """选股列表响应。"""
    items: list[ScreeningItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    data_date: dt_date | None = None


class LatestDateResponse(BaseModel):
    """最新数据日期。"""
    date: dt_date | None = None
