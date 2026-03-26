"""策略执行快照表 strategy_execution_snapshot。"""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StrategyExecutionSnapshot(Base):
    __tablename__ = "strategy_execution_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)

    market: Mapped[str] = mapped_column(String(16), nullable=False, server_default="A股")
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False, server_default="daily")

    params_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    assumptions_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    data_source: Mapped[str] = mapped_column(String(32), nullable=False, server_default="tushare")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

