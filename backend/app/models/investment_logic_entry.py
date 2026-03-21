"""投资逻辑条目表 investment_logic_entry，与 specs/004-首页投资逻辑/data-model.md 一致。"""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InvestmentLogicEntry(Base):
    __tablename__ = "investment_logic_entry"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    technical_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    fundamental_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight_technical: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_fundamental: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_message: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    extra_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
