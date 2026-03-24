"""大盘温度文案配置表 market_temperature_copywriting。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MarketTemperatureCopywriting(Base):
    __tablename__ = "market_temperature_copywriting"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    level_name: Mapped[str | None] = mapped_column(String(16), nullable=True)
    title: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    formula_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[int] = mapped_column(nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
