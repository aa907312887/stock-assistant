"""交易下的操作记录（建仓/加仓/减仓/清仓）。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PortfolioOperation(Base):
    __tablename__ = "portfolio_operation"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    op_type: Mapped[str] = mapped_column(String(16), nullable=False)
    op_date: Mapped[date] = mapped_column(Date, nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True, server_default="0")
    operation_rating: Mapped[str | None] = mapped_column(String(8), nullable=True)
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
