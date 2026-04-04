"""基本面分析请求与响应 Schema。"""

from datetime import date as dt_date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class FundamentalQueryParams(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")
    code: str | None = Field(default=None, description="股票代码模糊匹配")
    name: str | None = Field(default=None, description="股票名称模糊匹配")
    min_roe: float | None = Field(default=None, description="ROE 最小值")
    max_roe: float | None = Field(default=None, description="ROE 最大值")
    min_debt_to_assets: float | None = Field(default=None, description="资产负债率最小值")
    max_debt_to_assets: float | None = Field(default=None, description="资产负债率最大值")
    sort_by: str | None = Field(default=None, description="排序字段")
    sort_order: Literal["asc", "desc"] = Field(default="desc", description="排序方向")


class FundamentalItem(BaseModel):
    code: str
    name: str | None = None
    exchange: str | None = None
    market: str | None = None
    report_date: dt_date | None = None
    ann_date: dt_date | None = None
    revenue: Decimal | None = None
    net_profit: Decimal | None = None
    eps: Decimal | None = None
    bps: Decimal | None = None
    roe: Decimal | None = None
    roe_dt: Decimal | None = None
    roe_waa: Decimal | None = None
    roa: Decimal | None = None
    gross_margin: Decimal | None = None
    net_margin: Decimal | None = None
    debt_to_assets: Decimal | None = None
    current_ratio: Decimal | None = None
    quick_ratio: Decimal | None = None
    cfps: Decimal | None = None
    ebit: Decimal | None = None
    ocf_to_profit: Decimal | None = None

    model_config = {"from_attributes": True}


class FundamentalResponse(BaseModel):
    items: list[FundamentalItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
