"""股票日估值表 stock_valuation_daily。"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StockValuationDaily(Base):
    __tablename__ = "stock_valuation_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    pe_ttm: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    pe_static: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    pe_dynamic: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    pe: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    pb: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ps: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    roe: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    gross_margin: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    net_margin: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    data_source: Mapped[str] = mapped_column(String(32), nullable=False, server_default="tushare")
    sync_batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("stock_code", "trade_date", name="uk_stock_trade"),
    )
