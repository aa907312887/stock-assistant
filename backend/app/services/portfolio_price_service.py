"""参考价：取 stock_daily_bar 最新收盘价。"""

from datetime import date
from decimal import Decimal

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.stock_daily_bar import StockDailyBar


def get_latest_close(
    db: Session, stock_code: str
) -> tuple[Decimal | None, date | None]:
    """返回 (close, trade_date)；无数据时 (None, None)。"""
    row = (
        db.query(StockDailyBar)
        .filter(StockDailyBar.stock_code == stock_code)
        .filter(StockDailyBar.close.isnot(None))
        .order_by(desc(StockDailyBar.trade_date))
        .first()
    )
    if not row:
        return None, None
    return row.close, row.trade_date
