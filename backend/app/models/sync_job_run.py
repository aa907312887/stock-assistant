"""同步任务运行日志表 sync_job_run。"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SyncJobRun(Base):
    __tablename__ = "sync_job_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    job_mode: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    trade_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    stock_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    basic_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    daily_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    weekly_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    monthly_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    report_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    failed_stock_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
