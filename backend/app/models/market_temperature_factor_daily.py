"""大盘温度因子分项表 market_temperature_factor_daily。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MarketTemperatureFactorDaily(Base):
    __tablename__ = "market_temperature_factor_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    trend_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    liquidity_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    trend_weight: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, server_default="0.40")
    liquidity_weight: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, server_default="0.30")
    risk_weight: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, server_default="0.30")
    formula_version: Mapped[str] = mapped_column(String(32), nullable=False, server_default="v1.0.0")
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("trade_date", "formula_version", name="uk_factor_trade_date_version"),
    )
