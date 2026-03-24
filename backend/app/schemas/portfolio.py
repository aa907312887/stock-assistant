"""个人持仓 API 请求/响应模式。"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class TradeOpenBody(BaseModel):
    stock_code: str = Field(..., min_length=1, max_length=20)
    op_date: date
    qty: Decimal = Field(..., gt=0)
    price: Decimal = Field(..., gt=0)
    fee: Decimal | None = Field(default=None, ge=0)


class OperationBody(BaseModel):
    op_type: Literal["add", "reduce"]
    op_date: date
    qty: Decimal = Field(..., gt=0)
    price: Decimal = Field(..., gt=0)
    fee: Decimal | None = Field(default=None, ge=0)
    operation_rating: Literal["good", "bad"] | None = None
    note: str | None = None


class CloseBody(BaseModel):
    op_date: date
    qty: Decimal = Field(..., gt=0)
    price: Decimal = Field(..., gt=0)
    fee: Decimal | None = Field(default=None, ge=0)
    operation_rating: Literal["good", "bad"] | None = None
    note: str | None = None


class ReviewPatchBody(BaseModel):
    review_text: str | None = None


class OperationRatingBody(BaseModel):
    operation_rating: Literal["good", "bad"] | None = None


class OpenTradeResponse(BaseModel):
    trade_id: int
    operation_id: int


class OperationCreateResponse(BaseModel):
    operation_id: int


class CloseTradeResponse(BaseModel):
    trade_id: int
    realized_pnl: Decimal | None


class OpenTradeItem(BaseModel):
    trade_id: int
    stock_code: str
    stock_name: str | None
    total_qty: Decimal | None
    avg_cost: Decimal | None
    ref_close: Decimal | None = None
    ref_close_date: date | None = None
    ref_market_value: Decimal | None = None
    ref_pnl: Decimal | None = None
    ref_pnl_pct: Decimal | None = None
    has_ref_price: bool = False


class OpenTradesResponse(BaseModel):
    items: list[OpenTradeItem]


class ClosedTradeItem(BaseModel):
    trade_id: int
    stock_code: str
    stock_name: str | None
    closed_at: datetime | None
    realized_pnl: Decimal | None
    realized_pnl_rate: Decimal | None = None
    review_text: str | None
    image_count: int = 0


class ClosedTradesResponse(BaseModel):
    total: int
    items: list[ClosedTradeItem]


class TradeOut(BaseModel):
    id: int
    stock_code: str
    stock_name: str | None = None
    status: str
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    avg_cost: Decimal | None = None
    total_qty: Decimal | None = None
    realized_pnl: Decimal | None = None
    realized_pnl_rate: Decimal | None = None
    review_text: str | None = None


class OperationOut(BaseModel):
    id: int
    op_type: str
    op_date: date
    qty: Decimal
    price: Decimal
    operation_rating: str | None = None
    note: str | None = None


class TradeImageOut(BaseModel):
    id: int
    url: str


class TradeDetailResponse(BaseModel):
    trade: TradeOut
    operations: list[OperationOut]
    images: list[TradeImageOut] = []


class ImageUploadResponse(BaseModel):
    image_id: int
    url: str


class StockWinRate(BaseModel):
    won: int
    lost: int
    breakeven: int
    total: int
    rate: float | None


class OperationWinRate(BaseModel):
    good: int
    bad: int
    unrated: int
    rated_total: int
    rate: float | None


class OverallPnlSummary(BaseModel):
    total_profit: Decimal
    total_loss: Decimal
    net_pnl: Decimal
    net_pnl_rate: float | None


class StatsResponse(BaseModel):
    stock_win_rate: StockWinRate
    operation_win_rate: OperationWinRate
    overall_pnl: OverallPnlSummary
