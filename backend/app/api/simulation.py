"""历史模拟 API：发起模拟、查询任务与交易明细。"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.simulation_task import SimulationTask
from app.models.simulation_trade import SimulationTrade as SimulationTradeModel
from app.models.stock_daily_bar import StockDailyBar
from app.schemas.simulation import (
    RunSimulationRequest,
    RunSimulationResponse,
    SimulationReport,
    SimulationTaskDetailResponse,
    SimulationTaskItem,
    SimulationTaskListResponse,
    SimulationTradeItem,
    SimulationTradeListResponse,
)
from app.services.backtest.simulation_engine import run_simulation
from app.services.strategy.registry import get_strategy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulation", tags=["simulation"])


def _generate_task_id(strategy_id: str, start_date: date, end_date: date) -> str:
    short_uuid = uuid.uuid4().hex[:8]
    return f"sim-{strategy_id}-{start_date:%Y%m%d}-{end_date:%Y%m%d}-{short_uuid}"


def _split_csv_param(value: str | None) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


def _row_to_trade_item(r: SimulationTradeModel) -> SimulationTradeItem:
    return SimulationTradeItem(
        id=r.id,
        stock_code=r.stock_code,
        stock_name=r.stock_name,
        buy_date=r.buy_date,
        buy_price=float(r.buy_price),
        sell_date=r.sell_date,
        sell_price=float(r.sell_price) if r.sell_price is not None else None,
        return_rate=float(r.return_rate) if r.return_rate is not None else None,
        trade_type=r.trade_type,
        exchange=r.exchange,
        market=r.market,
        extra=r.extra_json,
    )


@router.post("/run")
def api_run_simulation(body: RunSimulationRequest, db: Session = Depends(get_db)):
    strategy = get_strategy(body.strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail={"code": "STRATEGY_NOT_FOUND", "message": "策略不存在"})

    if body.start_date >= body.end_date:
        raise HTTPException(status_code=400, detail={"code": "INVALID_PARAMS", "message": "开始日期必须早于结束日期"})

    min_date_row = db.query(func.min(StockDailyBar.trade_date)).scalar()
    max_date_row = db.query(func.max(StockDailyBar.trade_date)).scalar()
    if min_date_row is None or max_date_row is None:
        raise HTTPException(status_code=400, detail={"code": "DATE_OUT_OF_RANGE", "message": "数据库中无日线数据"})

    if body.start_date < min_date_row or body.end_date > max_date_row:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "DATE_OUT_OF_RANGE",
                "message": f"日期超出数据库可用范围 ({min_date_row} ~ {max_date_row})",
            },
        )

    task_id = _generate_task_id(body.strategy_id, body.start_date, body.end_date)
    desc = strategy.describe()

    task = SimulationTask(
        task_id=task_id,
        strategy_id=body.strategy_id,
        strategy_version=desc.version,
        start_date=body.start_date,
        end_date=body.end_date,
        status="running",
    )
    db.add(task)
    db.commit()

    def _runner():
        runner_db = SessionLocal()
        try:
            run_simulation(
                runner_db,
                task_id=task_id,
                strategy_id=body.strategy_id,
                start_date=body.start_date,
                end_date=body.end_date,
            )
        except Exception:
            logger.exception("模拟后台线程异常: task_id=%s", task_id)
        finally:
            runner_db.close()

    threading.Thread(target=_runner, daemon=True).start()
    logger.info("模拟任务已创建: task_id=%s", task_id)

    return JSONResponse(
        status_code=202,
        content=RunSimulationResponse(
            task_id=task_id,
            status="running",
            message="模拟任务已创建，后台执行中",
        ).model_dump(),
    )


@router.get("/tasks", response_model=SimulationTaskListResponse)
def api_list_simulation_tasks(
    strategy_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(SimulationTask)
    if strategy_id:
        query = query.filter(SimulationTask.strategy_id == strategy_id)

    total = query.count()
    tasks = query.order_by(SimulationTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for t in tasks:
        s = get_strategy(t.strategy_id)
        strategy_name = s.describe().name if s else t.strategy_id
        items.append(SimulationTaskItem(
            task_id=t.task_id,
            strategy_id=t.strategy_id,
            strategy_name=strategy_name,
            strategy_version=t.strategy_version,
            start_date=t.start_date,
            end_date=t.end_date,
            status=t.status,
            total_trades=t.total_trades,
            win_trades=t.win_trades,
            win_rate=float(t.win_rate) if t.win_rate is not None else None,
            avg_return=float(t.avg_return) if t.avg_return is not None else None,
            created_at=t.created_at,
            finished_at=t.finished_at,
        ))

    return SimulationTaskListResponse(total=total, page=page, page_size=page_size, items=items)


@router.get("/tasks/{task_id}", response_model=SimulationTaskDetailResponse)
def api_get_simulation_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(SimulationTask).filter(SimulationTask.task_id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "模拟任务不存在"})

    s = get_strategy(task.strategy_id)
    strategy_name = s.describe().name if s else task.strategy_id

    report = None
    assumptions = None
    if task.status in ("completed", "incomplete"):
        assumptions_json = task.assumptions_json or {}
        conclusion = assumptions_json.get("conclusion", "")

        report = SimulationReport(
            total_trades=task.total_trades or 0,
            win_trades=task.win_trades or 0,
            lose_trades=task.lose_trades or 0,
            win_rate=float(task.win_rate) if task.win_rate is not None else 0.0,
            avg_return=float(task.avg_return) if task.avg_return is not None else 0.0,
            max_win=float(task.max_win) if task.max_win is not None else 0.0,
            max_loss=float(task.max_loss) if task.max_loss is not None else 0.0,
            unclosed_count=task.unclosed_count,
            skipped_count=task.skipped_count,
            conclusion=conclusion,
        )
        assumptions = {
            k: v for k, v in assumptions_json.items()
            if k not in ("conclusion", "skip_reasons")
        }

    return SimulationTaskDetailResponse(
        task_id=task.task_id,
        strategy_id=task.strategy_id,
        strategy_name=strategy_name,
        strategy_version=task.strategy_version,
        start_date=task.start_date,
        end_date=task.end_date,
        status=task.status,
        report=report,
        assumptions=assumptions,
        created_at=task.created_at,
        finished_at=task.finished_at,
        strategy_description=task.strategy_description,
    )


@router.get("/tasks/{task_id}/trades", response_model=SimulationTradeListResponse)
def api_get_simulation_trades(
    task_id: str,
    trade_type: str | None = Query(default=None, description="closed=已平仓；unclosed=未平仓"),
    exchanges: str | None = Query(default=None, description="多选交易所，逗号分隔"),
    markets: str | None = Query(default=None, description="多选板块，逗号分隔"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    task = db.query(SimulationTask).filter(SimulationTask.task_id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "模拟任务不存在"})

    query = db.query(SimulationTradeModel).filter(SimulationTradeModel.task_id == task_id)

    if trade_type:
        query = query.filter(SimulationTradeModel.trade_type == trade_type)

    selected_exchanges = _split_csv_param(exchanges)
    if selected_exchanges:
        query = query.filter(SimulationTradeModel.exchange.in_(selected_exchanges))

    selected_markets = _split_csv_param(markets)
    empty_token = "__EMPTY__"
    if selected_markets:
        has_empty = empty_token in selected_markets
        normal_markets = [m for m in selected_markets if m != empty_token]
        if has_empty and normal_markets:
            query = query.filter(
                or_(
                    SimulationTradeModel.market.in_(normal_markets),
                    SimulationTradeModel.market.is_(None),
                    SimulationTradeModel.market == "",
                )
            )
        elif has_empty:
            query = query.filter(
                or_(
                    SimulationTradeModel.market.is_(None),
                    SimulationTradeModel.market == "",
                )
            )
        else:
            query = query.filter(SimulationTradeModel.market.in_(normal_markets))

    total = query.count()
    records = query.order_by(SimulationTradeModel.buy_date).offset((page - 1) * page_size).limit(page_size).all()

    items = [_row_to_trade_item(r) for r in records]
    return SimulationTradeListResponse(total=total, page=page, page_size=page_size, items=items)
