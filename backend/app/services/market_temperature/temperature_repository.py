"""大盘温度数据访问。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from app.models.market_index_daily_quote import MarketIndexDailyQuote
from app.models.market_temperature_daily import MarketTemperatureDaily
from app.models.market_temperature_factor_daily import MarketTemperatureFactorDaily
from app.services.market_temperature.constants import FORMULA_VERSION


def fetch_quotes_by_code(db: Session, start_date: date, end_date: date) -> dict[str, list[dict]]:
    rows = (
        db.query(MarketIndexDailyQuote)
        .filter(MarketIndexDailyQuote.trade_date >= start_date, MarketIndexDailyQuote.trade_date <= end_date)
        .order_by(MarketIndexDailyQuote.trade_date.asc())
        .all()
    )
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        grouped.setdefault(r.index_code, []).append(
            {
                "trade_date": r.trade_date,
                "open": float(r.open or 0),
                "high": float(r.high or 0),
                "low": float(r.low or 0),
                "close": float(r.close or 0),
                "vol": float(r.vol or 0),
                "amount": float(r.amount or 0),
            }
        )
    return grouped


def upsert_temperature(
    db: Session,
    trade_date: date,
    temperature_score: Decimal,
    temperature_level: str,
    trend_flag: str,
    delta_score: Decimal,
    strategy_hint: str,
    trend_score: Decimal,
    liquidity_score: Decimal,
    risk_score: Decimal,
    formula_version: str = FORMULA_VERSION,
) -> None:
    stmt = mysql_insert(MarketTemperatureDaily).values(
        trade_date=trade_date,
        temperature_score=temperature_score,
        temperature_level=temperature_level,
        trend_flag=trend_flag,
        delta_score=delta_score,
        strategy_hint=strategy_hint,
        data_status="normal",
        formula_version=formula_version,
        generated_at=datetime.now(),
    )
    stmt = stmt.on_duplicate_key_update(
        temperature_score=stmt.inserted.temperature_score,
        temperature_level=stmt.inserted.temperature_level,
        trend_flag=stmt.inserted.trend_flag,
        delta_score=stmt.inserted.delta_score,
        strategy_hint=stmt.inserted.strategy_hint,
        data_status="normal",
        generated_at=stmt.inserted.generated_at,
    )
    db.execute(stmt)

    stmt2 = mysql_insert(MarketTemperatureFactorDaily).values(
        trade_date=trade_date,
        trend_score=trend_score,
        liquidity_score=liquidity_score,
        risk_score=risk_score,
        trend_weight=Decimal("0.40"),
        liquidity_weight=Decimal("0.30"),
        risk_weight=Decimal("0.30"),
        formula_version=formula_version,
        generated_at=datetime.now(),
    )
    stmt2 = stmt2.on_duplicate_key_update(
        trend_score=stmt2.inserted.trend_score,
        liquidity_score=stmt2.inserted.liquidity_score,
        risk_score=stmt2.inserted.risk_score,
        generated_at=stmt2.inserted.generated_at,
    )
    db.execute(stmt2)


def latest_temperature(db: Session, formula_version: str = FORMULA_VERSION) -> MarketTemperatureDaily | None:
    return (
        db.query(MarketTemperatureDaily)
        .filter(MarketTemperatureDaily.formula_version == formula_version)
        .order_by(MarketTemperatureDaily.trade_date.desc())
        .first()
    )


def list_trend(db: Session, days: int = 20, formula_version: str = FORMULA_VERSION) -> list[MarketTemperatureDaily]:
    rows = (
        db.query(MarketTemperatureDaily)
        .filter(MarketTemperatureDaily.formula_version == formula_version)
        .order_by(MarketTemperatureDaily.trade_date.desc())
        .limit(days)
        .all()
    )
    return list(reversed(rows))
