"""大盘温度任务服务：增量/区间重算。"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.market_temperature_daily import MarketTemperatureDaily
from app.services.market_temperature.constants import FORMULA_VERSION
from app.services.market_temperature.formula_engine import calculate_scores_for_dates, map_level
from app.services.market_temperature.index_quote_service import sync_index_quotes
from app.services.market_temperature.rule_service import ensure_default_rules, get_strategy_hint_by_level
from app.services.market_temperature.temperature_repository import fetch_quotes_by_code, upsert_temperature
from app.services.tushare_client import get_latest_open_trade_date

logger = logging.getLogger(__name__)


def rebuild_temperature_range(
    db: Session,
    start_date: date,
    end_date: date,
    formula_version: str = FORMULA_VERSION,
    force_refresh_source: bool = False,
) -> dict:
    if force_refresh_source:
        sync_rows = sync_index_quotes(db, start_date, end_date)
        logger.info("强制刷新指数行情完成 rows=%s", sync_rows)
    ensure_default_rules(db)
    quotes_by_code = fetch_quotes_by_code(db, start_date, end_date)
    if not quotes_by_code:
        return {"rows_updated": 0}
    score_map = calculate_scores_for_dates(quotes_by_code)
    rows = 0
    for td, data in score_map.items():
        level = map_level(data["temperature_score"])  # type: ignore[arg-type]
        hint = get_strategy_hint_by_level(db, level)
        upsert_temperature(
            db,
            trade_date=td,
            temperature_score=data["temperature_score"],  # type: ignore[arg-type]
            temperature_level=level,
            trend_flag=str(data["trend_flag"]),
            delta_score=data["delta_score"],  # type: ignore[arg-type]
            strategy_hint=hint,
            trend_score=data["trend_score"],  # type: ignore[arg-type]
            liquidity_score=data["liquidity_score"],  # type: ignore[arg-type]
            risk_score=data["risk_score"],  # type: ignore[arg-type]
            formula_version=formula_version,
        )
        rows += 1
    db.commit()
    return {"rows_updated": rows}


def run_incremental_temperature_job(db: Session, formula_version: str = FORMULA_VERSION) -> dict:
    today = date.today()
    latest_trade_date = get_latest_open_trade_date(today)
    if latest_trade_date is None:
        return {"rows_updated": 0, "reason": "无交易日"}
    last = (
        db.query(MarketTemperatureDaily)
        .filter(MarketTemperatureDaily.formula_version == formula_version)
        .order_by(MarketTemperatureDaily.trade_date.desc())
        .first()
    )
    end_date = latest_trade_date
    if last:
        start_date = max(last.trade_date - timedelta(days=120), end_date - timedelta(days=200))
    else:
        start_date = end_date - timedelta(days=365 * 4)

    sync_index_quotes(db, start_date, end_date)
    return rebuild_temperature_range(db, start_date, end_date, formula_version=formula_version)
