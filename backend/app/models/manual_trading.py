"""手动模拟交易数据模型。

比例跟盘验算：用户手填价格，持仓名义金额随收盘价同比变化，不折算股数。
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ManualTradingSession(Base):
    """手动模拟交易会話。"""

    __tablename__ = "manual_trading_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    asset_name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference_price: Mapped[Decimal | None] = mapped_column(Numeric(16, 4), nullable=True)
    position_value: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default="0")
    total_invested: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default="0")
    awaiting_reval: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    last_advance_step: Mapped[str | None] = mapped_column(String(10), nullable=True)
    first_operation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("idx_mts_user_status", "user_id", "status", "created_at"),)


class ManualTradingOperation(Base):
    """手动模拟交易操作流水。"""

    __tablename__ = "manual_trading_operation"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    op_type: Mapped[str] = mapped_column(String(20), nullable=False)
    op_date: Mapped[date] = mapped_column(Date, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(16, 4), nullable=True)
    buy_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    advance_step: Mapped[str | None] = mapped_column(String(10), nullable=True)
    position_before: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    position_after: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    segment_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_mto_session_date", "session_id", "op_date", "id"),)
