"""兼容层：旧同步入口委托到新的同步编排服务。"""

from datetime import date

from sqlalchemy.orm import Session

from app.services.stock_sync_orchestrator import run_stock_sync


def run_sync(db: Session, trade_date: date | None = None, limit: int | None = None) -> dict[str, int]:
    result = run_stock_sync(
        db,
        mode="incremental",
        requested_trade_date=trade_date,
        limit=limit,
    )
    return {
        "stock_basic": int(result.get("basic_rows", 0)),
        "stock_daily_bar": int(result.get("daily_rows", 0)),
        "stock_financial_report": int(result.get("report_rows", 0)),
    }
