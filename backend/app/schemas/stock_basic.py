"""股票基本信息 API 模型。"""
from datetime import date, datetime

from pydantic import BaseModel, Field


class StockBasicItem(BaseModel):
    code: str
    name: str | None = None
    exchange: str | None = None
    market: str | None = None
    industry_name: str | None = None
    region: str | None = None
    list_date: date | None = None
    synced_at: datetime | None = None
    data_source: str | None = None

    model_config = {"from_attributes": True}


class StockBasicListResponse(BaseModel):
    items: list[StockBasicItem]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    last_synced_at: datetime | None = None


class StockBasicSyncResponse(BaseModel):
    """同步完成后返回（请求内同步执行）。"""
    status: str = "ok"
    message: str = "股票基本信息同步完成"
    stock_basic: int = 0
