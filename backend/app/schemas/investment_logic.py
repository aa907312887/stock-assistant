"""投资逻辑 API 模型。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InvestmentLogicEntryOut(BaseModel):
    """单条条目响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    technical_content: str | None = None
    fundamental_content: str | None = None
    message_content: str | None = None
    weight_technical: int
    weight_fundamental: int
    weight_message: int
    created_at: datetime
    updated_at: datetime
    extra_json: dict[str, Any] | None = None


class InvestmentLogicCreateIn(BaseModel):
    """POST 新增。"""

    technical_content: str | None = None
    fundamental_content: str | None = None
    message_content: str | None = None
    weight_technical: int = Field(..., ge=0, le=100)
    weight_fundamental: int = Field(..., ge=0, le=100)
    weight_message: int = Field(..., ge=0, le=100)
    extra_json: dict[str, Any] | None = None


class InvestmentLogicCurrentOut(BaseModel):
    entry: InvestmentLogicEntryOut | None = None


class InvestmentLogicListOut(BaseModel):
    items: list[InvestmentLogicEntryOut]
