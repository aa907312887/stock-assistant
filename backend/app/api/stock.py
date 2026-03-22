"""选股接口：列表、最新数据日期。"""
import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.database import get_db
from app.models import User
from app.schemas.stock import LatestDateResponse, ScreeningItem, ScreeningResponse
from app.services.screening_service import get_latest_bar_date, list_screening

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stock", tags=["选股"])

ScreeningTimeframe = Literal["daily", "weekly", "monthly"]


@router.get("/screening", response_model=ScreeningResponse)
def get_screening(
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: str | None = Query(None, description="股票代码模糊"),
    name: str | None = Query(None, description="股票名称模糊"),
    ma_bull: bool | None = Query(None, description="是否均线多头排列：MA5>MA10>MA20>MA60"),
    macd_red: bool | None = Query(None, description="是否 MACD 红柱（柱>0）"),
    ma_cross: bool | None = Query(None, description="是否 MA5 上穿 MA10（相对上一根同周期 K）"),
    macd_cross: bool | None = Query(None, description="是否 MACD 金叉 DIF 上穿 DEA（相对上一根）"),
    timeframe: ScreeningTimeframe = Query("daily", description="日K / 周K / 月K"),
    data_date: date | None = Query(None),
    db=Depends(get_db),
):
    """选股列表，分页+筛选。需登录。"""
    try:
        items, total, data_date_res = list_screening(
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
        return ScreeningResponse(
            items=[ScreeningItem(**x) for x in items],
            total=total,
            page=page,
            page_size=page_size,
            timeframe=timeframe,
            data_date=data_date_res,
        )
    except Exception as e:
        logger.exception("选股列表失败: %s", e)
        raise


@router.get("/screening/latest-date", response_model=LatestDateResponse)
def get_screening_latest_date(
    current_user: User = Depends(get_current_user),
    timeframe: ScreeningTimeframe = Query("daily", description="日K / 周K / 月K"),
    db=Depends(get_db),
):
    """最新数据日期（各周期 bar 表最大日期列）。需登录。"""
    d = get_latest_bar_date(db, timeframe)
    return LatestDateResponse(date=d, timeframe=timeframe)
