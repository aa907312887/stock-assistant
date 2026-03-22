"""管理端技术指标回填请求/响应。"""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TriggerStockIndicatorsRequest(BaseModel):
    mode: str = Field(..., description="incremental、backfill 或 full（全表每标的全部 K 线）")
    timeframes: list[str] | None = Field(
        default=None,
        description="默认 daily, weekly, monthly",
    )
    trade_date: date | None = Field(
        default=None,
        description="incremental 时锚定「截至该日」的 K 线；默认当日（由服务端取最近交易日）",
    )
    start_date: date | None = None
    end_date: date | None = None
    limit: int | None = Field(default=None, ge=1)

    @field_validator("mode")
    @classmethod
    def _mode_ok(cls, v: str) -> str:
        if v not in ("incremental", "backfill", "full"):
            raise ValueError("mode 必须为 incremental、backfill 或 full")
        return v


class TriggerStockIndicatorsResponse(BaseModel):
    batch_id: str
    status: str
    rows_updated: dict[str, Any] | None = None
    error_message: str | None = None
