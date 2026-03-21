"""股票日行情表 stock_daily_quote，与 docs/数据库设计.md 3.6 一致。"""
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StockDailyQuote(Base):
    __tablename__ = "stock_daily_quote"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    open: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    close: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    prev_close: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    change_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    pct_change: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    amplitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    turnover_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    volume_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    internal_volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    external_volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    bid_volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    ask_volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    bid_ask_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    total_market_cap: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    float_market_cap: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    data_source: Mapped[str] = mapped_column(String(32), nullable=False, server_default="tushare")
    sync_batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("stock_code", "trade_date", name="uk_stock_date"),
    )
