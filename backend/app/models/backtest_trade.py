"""回测交易明细表 backtest_trade。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Index, JSON, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BacktestTrade(Base):
    __tablename__ = "backtest_trade"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    buy_date: Mapped[date] = mapped_column(Date, nullable=False)
    trigger_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    buy_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    sell_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sell_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    return_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    trade_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="closed")
    exchange: Mapped[str | None] = mapped_column(String(10), nullable=True)
    market: Mapped[str | None] = mapped_column(String(20), nullable=True)
    market_temp_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    market_temp_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    extra_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 用户对「该笔策略决策是否合适」的主观评价（用于人工正确率统计）
    user_decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    user_decision_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    user_decision_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_bt_trade_task_id", "task_id"),
        Index("idx_bt_trade_stock", "stock_code", "buy_date"),
        Index("idx_bt_trade_type", "task_id", "trade_type"),
        Index("idx_bt_trade_exchange", "task_id", "exchange"),
        Index("idx_bt_trade_market", "task_id", "market"),
        Index("idx_bt_trade_temp", "task_id", "market_temp_level"),
    )
