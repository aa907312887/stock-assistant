"""回测任务表 backtest_task。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Index, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BacktestTask(Base):
    __tablename__ = "backtest_task"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="running")

    total_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    win_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lose_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    win_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    total_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    avg_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    max_win: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    max_loss: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    unclosed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    assumptions_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    strategy_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_backtest_task_strategy", "strategy_id", "created_at"),
        Index("idx_backtest_task_status", "status"),
    )
