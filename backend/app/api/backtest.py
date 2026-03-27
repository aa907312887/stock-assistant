"""智能回测 API：发起回测、查询任务与交易明细。"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.backtest_task import BacktestTask
from app.models.backtest_trade import BacktestTrade as BacktestTradeModel
from app.models.stock_daily_bar import StockDailyBar
from app.schemas.backtest import (
    BacktestReport,
    DimensionStat,
    BacktestTaskDetailResponse,
    BacktestTaskItem,
    BacktestTaskListResponse,
    BacktestTradeItem,
    BacktestTradeListResponse,
    DataRangeResponse,
    RunBacktestRequest,
    RunBacktestResponse,
    TempLevelStat,
)
from app.services.backtest.backtest_engine import run_backtest
from app.services.strategy.registry import get_strategy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["backtest"])


def _generate_task_id(strategy_id: str, start_date: date, end_date: date) -> str:
    short_uuid = uuid.uuid4().hex[:8]
    return f"bt-{strategy_id}-{start_date:%Y%m%d}-{end_date:%Y%m%d}-{short_uuid}"


@router.post("/run")
def api_run_backtest(body: RunBacktestRequest, db: Session = Depends(get_db)):
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

    task = BacktestTask(
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
            run_backtest(
                runner_db,
                task_id=task_id,
                strategy_id=body.strategy_id,
                start_date=body.start_date,
                end_date=body.end_date,
            )
        except Exception as e:
            logger.exception("回测后台线程异常: task_id=%s", task_id)
        finally:
            runner_db.close()

    threading.Thread(target=_runner, daemon=True).start()
    logger.info("回测任务已创建: task_id=%s", task_id)

    return JSONResponse(
        status_code=202,
        content=RunBacktestResponse(
            task_id=task_id,
            status="running",
            message="回测任务已创建，后台执行中",
        ).model_dump(),
    )


@router.get("/tasks", response_model=BacktestTaskListResponse)
def api_list_backtest_tasks(
    strategy_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(BacktestTask)
    if strategy_id:
        query = query.filter(BacktestTask.strategy_id == strategy_id)

    total = query.count()
    tasks = query.order_by(BacktestTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for t in tasks:
        s = get_strategy(t.strategy_id)
        strategy_name = s.describe().name if s else t.strategy_id
        items.append(BacktestTaskItem(
            task_id=t.task_id,
            strategy_id=t.strategy_id,
            strategy_name=strategy_name,
            strategy_version=t.strategy_version,
            start_date=t.start_date,
            end_date=t.end_date,
            status=t.status,
            total_trades=t.total_trades,
            win_rate=float(t.win_rate) if t.win_rate is not None else None,
            total_return=float(t.total_return) if t.total_return is not None else None,
            created_at=t.created_at,
            finished_at=t.finished_at,
        ))

    return BacktestTaskListResponse(total=total, page=page, page_size=page_size, items=items)


@router.get("/tasks/{task_id}", response_model=BacktestTaskDetailResponse)
def api_get_backtest_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(BacktestTask).filter(BacktestTask.task_id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "回测任务不存在"})

    s = get_strategy(task.strategy_id)
    strategy_name = s.describe().name if s else task.strategy_id

    report = None
    assumptions = None
    if task.status in ("completed", "incomplete"):
        assumptions_json = task.assumptions_json or {}
        temp_stats_raw = assumptions_json.get("temp_level_stats", [])
        exchange_stats_raw = assumptions_json.get("exchange_stats", [])
        market_stats_raw = assumptions_json.get("market_stats", [])
        temp_stats = [TempLevelStat(**ts) for ts in temp_stats_raw]
        exchange_stats = [DimensionStat(**s) for s in exchange_stats_raw]
        market_stats = [DimensionStat(**s) for s in market_stats_raw]
        conclusion = assumptions_json.get("conclusion", "")

        report = BacktestReport(
            total_trades=task.total_trades or 0,
            win_trades=task.win_trades or 0,
            lose_trades=task.lose_trades or 0,
            win_rate=float(task.win_rate) if task.win_rate is not None else 0.0,
            total_return=float(task.total_return) if task.total_return is not None else 0.0,
            avg_return=float(task.avg_return) if task.avg_return is not None else 0.0,
            max_win=float(task.max_win) if task.max_win is not None else 0.0,
            max_loss=float(task.max_loss) if task.max_loss is not None else 0.0,
            unclosed_count=task.unclosed_count,
            skipped_count=task.skipped_count,
            conclusion=conclusion,
            temp_level_stats=temp_stats,
            exchange_stats=exchange_stats,
            market_stats=market_stats,
        )
        assumptions = {
            k: v for k, v in assumptions_json.items()
            if k not in ("conclusion", "temp_level_stats", "exchange_stats", "market_stats", "skip_reasons")
        }

    return BacktestTaskDetailResponse(
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
    )


@router.get("/tasks/{task_id}/trades", response_model=BacktestTradeListResponse)
def api_get_backtest_trades(
    task_id: str,
    trade_type: str | None = Query(default=None),
    market_temp_level: str | None = Query(default=None),
    market: str | None = Query(default=None),
    exchange: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    task = db.query(BacktestTask).filter(BacktestTask.task_id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "回测任务不存在"})

    query = db.query(BacktestTradeModel).filter(BacktestTradeModel.task_id == task_id)
    if trade_type:
        query = query.filter(BacktestTradeModel.trade_type == trade_type)
    if market_temp_level:
        query = query.filter(BacktestTradeModel.market_temp_level == market_temp_level)
    if market:
        query = query.filter(BacktestTradeModel.market == market)
    if exchange:
        query = query.filter(BacktestTradeModel.exchange == exchange)

    total = query.count()
    records = query.order_by(BacktestTradeModel.buy_date).offset((page - 1) * page_size).limit(page_size).all()

    items = [
        BacktestTradeItem(
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
            market_temp_score=float(r.market_temp_score) if r.market_temp_score is not None else None,
            market_temp_level=r.market_temp_level,
            extra=r.extra_json,
        )
        for r in records
    ]

    return BacktestTradeListResponse(total=total, page=page, page_size=page_size, items=items)


@router.get("/data-range", response_model=DataRangeResponse)
def api_get_data_range(db: Session = Depends(get_db)):
    min_date = db.query(func.min(StockDailyBar.trade_date)).scalar()
    max_date = db.query(func.max(StockDailyBar.trade_date)).scalar()
    return DataRangeResponse(min_date=min_date, max_date=max_date)
