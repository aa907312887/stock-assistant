"""大盘温度分级规则表 market_temperature_level_rule。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MarketTemperatureLevelRule(Base):
    __tablename__ = "market_temperature_level_rule"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    level_name: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    score_min: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    score_max: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    strategy_action: Mapped[str] = mapped_column(String(32), nullable=False)
    strategy_hint: Mapped[str] = mapped_column(String(255), nullable=False)
    visual_token: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[int] = mapped_column(nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
