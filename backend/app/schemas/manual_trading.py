"""手动模拟交易 Pydantic 模型。"""

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    asset_name: str = Field(..., min_length=1, max_length=100)
    start_date: date
    name: Optional[str] = Field(default=None, max_length=100)


class BuyRequest(BaseModel):
    amount: float = Field(..., gt=0)
    price: float = Field(..., gt=0)


class AdvanceRequest(BaseModel):
    step: Literal["day", "week", "month", "year"]


class RevalRequest(BaseModel):
    close_price: float = Field(..., gt=0)


class SessionListItem(BaseModel):
    session_id: str
    name: Optional[str]
    asset_name: str
    start_date: date
    current_date: date
    position_value: float
    total_invested: float
    total_pnl: float
    status: str
    awaiting_reval: bool
    created_at: datetime


class SessionListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SessionListItem]


class SessionDetailResponse(BaseModel):
    session_id: str
    name: Optional[str]
    asset_name: str
    start_date: date
    current_date: date
    reference_price: Optional[float]
    position_value: float
    total_invested: float
    total_pnl: float
    total_pnl_pct: Optional[float]
    total_trading_days: Optional[int]
    status: str
    awaiting_reval: bool
    end_date: Optional[date]
    first_operation_date: Optional[date]
    created_at: datetime
    updated_at: datetime


class AdvanceResponse(BaseModel):
    session_id: str
    current_date: date
    awaiting_reval: bool
    step: str


class OperationItem(BaseModel):
    id: int
    op_type: str
    op_type_label: str
    op_date: date
    price: Optional[float]
    buy_amount: Optional[float]
    advance_step: Optional[str]
    position_before: float
    position_after: float
    segment_pnl: Optional[float]
    days_since_prev: Optional[int]


class OperationsResponse(BaseModel):
    session_id: str
    total_pnl: float
    total_trading_days: Optional[int]
    items: list[OperationItem]
