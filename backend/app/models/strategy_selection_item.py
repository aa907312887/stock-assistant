"""策略选股候选明细表 strategy_selection_item。"""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StrategySelectionItem(Base):
    __tablename__ = "strategy_selection_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    trigger_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("execution_id", "stock_code", name="uk_strategy_sel_execution_stock"),
    )

