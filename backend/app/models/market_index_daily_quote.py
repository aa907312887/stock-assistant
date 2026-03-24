"""指数日线行情表 market_index_daily_quote。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MarketIndexDailyQuote(Base):
    __tablename__ = "market_index_daily_quote"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    index_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    open: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    close: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    vol: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, server_default="tushare")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("index_code", "trade_date", name="uk_market_index_date"),
    )
