"""指数行情拉取与入库服务。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from app.models.market_index_daily_quote import MarketIndexDailyQuote
from app.services.market_temperature.constants import INDEX_CODES
from app.services.tushare_client import get_index_daily_range


def _to_decimal(v: Any) -> Decimal | None:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def sync_index_quotes(db: Session, start_date: date, end_date: date) -> int:
    """拉取四指数区间日线并 upsert 到本地。"""
    rows_affected = 0
    for code in INDEX_CODES:
        rows = get_index_daily_range(code, start_date=start_date, end_date=end_date)
        for r in rows:
            td = str(r.get("trade_date") or "")
            if len(td) != 8:
                continue
            trade_date = date(int(td[:4]), int(td[4:6]), int(td[6:8]))
            stmt = mysql_insert(MarketIndexDailyQuote).values(
                index_code=code,
                trade_date=trade_date,
                open=_to_decimal(r.get("open")),
                high=_to_decimal(r.get("high")),
                low=_to_decimal(r.get("low")),
                close=_to_decimal(r.get("close")),
                vol=_to_decimal(r.get("vol")),
                amount=_to_decimal(r.get("amount")),
                source="tushare",
            )
            stmt = stmt.on_duplicate_key_update(
                open=stmt.inserted.open,
                high=stmt.inserted.high,
                low=stmt.inserted.low,
                close=stmt.inserted.close,
                vol=stmt.inserted.vol,
                amount=stmt.inserted.amount,
                source=stmt.inserted.source,
            )
            db.execute(stmt)
            rows_affected += 1
    db.commit()
    return rows_affected
