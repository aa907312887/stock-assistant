"""选股接口：列表、最新数据日期。"""
import logging
from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.database import get_db
from app.models import User
from app.schemas.stock import LatestDateResponse, ScreeningItem, ScreeningResponse
from app.services.screening_service import get_latest_trade_date, list_screening

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stock", tags=["选股"])


@router.get("/screening", response_model=ScreeningResponse)
def get_screening(
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    code: str | None = Query(None),
    pct_min: float | None = Query(None),
    pct_max: float | None = Query(None),
    price_min: float | None = Query(None),
    price_max: float | None = Query(None),
    gpm_min: float | None = Query(None),
    gpm_max: float | None = Query(None),
    revenue_min: float | None = Query(None),
    revenue_max: float | None = Query(None),
    net_profit_min: float | None = Query(None),
    net_profit_max: float | None = Query(None),
    data_date: date | None = Query(None),
    db=Depends(get_db),
):
    """选股列表，分页+筛选。需登录。"""
    try:
        items, total, data_date_res = list_screening(
            db,
            page=page,
            page_size=page_size,
            code=code,
            pct_min=pct_min,
            pct_max=pct_max,
            price_min=price_min,
            price_max=price_max,
            gpm_min=gpm_min,
            gpm_max=gpm_max,
            revenue_min=revenue_min,
            revenue_max=revenue_max,
            net_profit_min=net_profit_min,
            net_profit_max=net_profit_max,
            data_date=data_date,
        )
        return ScreeningResponse(
            items=[ScreeningItem(**x) for x in items],
            total=total,
            page=page,
            page_size=page_size,
            data_date=data_date_res,
        )
    except Exception as e:
        logger.exception("选股列表失败: %s", e)
        raise


@router.get("/screening/latest-date", response_model=LatestDateResponse)
def get_screening_latest_date(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """最新数据日期，供前端展示「今天/昨天」。需登录。"""
    d = get_latest_trade_date(db)
    return LatestDateResponse(date=d)
