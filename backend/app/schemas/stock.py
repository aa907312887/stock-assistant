"""选股列表请求与响应 Schema，与 contracts/api-stock-screening.md 一致。"""
from datetime import date as dt_date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

ScreeningTimeframe = Literal["daily", "weekly", "monthly"]


class ScreeningQueryParams(BaseModel):
    """GET /api/stock/screening 的 query 参数（由 FastAPI 自动从 query 解析）。"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")
    code: str | None = Field(default=None, description="股票代码模糊")
    name: str | None = Field(default=None, description="股票名称模糊")
    ma_bull: bool | None = Field(default=None, description="是否均线多头排列 MA5>MA10>MA20>MA60")
    macd_red: bool | None = Field(default=None, description="是否 MACD 红柱（柱>0）")
    ma_cross: bool | None = Field(default=None, description="是否 MA5 上穿 MA10（相对上一根同周期 K）")
    macd_cross: bool | None = Field(default=None, description="是否 MACD 金叉 DIF 上穿 DEA")
    timeframe: ScreeningTimeframe | None = Field(default=None, description="日/周/月 K，默认 daily")
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
    ma5: Decimal | None = None
    ma10: Decimal | None = None
    ma20: Decimal | None = None
    ma60: Decimal | None = None
    macd_dif: Decimal | None = None
    macd_dea: Decimal | None = None
    macd_hist: Decimal | None = None
    volume: Decimal | None = None
    amount: Decimal | None = None
    amplitude: Decimal | None = None
    turnover_rate: Decimal | None = None
    pe: Decimal | None = None
    pe_ttm: Decimal | None = None
    pb: Decimal | None = None
    dv_ratio: Decimal | None = None
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
    timeframe: ScreeningTimeframe = "daily"
    data_date: dt_date | None = None


class LatestDateResponse(BaseModel):
    """最新数据日期。"""
    date: dt_date | None = None
    timeframe: ScreeningTimeframe = "daily"
