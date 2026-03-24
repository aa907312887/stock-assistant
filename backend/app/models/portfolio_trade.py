"""用户持仓交易（一笔：建仓至清仓）。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PortfolioTrade(Base):
    __tablename__ = "portfolio_trade"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="open")
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    avg_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    total_qty: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    total_cost_basis: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    accumulated_realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), nullable=False, server_default="0"
    )
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    review_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
