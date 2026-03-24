"""同步任务 API 模型。"""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class TriggerSyncRequest(BaseModel):
    mode: Literal["incremental", "backfill"] = "incremental"
    modules: list[str] | None = None
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_backfill_dates(self) -> "TriggerSyncRequest":
        if self.mode == "backfill" and (self.start_date is None or self.end_date is None):
            raise ValueError("backfill 模式必须提供 start_date 和 end_date")
        return self


class RetryTradeDateSyncRequest(BaseModel):
    """补偿重试：按指定交易日触发一次增量同步。"""

    trade_date: date
    modules: list[str] | None = None


class TriggerSyncResponse(BaseModel):
    status: str = "started"
    batch_id: str
    mode: str
    message: str


class SyncJobItem(BaseModel):
    batch_id: str
    job_name: str
    job_mode: str
    status: str
    trade_date: date | None = None
    started_at: datetime
    finished_at: datetime | None = None
    basic_rows: int = 0
    daily_rows: int = 0
    weekly_rows: int = 0
    monthly_rows: int = 0
    report_rows: int = 0
    failed_stock_count: int = 0
    error_message: str | None = None


class SyncJobListResponse(BaseModel):
    items: list[SyncJobItem]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class SyncJobDetailResponse(SyncJobItem):
    stock_total: int | None = None
    extra_json: dict[str, Any] | None = None


class SyncTaskItem(BaseModel):
    """子任务状态表一行。"""

    id: int
    trade_date: date
    task_type: str
    trigger_type: str
    status: str
    batch_id: str | None = None
    rows_affected: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class SyncTaskListResponse(BaseModel):
    items: list[SyncTaskItem]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
