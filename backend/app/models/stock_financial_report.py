"""股票财报历史表 stock_financial_report。"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StockFinancialReport(Base):
    __tablename__ = "stock_financial_report"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    report_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    net_profit: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    eps: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    bps: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
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
        UniqueConstraint("stock_code", "report_date", name="uk_stock_report"),
    )
