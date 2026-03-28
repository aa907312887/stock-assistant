"""大盘温度查询接口。"""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, SessionLocal
from app.services.market_temperature.constants import FORMULA_VERSION
from app.services.market_temperature.rule_service import get_formula_explain, get_level_rules
from app.services.market_temperature.temperature_job_service import rebuild_temperature_range
from app.services.market_temperature.temperature_repository import (
    latest_temperature,
    list_by_date_range,
    list_trend,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market-temperature", tags=["大盘温度"])


@router.get("/latest")
def get_latest(db: Session = Depends(get_db)):
    row = latest_temperature(db)
    if not row:
        raise HTTPException(status_code=404, detail="暂无大盘温度数据")
    level_styles = [
        {"level_name": x.level_name, "visual_token": x.visual_token, "short_desc": x.strategy_action}
        for x in get_level_rules(db)
    ]
    return {
        "trade_date": row.trade_date,
        "temperature_score": float(row.temperature_score),
        "temperature_level": row.temperature_level,
        "trend_flag": row.trend_flag,
        "strategy_hint": row.strategy_hint,
        "updated_at": row.generated_at,
        "data_status": row.data_status,
        "level_styles": level_styles,
    }


@router.get("/trend")
def get_trend(days: int = Query(20, ge=5, le=120), db: Session = Depends(get_db)):
    rows = list_trend(db, days=days)
    return {
        "formula_version": FORMULA_VERSION,
        "points": [
            {
                "trade_date": x.trade_date,
                "temperature_score": float(x.temperature_score),
                "temperature_level": x.temperature_level,
                "trend_flag": x.trend_flag,
            }
            for x in rows
        ],
    }


@router.get("/range")
def get_range(
    start_date: date = Query(..., description="区间起始日（含）"),
    end_date: date = Query(..., description="区间结束日（含）"),
    db: Session = Depends(get_db),
):
    """按自然日区间查询该范围内所有交易日的大盘温度（用于历史回看）。"""
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date 不能晚于 end_date")
    max_days = 365 * 3
    if (end_date - start_date).days > max_days:
        raise HTTPException(status_code=422, detail=f"日期区间最长 {max_days} 个自然日")

    rows = list_by_date_range(db, start_date=start_date, end_date=end_date)
    if not rows:
        raise HTTPException(status_code=404, detail="该区间内暂无大盘温度数据")

    level_styles = [
        {"level_name": x.level_name, "visual_token": x.visual_token, "short_desc": x.strategy_action}
        for x in get_level_rules(db)
    ]
    last = rows[-1]
    return {
        "formula_version": FORMULA_VERSION,
        "start_date": rows[0].trade_date,
        "end_date": last.trade_date,
        "trade_day_count": len(rows),
        "level_styles": level_styles,
        "snapshot": {
            "trade_date": last.trade_date,
            "temperature_score": float(last.temperature_score),
            "temperature_level": last.temperature_level,
            "trend_flag": last.trend_flag,
            "strategy_hint": last.strategy_hint,
            "updated_at": last.generated_at,
            "data_status": last.data_status,
        },
        "points": [
            {
                "trade_date": x.trade_date,
                "temperature_score": float(x.temperature_score),
                "temperature_level": x.temperature_level,
                "trend_flag": x.trend_flag,
            }
            for x in rows
        ],
    }


@router.get("/explain")
def get_explain(version: str | None = Query(None), db: Session = Depends(get_db)):
    return get_formula_explain(db, version)


def _check_admin(x_admin_secret: str | None = None) -> None:
    secret = (settings.admin_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="未配置 ADMIN_SECRET")
    if (x_admin_secret or "").strip() != secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="鉴权失败")


@router.post("/rebuild")
def rebuild(
    payload: dict = Body(...),
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
):
    _check_admin(x_admin_secret)
    try:
        start_date = date.fromisoformat(payload["start_date"])
        end_date = date.fromisoformat(payload["end_date"])
    except Exception as e:
        raise HTTPException(status_code=422, detail="start_date/end_date 格式应为 YYYY-MM-DD") from e
    formula_version = payload.get("formula_version") or FORMULA_VERSION
    force_refresh_source = bool(payload.get("force_refresh_source", False))
    task_id = f"mt-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    def _runner() -> None:
        db = SessionLocal()
        try:
            rebuild_temperature_range(
                db,
                start_date=start_date,
                end_date=end_date,
                formula_version=formula_version,
                force_refresh_source=force_refresh_source,
            )
        except Exception:
            logger.exception("手动重算失败 task_id=%s", task_id)
        finally:
            db.close()

    threading.Thread(target=_runner, daemon=True).start()
    return JSONResponse(status_code=202, content={"task_id": task_id, "status": "accepted", "message": "已受理"})
