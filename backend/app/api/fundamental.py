"""基本面分析 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Literal

from app.database import get_db
from app.schemas.fundamental import FundamentalItem, FundamentalResponse
from app.services.fundamental_service import list_fundamentals

router = APIRouter(prefix="/fundamental", tags=["基本面分析"])


@router.get("/analysis", response_model=FundamentalResponse)
def api_fundamental_analysis(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    code: str | None = Query(default=None, description="股票代码模糊匹配"),
    name: str | None = Query(default=None, description="股票名称模糊匹配"),
    min_roe: float | None = Query(default=None, description="ROE 最小值"),
    max_roe: float | None = Query(default=None, description="ROE 最大值"),
    min_debt_to_assets: float | None = Query(default=None, description="资产负债率最小值"),
    max_debt_to_assets: float | None = Query(default=None, description="资产负债率最大值"),
    sort_by: str | None = Query(default=None, description="排序字段"),
    sort_order: Literal["asc", "desc"] = Query(default="desc", description="排序方向"),
    db: Session = Depends(get_db),
) -> FundamentalResponse:
    try:
        items, total = list_fundamentals(
            db,
            page=page,
            page_size=page_size,
            code=code,
            name=name,
            min_roe=min_roe,
            max_roe=max_roe,
            min_debt_to_assets=min_debt_to_assets,
            max_debt_to_assets=max_debt_to_assets,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return FundamentalResponse(
            items=[FundamentalItem(**it) for it in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)}) from e
