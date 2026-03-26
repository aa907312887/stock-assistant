"""策略信号事件表 strategy_signal_event。"""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StrategySignalEvent(Base):
    __tablename__ = "strategy_signal_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    event_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

