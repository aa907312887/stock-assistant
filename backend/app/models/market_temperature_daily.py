"""大盘温度日结果表 market_temperature_daily。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MarketTemperatureDaily(Base):
    __tablename__ = "market_temperature_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    temperature_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    temperature_level: Mapped[str] = mapped_column(String(16), nullable=False)
    trend_flag: Mapped[str] = mapped_column(String(8), nullable=False)
    delta_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    strategy_hint: Mapped[str] = mapped_column(String(255), nullable=False)
    data_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="normal")
    formula_version: Mapped[str] = mapped_column(String(32), nullable=False, server_default="v1.0.0")
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("trade_date", "formula_version", name="uk_temp_trade_date_version"),
    )
