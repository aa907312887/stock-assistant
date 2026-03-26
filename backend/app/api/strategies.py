"""策略选股 API：内置策略列表、详情、结果查询与执行。"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.strategy import (
    ExecuteStrategyRequest,
    ExecuteStrategyResponse,
    ExecutionSnapshot,
    GetStrategyResponse,
    ListStrategiesResponse,
    StrategySelectionItem,
    StrategySummary,
)
from app.services.strategy.registry import get_strategy, list_strategies
from app.services.strategy.strategy_execute_service import (
    StrategyDataNotReadyError,
    StrategyNotFoundError,
    execute_strategy,
    get_latest_strategy_result,
    StrategyResultNotFoundError,
)


router = APIRouter(tags=["strategies"])


@router.get("/strategies", response_model=ListStrategiesResponse)
def api_list_strategies() -> ListStrategiesResponse:
    items: list[StrategySummary] = []
    for s in list_strategies():
        d = s.describe()
        items.append(
            StrategySummary(
                strategy_id=d.strategy_id,
                name=d.name,
                version=d.version,
                short_description=d.short_description,
                route_path=d.route_path,
            )
        )
    return ListStrategiesResponse(items=items)


@router.get("/strategies/{strategy_id}", response_model=GetStrategyResponse)
def api_get_strategy(strategy_id: str) -> GetStrategyResponse:
    s = get_strategy(strategy_id)
    if not s:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "策略不存在"})
    d = s.describe()
    return GetStrategyResponse(
        strategy_id=d.strategy_id,
        name=d.name,
        version=d.version,
        description=d.description,
        assumptions=d.assumptions,
        risks=d.risks,
    )


@router.post("/strategies/{strategy_id}/execute", response_model=ExecuteStrategyResponse)
def api_execute_strategy(
    strategy_id: str,
    body: ExecuteStrategyRequest | None = None,
    db: Session = Depends(get_db),
) -> ExecuteStrategyResponse:
    try:
        snapshot, items, signals = execute_strategy(
            db,
            strategy_id=strategy_id,
            as_of_date=body.as_of_date if body else None,
        )
        return ExecuteStrategyResponse(
            execution=ExecutionSnapshot(
                execution_id=snapshot.execution_id,
                strategy_id=snapshot.strategy_id,
                strategy_version=snapshot.strategy_version,
                market="A股",
                as_of_date=snapshot.as_of_date,
                timeframe="daily",
                assumptions=snapshot.assumptions_json or {},
            ),
            items=[
                StrategySelectionItem(**it)
                for it in items
            ],
            signals=signals,
        )
    except StrategyNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except StrategyDataNotReadyError as e:
        raise HTTPException(status_code=409, detail={"code": "DATA_NOT_READY", "message": str(e)}) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)}) from e


@router.get("/strategies/{strategy_id}/latest", response_model=ExecuteStrategyResponse)
def api_get_latest_strategy_result(
    strategy_id: str,
    as_of_date: date | None = Query(default=None, description="截止时间点；不传则返回该策略最新一次已落库结果"),
    db: Session = Depends(get_db),
) -> ExecuteStrategyResponse:
    """
    查询已落库的最新结果（只读，不触发执行）。

    页面进入时应调用该接口；“执行/刷新”按钮再调用 /execute。
    """
    try:
        snapshot, items, signals = get_latest_strategy_result(db, strategy_id=strategy_id, as_of_date=as_of_date)
        return ExecuteStrategyResponse(
            execution=ExecutionSnapshot(
                execution_id=snapshot.execution_id,
                strategy_id=snapshot.strategy_id,
                strategy_version=snapshot.strategy_version,
                market="A股",
                as_of_date=snapshot.as_of_date,
                timeframe="daily",
                assumptions=snapshot.assumptions_json or {},
            ),
            items=[StrategySelectionItem(**it) for it in items],
            signals=signals,
        )
    except StrategyResultNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)}) from e

