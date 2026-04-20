"""指数月线 index_monthly_bar。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IndexMonthlyBar(Base):
    __tablename__ = "index_monthly_bar"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    index_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    trade_month_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    open: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    close: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ma5: Mapped[Decimal | None] = mapped_column(Numeric(16, 8), nullable=True)
    ma10: Mapped[Decimal | None] = mapped_column(Numeric(16, 8), nullable=True)
    ma20: Mapped[Decimal | None] = mapped_column(Numeric(16, 8), nullable=True)
    ma60: Mapped[Decimal | None] = mapped_column(Numeric(16, 8), nullable=True)
    macd_dif: Mapped[Decimal | None] = mapped_column(Numeric(16, 8), nullable=True)
    macd_dea: Mapped[Decimal | None] = mapped_column(Numeric(16, 8), nullable=True)
    macd_hist: Mapped[Decimal | None] = mapped_column(Numeric(16, 8), nullable=True)
    change_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    pct_change: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    data_source: Mapped[str] = mapped_column(String(32), nullable=False, server_default="tushare")
    sync_batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("index_code", "trade_month_end", name="uk_index_monthly_code_date"),
    )
