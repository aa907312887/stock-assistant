"""指数基金专题 API：列表、最新日期、成分与指数 PE 推理。"""
import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user
from app.database import get_db
from app.models import User
from app.schemas.index import CompositionResponse, IndexScreeningResponse
from app.schemas.stock import LatestDateResponse
from app.services.index_pe_percentile_service import infer_index_pe_percentile_bundle, suggest_snapshot_trade_date
from app.services.index_screening_service import get_latest_snapshot_date, list_index_screening

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/index", tags=["指数基金"])

ScreeningTimeframe = Literal["daily", "weekly", "monthly"]


@router.get("/screening", response_model=IndexScreeningResponse)
def get_index_screening(
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: str | None = Query(None, description="指数 ts_code 模糊"),
    name: str | None = Query(None, description="指数名称模糊"),
    ma_bull: bool | None = Query(None, description="均线多头排列"),
    macd_red: bool | None = Query(None, description="MACD 红柱"),
    ma_cross: bool | None = Query(None, description="MA5 上穿 MA10"),
    macd_cross: bool | None = Query(None, description="MACD 金叉"),
    timeframe: ScreeningTimeframe = Query("daily"),
    data_date: date | None = Query(None),
    db=Depends(get_db),
):
    """指数基金列表（分页）。需登录。"""
    try:
        items, total, data_date_res = list_index_screening(
            db,
            page=page,
            page_size=page_size,
            timeframe=timeframe,
            code=code,
            name=name,
            ma_bull=ma_bull,
            macd_red=macd_red,
            ma_cross=ma_cross,
            macd_cross=macd_cross,
            data_date=data_date,
        )
        return IndexScreeningResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            timeframe=timeframe,
            data_date=data_date_res,
        )
    except Exception as e:
        logger.exception("指数基金列表失败: %s", e)
        raise


@router.get("/screening/latest-date", response_model=LatestDateResponse)
def get_index_screening_latest_date(
    current_user: User = Depends(get_current_user),
    timeframe: ScreeningTimeframe = Query("daily"),
    db=Depends(get_db),
):
    """专题最新快照日期。需登录。"""
    d = get_latest_snapshot_date(db, timeframe)
    return LatestDateResponse(date=d, timeframe=timeframe)


@router.get("/{ts_code}/composition", response_model=CompositionResponse)
def get_index_composition(
    ts_code: str,
    current_user: User = Depends(get_current_user),
    trade_date: date | None = Query(None, description="个股 PE 百分位快照日"),
    weight_as_of: date | None = Query(None, description="成分权重表日期（不传则自动选取）"),
    db=Depends(get_db),
):
    """成分权重 + 指数 PE 百分位推理。需登录。"""
    snap = suggest_snapshot_trade_date(db, trade_date)
    if snap is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "INDEX_NO_BAR", "message": "暂无指数日线，无法确定快照日"},
        )
    bundle = infer_index_pe_percentile_bundle(db, ts_code, snapshot_trade_date=snap, weight_as_of=weight_as_of)
    return CompositionResponse.from_service_bundle(bundle)
