"""智能回测 API：发起回测、查询任务与交易明细。"""

from __future__ import annotations

import logging
import math
import threading
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.backtest_task import BacktestTask
from app.models.backtest_trade import BacktestTrade as BacktestTradeModel
from app.models.stock_daily_bar import StockDailyBar
from app.schemas.backtest import (
    BacktestBestOptionItem,
    BacktestBestOptionsResponse,
    BacktestFilteredMetrics,
    BacktestFilteredReportResponse,
    BacktestReport,
    BacktestYearlyAnalysisResponse,
    DimensionStat,
    BacktestTaskDetailResponse,
    BacktestTaskItem,
    BacktestTaskListResponse,
    BacktestTradeItem,
    BacktestTradeListResponse,
    DataRangeResponse,
    PortfolioCapitalOut,
    RunBacktestRequest,
    RunBacktestResponse,
    TempLevelStat,
    UserDecisionTaskStats,
    UserDecisionUpdateRequest,
)
from app.services.backtest.backtest_engine import run_backtest
from app.services.strategy.registry import get_strategy
from app.services.trade_query_metrics import (
    apply_trade_dimension_filters,
    calculate_metrics_from_trade_rows,
    yearly_aggregate_from_rows,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["backtest"])


def _generate_task_id(strategy_id: str, start_date: date, end_date: date) -> str:
    short_uuid = uuid.uuid4().hex[:8]
    return f"bt-{strategy_id}-{start_date:%Y%m%d}-{end_date:%Y%m%d}-{short_uuid}"


def _split_csv_param(value: str | None) -> list[str]:
    """把逗号分隔参数转成字符串数组，自动去空白与空值。"""
    if not value:
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


def _row_to_trade_item(r: BacktestTradeModel) -> BacktestTradeItem:
    """ORM 行转 API 交易明细项。"""
    return BacktestTradeItem(
        id=r.id,
        stock_code=r.stock_code,
        stock_name=r.stock_name,
        trigger_date=r.trigger_date,
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
        user_decision=r.user_decision,
        user_decision_reason=r.user_decision_reason,
        user_decision_at=r.user_decision_at,
    )


def _compute_user_decision_stats(db: Session, task_id: str) -> UserDecisionTaskStats:
    """汇总用户对某回测任务下全部交易的主观评价（正确率 = 优秀 ÷ 已评价）。"""
    rows = db.query(BacktestTradeModel).filter(BacktestTradeModel.task_id == task_id).all()
    trade_count = len(rows)
    judged = [r for r in rows if r.user_decision in ("excellent", "wrong")]
    excellent_count = sum(1 for r in judged if r.user_decision == "excellent")
    wrong_count = sum(1 for r in judged if r.user_decision == "wrong")
    judged_count = len(judged)
    correctness_rate = (excellent_count / judged_count) if judged_count > 0 else None
    return UserDecisionTaskStats(
        trade_count=trade_count,
        judged_count=judged_count,
        excellent_count=excellent_count,
        wrong_count=wrong_count,
        correctness_rate=correctness_rate,
    )


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
                position_amount=float(body.position_amount),
                reserve_amount=float(body.reserve_amount),
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

        portfolio_capital = None
        pc_raw = assumptions_json.get("portfolio_capital")
        if isinstance(pc_raw, dict):
            try:
                portfolio_capital = PortfolioCapitalOut(**pc_raw)
            except Exception:
                logger.warning("task_id=%s portfolio_capital 解析失败，已忽略", task.task_id)

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
            portfolio_capital=portfolio_capital,
        )
        assumptions = {
            k: v for k, v in assumptions_json.items()
            if k
            not in (
                "conclusion",
                "temp_level_stats",
                "exchange_stats",
                "market_stats",
                "skip_reasons",
                "portfolio_capital",
                "strategy_raw_closed_count",
                "portfolio_skipped_closed_count",
                "simple_sum_return_closed",
                "portfolio_params",
                "portfolio_simulation_applied",
                "portfolio_calendar_allow_same_day_rebuy_after_sell",
            )
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
        user_decision_stats=_compute_user_decision_stats(db, task_id),
        strategy_description=task.strategy_description,
    )


@router.patch("/tasks/{task_id}/trades/{trade_id}", response_model=BacktestTradeItem)
def api_patch_trade_user_decision(
    task_id: str,
    trade_id: int,
    body: UserDecisionUpdateRequest,
    db: Session = Depends(get_db),
):
    """更新单笔交易的人工策略评价（优秀 / 错误），可附理由；`judgment` 为空则清除评价。"""
    task = db.query(BacktestTask).filter(BacktestTask.task_id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "回测任务不存在"})

    row = (
        db.query(BacktestTradeModel)
        .filter(BacktestTradeModel.id == trade_id, BacktestTradeModel.task_id == task_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "TRADE_NOT_FOUND", "message": "交易明细不存在"})

    if body.judgment is None:
        row.user_decision = None
        row.user_decision_reason = None
        row.user_decision_at = None
    else:
        row.user_decision = body.judgment
        row.user_decision_reason = body.reason.strip() if body.reason and body.reason.strip() else None
        row.user_decision_at = datetime.now()

    db.commit()
    db.refresh(row)
    return _row_to_trade_item(row)


@router.get("/tasks/{task_id}/trades", response_model=BacktestTradeListResponse)
def api_get_backtest_trades(
    task_id: str,
    trade_type: str | None = Query(
        default=None,
        description="closed=已成交平仓；not_traded=选中未交易；unclosed=未平仓",
    ),
    market_temp_level: str | None = Query(default=None, description="兼容旧参数：单个温度级别"),
    market: str | None = Query(default=None, description="兼容旧参数：单个板块"),
    exchange: str | None = Query(default=None, description="兼容旧参数：单个交易所"),
    market_temp_levels: str | None = Query(default=None, description="多选温度级别，逗号分隔"),
    markets: str | None = Query(default=None, description="多选板块，逗号分隔"),
    exchanges: str | None = Query(default=None, description="多选交易所，逗号分隔"),
    year: int | None = Query(default=None, ge=1990, le=2100, description="按买入日自然年筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    task = db.query(BacktestTask).filter(BacktestTask.task_id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "回测任务不存在"})

    selected_temp_levels = _split_csv_param(market_temp_levels) or _split_csv_param(market_temp_level)
    selected_markets = _split_csv_param(markets) or _split_csv_param(market)
    selected_exchanges = _split_csv_param(exchanges) or _split_csv_param(exchange)

    query = db.query(BacktestTradeModel).filter(BacktestTradeModel.task_id == task_id)
    query = apply_trade_dimension_filters(
        query,
        BacktestTradeModel,
        trade_type=trade_type,
        market_temp_levels=selected_temp_levels,
        markets=selected_markets,
        exchanges=selected_exchanges,
        buy_year=year,
    )

    total = query.count()
    records = query.order_by(BacktestTradeModel.buy_date).offset((page - 1) * page_size).limit(page_size).all()

    items = [_row_to_trade_item(r) for r in records]

    return BacktestTradeListResponse(total=total, page=page, page_size=page_size, items=items)


@router.get("/tasks/{task_id}/filtered-report", response_model=BacktestFilteredReportResponse)
def api_get_filtered_report(
    task_id: str,
    trade_type: str | None = Query(
        default=None,
        description="closed=已成交平仓；not_traded=选中未交易；unclosed=未平仓；不传=不限",
    ),
    market_temp_levels: str | None = Query(default=None, description="多选温度级别，逗号分隔"),
    markets: str | None = Query(default=None, description="多选板块，逗号分隔"),
    exchanges: str | None = Query(default=None, description="多选交易所，逗号分隔"),
    year: int | None = Query(default=None, ge=1990, le=2100, description="按买入日自然年筛选"),
    db: Session = Depends(get_db),
):
    """
    对同一回测任务按条件交叉筛选后，复算胜率/总收益等指标。

    说明：该接口基于已落库交易明细计算，不会重新跑策略。
    """
    task = db.query(BacktestTask).filter(BacktestTask.task_id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "回测任务不存在"})

    selected_temp_levels = _split_csv_param(market_temp_levels)
    selected_markets = _split_csv_param(markets)
    selected_exchanges = _split_csv_param(exchanges)

    query = db.query(BacktestTradeModel).filter(BacktestTradeModel.task_id == task_id)
    query = apply_trade_dimension_filters(
        query,
        BacktestTradeModel,
        trade_type=trade_type,
        market_temp_levels=selected_temp_levels,
        markets=selected_markets,
        exchanges=selected_exchanges,
        buy_year=year,
    )
    rows = query.all()
    metrics = calculate_metrics_from_trade_rows(rows)

    return BacktestFilteredReportResponse(
        task_id=task_id,
        filters={
            "trade_type": trade_type,
            "market_temp_levels": selected_temp_levels,
            "markets": selected_markets,
            "exchanges": selected_exchanges,
            "year": year,
        },
        metrics=metrics,
    )


@router.get("/tasks/{task_id}/yearly-analysis", response_model=BacktestYearlyAnalysisResponse)
def api_get_yearly_analysis(
    task_id: str,
    trade_type: str | None = Query(
        default=None,
        description="closed=已成交平仓；not_traded=选中未交易；unclosed=未平仓；不传=不限",
    ),
    market_temp_levels: str | None = Query(default=None, description="多选温度级别，逗号分隔"),
    markets: str | None = Query(default=None, description="多选板块，逗号分隔"),
    exchanges: str | None = Query(default=None, description="多选交易所，逗号分隔"),
    year: int | None = Query(default=None, ge=1990, le=2100, description="仅统计该买入自然年；不传则按年分列展示全部"),
    db: Session = Depends(get_db),
):
    """
    按买入日自然年聚合：每年交易笔数、胜率、总收益等。
    可与温度/交易所/板块/年份筛选组合；年份与其它条件为 AND。
    """
    task = db.query(BacktestTask).filter(BacktestTask.task_id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "回测任务不存在"})

    selected_temp_levels = _split_csv_param(market_temp_levels)
    selected_markets = _split_csv_param(markets)
    selected_exchanges = _split_csv_param(exchanges)

    query = db.query(BacktestTradeModel).filter(BacktestTradeModel.task_id == task_id)
    query = apply_trade_dimension_filters(
        query,
        BacktestTradeModel,
        trade_type=trade_type,
        market_temp_levels=selected_temp_levels,
        markets=selected_markets,
        exchanges=selected_exchanges,
        buy_year=year,
    )
    rows = query.order_by(BacktestTradeModel.buy_date).all()

    items = yearly_aggregate_from_rows(rows)

    return BacktestYearlyAnalysisResponse(
        task_id=task_id,
        filters={
            "trade_type": trade_type,
            "market_temp_levels": selected_temp_levels,
            "markets": selected_markets,
            "exchanges": selected_exchanges,
            "year": year,
        },
        items=items,
    )


@router.get("/tasks/{task_id}/best-options", response_model=BacktestBestOptionsResponse)
def api_get_best_options(task_id: str, db: Session = Depends(get_db)):
    """
    自动搜索最优选项：
    - best_win_rate：胜率最高
    - best_total_return：总收益最高
    条件空间：温度/交易所/板块分别取“不过滤或某一个具体值（含空板块）”的交叉组合。
    """
    task = db.query(BacktestTask).filter(BacktestTask.task_id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "回测任务不存在"})

    all_rows = db.query(BacktestTradeModel).filter(BacktestTradeModel.task_id == task_id).all()
    if not all_rows:
        empty_metrics = calculate_metrics_from_trade_rows([])
        empty_item = BacktestBestOptionItem(
            filters={"market_temp_levels": [], "markets": [], "exchanges": []},
            metrics=empty_metrics,
        )
        return BacktestBestOptionsResponse(
            task_id=task_id,
            best_win_rate=empty_item,
            best_total_return=empty_item,
        )

    # 最佳胜率增加最小样本约束：候选组合的已平仓笔数必须 >= 总已平仓笔数的 1/10
    all_closed_total = len([r for r in all_rows if r.trade_type == "closed" and r.return_rate is not None])
    min_trades_for_best_win_rate = max(1, math.ceil(all_closed_total / 10)) if all_closed_total > 0 else 1

    temp_levels = sorted({r.market_temp_level for r in all_rows if r.market_temp_level})
    exchanges = sorted({r.exchange for r in all_rows if r.exchange})
    markets_raw = {r.market for r in all_rows}
    markets = sorted({m for m in markets_raw if m})
    has_empty_market = (None in markets_raw) or ("" in markets_raw)
    empty_token = "__EMPTY__"

    temp_choices: list[str | None] = [None, *temp_levels]
    exchange_choices: list[str | None] = [None, *exchanges]
    market_choices: list[str | None] = [None, *markets]
    if has_empty_market:
        market_choices.append(empty_token)

    best_win_filters: dict | None = None
    best_win_metrics: BacktestFilteredMetrics | None = None
    best_profit_filters: dict | None = None
    best_profit_metrics: BacktestFilteredMetrics | None = None

    for t in temp_choices:
        for e in exchange_choices:
            for m in market_choices:
                filtered = all_rows
                if t is not None:
                    filtered = [r for r in filtered if r.market_temp_level == t]
                if e is not None:
                    filtered = [r for r in filtered if r.exchange == e]
                if m is not None:
                    if m == empty_token:
                        filtered = [r for r in filtered if (r.market is None or r.market == "")]
                    else:
                        filtered = [r for r in filtered if r.market == m]

                metrics = calculate_metrics_from_trade_rows(filtered)
                if metrics.total_trades <= 0:
                    continue

                filters = {
                    "market_temp_levels": [t] if t is not None else [],
                    "exchanges": [e] if e is not None else [],
                    "markets": [m] if m is not None else [],
                }

                # 仅在样本量达标时参与“最佳胜率”评选，降低小样本偶然性
                if metrics.total_trades >= min_trades_for_best_win_rate:
                    if best_win_metrics is None:
                        best_win_metrics = metrics
                        best_win_filters = filters
                    else:
                        if (
                            metrics.win_rate > best_win_metrics.win_rate
                            or (
                                metrics.win_rate == best_win_metrics.win_rate
                                and metrics.total_return > best_win_metrics.total_return
                            )
                            or (
                                metrics.win_rate == best_win_metrics.win_rate
                                and metrics.total_return == best_win_metrics.total_return
                                and metrics.total_trades > best_win_metrics.total_trades
                            )
                        ):
                            best_win_metrics = metrics
                            best_win_filters = filters

                if best_profit_metrics is None:
                    best_profit_metrics = metrics
                    best_profit_filters = filters
                else:
                    if (
                        metrics.total_return > best_profit_metrics.total_return
                        or (
                            metrics.total_return == best_profit_metrics.total_return
                            and metrics.win_rate > best_profit_metrics.win_rate
                        )
                        or (
                            metrics.total_return == best_profit_metrics.total_return
                            and metrics.win_rate == best_profit_metrics.win_rate
                            and metrics.total_trades > best_profit_metrics.total_trades
                        )
                    ):
                        best_profit_metrics = metrics
                        best_profit_filters = filters

    if best_profit_metrics is None:
        empty_metrics = calculate_metrics_from_trade_rows([])
        empty_item = BacktestBestOptionItem(
            filters={"market_temp_levels": [], "markets": [], "exchanges": []},
            metrics=empty_metrics,
        )
        return BacktestBestOptionsResponse(
            task_id=task_id,
            best_win_rate=empty_item,
            best_total_return=empty_item,
        )

    # 若没有任何组合满足“最佳胜率最小样本约束”，回退为“全量不过滤”结果
    if best_win_metrics is None:
        fallback_metrics = calculate_metrics_from_trade_rows(all_rows)
        best_win_metrics = fallback_metrics
        best_win_filters = {"market_temp_levels": [], "markets": [], "exchanges": []}

    return BacktestBestOptionsResponse(
        task_id=task_id,
        best_win_rate=BacktestBestOptionItem(filters=best_win_filters or {}, metrics=best_win_metrics),
        best_total_return=BacktestBestOptionItem(filters=best_profit_filters or {}, metrics=best_profit_metrics),
    )


@router.get("/data-range", response_model=DataRangeResponse)
def api_get_data_range(db: Session = Depends(get_db)):
    min_date = db.query(func.min(StockDailyBar.trade_date)).scalar()
    max_date = db.query(func.max(StockDailyBar.trade_date)).scalar()
    return DataRangeResponse(min_date=min_date, max_date=max_date)
