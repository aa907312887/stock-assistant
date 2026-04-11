"""历史模拟交易相关数据模型。

包含三张表：
- PaperTradingSession：模拟交易会话（含当前日期和时间节点 phase）
- PaperTradingPosition：持仓批次（每次买入一条，支持 FIFO 卖出和 T+1 判断）
- PaperTradingOrder：交易记录（每笔买卖操作的完整流水）
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PaperTradingSession(Base):
    """模拟交易会话表。

    一次交互式历史模拟交易游戏的主记录，保存起始配置、当前进度和账户状态。
    current_phase 标识当前所处时间节点：open（开盘）/ close（收盘）。
    """

    __tablename__ = "paper_trading_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_date: Mapped[date] = mapped_column(Date, nullable=False)
    # 当前时间节点：open（开盘，仅知道开盘价）/ close（收盘，完整 K 线可见）
    current_phase: Mapped[str] = mapped_column(String(10), nullable=False, server_default="open")
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    available_cash: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    # 会话状态：active（进行中）/ ended（已结束）
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_pts_status", "status", "created_at"),
    )


class PaperTradingPosition(Base):
    """持仓批次表。

    每次买入操作产生一条独立记录，支持：
    - FIFO 卖出：按 buy_date ASC, id ASC 排序扣减
    - T+1 判断：buy_date == current_date 的批次当日不可卖出
    - 加权均价展示：前端按 stock_code 聚合计算
    """

    __tablename__ = "paper_trading_position"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    buy_date: Mapped[date] = mapped_column(Date, nullable=False)
    buy_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    commission: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    # 批次状态：holding（持有中）/ closed（已全部卖出）
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="holding")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_ptp_session_stock", "session_id", "stock_code", "buy_date"),
        Index("idx_ptp_session_status", "session_id", "status"),
    )


class PaperTradingOrder(Base):
    """交易记录表。

    每笔买入或卖出操作的完整流水，用于交易历史查询和账户资金核对。
    卖出时 position_id 指向被扣减的最早持仓批次（FIFO 第一批）。
    """

    __tablename__ = "paper_trading_order"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # 交易类型：buy（买入）/ sell（卖出）
    order_type: Mapped[str] = mapped_column(String(10), nullable=False)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    commission: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    cash_after: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    # 卖出时关联被扣减的最早持仓批次 ID，买入时为 NULL
    position_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_pto_session", "session_id", "trade_date"),
        Index("idx_pto_session_stock", "session_id", "stock_code"),
    )
