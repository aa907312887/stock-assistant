"""回测引擎：执行回测主流程（后台线程调用）。"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.backtest_task import BacktestTask
from app.models.backtest_trade import BacktestTrade as BacktestTradeModel
from app.models.market_temperature_daily import MarketTemperatureDaily
from app.models.index_basic import IndexBasic
from app.models.stock_basic import StockBasic
from app.services.backtest.backtest_context import reset_backtest_symbols, set_backtest_symbols
from app.services.backtest.backtest_report import (
    calculate_exchange_stats,
    calculate_market_stats,
    calculate_report,
    calculate_temp_level_stats,
    generate_conclusion,
)
from app.services.backtest.portfolio_simulation import simulate_single_slot_portfolio
from app.services.strategy.registry import get_strategy
from app.services.strategy.strategy_base import BacktestTrade
from app.services.strategy.strategy_descriptions import STRATEGY_DESCRIPTIONS

logger = logging.getLogger(__name__)

# 所有策略均跑单仓+补仓资金仿真；仅 panic_pullback 允许「上一笔卖出当日」再开仓他股（allow_rebuy_same_day_as_prior_sell）。
_PANIC_SAME_DAY_REBUY_STRATEGY_ID = "panic_pullback"


def enrich_trades_with_temperature(db: Session, trades: list[BacktestTrade]) -> list[BacktestTrade]:
    """批量查询所有买入日的大盘温度，补充到每笔交易中。"""
    if not trades:
        return trades

    buy_dates = list({t.buy_date for t in trades})
    temps = (
        db.query(
            MarketTemperatureDaily.trade_date,
            MarketTemperatureDaily.temperature_score,
            MarketTemperatureDaily.temperature_level,
        )
        .filter(MarketTemperatureDaily.trade_date.in_(buy_dates))
        .all()
    )
    temp_map = {t.trade_date: (float(t.temperature_score), t.temperature_level) for t in temps}

    enriched = []
    for trade in trades:
        score, level = temp_map.get(trade.buy_date, (None, None))
        enriched.append(replace(trade, market_temp_score=score, market_temp_level=level))
    return enriched


def enrich_trades_with_stock_dimension(db: Session, trades: list[BacktestTrade]) -> list[BacktestTrade]:
    """批量补充交易所与板块维度。"""
    if not trades:
        return trades

    codes = list({t.stock_code for t in trades})
    rows = (
        db.query(StockBasic.code, StockBasic.exchange, StockBasic.market)
        .filter(StockBasic.code.in_(codes))
        .all()
    )
    info_map = {r.code: (r.exchange, r.market) for r in rows}

    rows_ix = (
        db.query(IndexBasic.ts_code, IndexBasic.market)
        .filter(IndexBasic.ts_code.in_(codes))
        .all()
    )
    for r in rows_ix:
        # 指数：exchange 填空，market 用 publisher/market 文本便于报表维度展示
        if r.ts_code not in info_map:
            info_map[r.ts_code] = (None, r.market)

    enriched = []
    for trade in trades:
        exchange, market = info_map.get(trade.stock_code, (None, None))
        # 北交所属于交易所维度，不纳入“板块”统计
        if exchange == "BSE" and market == "北交所":
            market = None
        enriched.append(replace(trade, exchange=exchange, market=market))
    return enriched


def run_backtest(
    db: Session,
    *,
    task_id: str,
    strategy_id: str,
    start_date: date,
    end_date: date,
    position_amount: float = 100_000.0,
    reserve_amount: float = 100_000.0,
    symbols: list[str] | None = None,
) -> None:
    """后台线程中执行的回测主流程。"""
    task = db.query(BacktestTask).filter(BacktestTask.task_id == task_id).one()

    # 在回测开始时，将当时的策略描述持久化到数据库，确保历史记录准确
    task.strategy_description = STRATEGY_DESCRIPTIONS.get(strategy_id)

    try:
        strategy = get_strategy(strategy_id)
        if strategy is None:
            raise ValueError(f"策略不存在: {strategy_id}")

        logger.info(
            "回测开始: task_id=%s, strategy=%s, %s ~ %s symbols=%s",
            task_id,
            strategy_id,
            start_date,
            end_date,
            symbols or [],
        )

        ctx_tok = set_backtest_symbols(symbols)
        try:
            result = strategy.backtest(start_date=start_date, end_date=end_date)
        finally:
            reset_backtest_symbols(ctx_tok)

        enriched_trades = enrich_trades_with_temperature(db, result.trades)
        enriched_trades = enrich_trades_with_stock_dimension(db, enriched_trades)

        closed_for_slot = [t for t in enriched_trades if t.trade_type == "closed"]
        unclosed_kept = [t for t in enriched_trades if t.trade_type != "closed"]
        allow_same_day_rebuy = strategy_id == _PANIC_SAME_DAY_REBUY_STRATEGY_ID

        executed_closed, not_traded_rows, portfolio_summary = simulate_single_slot_portfolio(
            closed_for_slot,
            position_size=position_amount,
            initial_principal=position_amount,
            initial_reserve=reserve_amount,
            allow_rebuy_same_day_as_prior_sell=allow_same_day_rebuy,
        )
        combined = executed_closed + not_traded_rows + unclosed_kept

        _type_order = {"closed": 0, "not_traded": 1, "unclosed": 2}

        def _persist_sort_key(t: BacktestTrade) -> tuple:
            return (t.buy_date, _type_order.get(t.trade_type, 9), t.stock_code or "")

        enriched_trades = sorted(combined, key=_persist_sort_key)

        for trade in enriched_trades:
            db.add(BacktestTradeModel(
                task_id=task_id,
                stock_code=trade.stock_code,
                stock_name=trade.stock_name,
                buy_date=trade.buy_date,
                trigger_date=trade.trigger_date,
                buy_price=trade.buy_price,
                sell_date=trade.sell_date,
                sell_price=trade.sell_price,
                return_rate=trade.return_rate,
                trade_type=trade.trade_type,
                exchange=trade.exchange,
                market=trade.market,
                market_temp_score=trade.market_temp_score,
                market_temp_level=trade.market_temp_level,
                extra_json=trade.extra if trade.extra else None,
            ))

        report = calculate_report(enriched_trades)
        temp_stats = calculate_temp_level_stats(enriched_trades)
        exchange_stats = calculate_exchange_stats(enriched_trades)
        market_stats = calculate_market_stats(enriched_trades)

        headline_return = float(portfolio_summary.total_return_on_initial_total)
        conclusion = generate_conclusion(
            headline_return,
            start_date,
            end_date,
            portfolio=portfolio_summary,
        )

        task.status = "completed" if report.unclosed_count == 0 else "incomplete"
        task.total_trades = report.total_trades
        task.win_trades = report.win_trades
        task.lose_trades = report.lose_trades
        task.win_rate = report.win_rate
        task.total_return = headline_return
        task.avg_return = report.avg_return
        task.max_win = report.max_win
        task.max_loss = report.max_loss
        task.unclosed_count = report.unclosed_count
        task.skipped_count = result.skipped_count

        assumptions_base: dict = {
            "price_type": "日线开盘价/收盘价",
            "data_source": "tushare",
            "fee_model": "无手续费",
            "conclusion": conclusion,
            "temp_level_stats": temp_stats,
            "exchange_stats": exchange_stats,
            "market_stats": market_stats,
            "skip_reasons": result.skip_reasons,
            "portfolio_simulation_applied": True,
            "portfolio_calendar_allow_same_day_rebuy_after_sell": allow_same_day_rebuy,
            # 策略层全部闭仓信号加总（含后来被标为 not_traded 的），仅作对照，非资金仿真结果
            "simple_sum_return_closed": float(sum(t.return_rate or 0 for t in closed_for_slot)),
            # 单仓仿真后实际成交闭仓的收益率加总（与明细中 trade_type=closed 一致）
            "simple_sum_return_executed": float(sum(t.return_rate or 0 for t in executed_closed)),
        }

        cal_rule = (
            "恐慌回落法：卖出当日收盘可再开仓他股。"
            if allow_same_day_rebuy
            else "本策略：须上一笔卖出日次日及以后方可再买（卖出当日不得换股）。"
        )
        assumptions_base["position_model"] = (
            f"单仓位+补仓池仿真。持仓 {position_amount:,.0f} 元/笔；补仓池初始 {reserve_amount:,.0f} 元；"
            f"同一买入日仅成交一笔；{cal_rule}"
            "开仓前本金不足持仓额时由补仓池划入；平仓盈利进补仓池，本金名义回现金，亏损全额回现金。"
        )
        assumptions_base["portfolio_params"] = {
            "position_amount": position_amount,
            "reserve_amount": reserve_amount,
        }
        assumptions_base["portfolio_capital"] = portfolio_summary.to_json_dict()
        assumptions_base["strategy_raw_closed_count"] = portfolio_summary.strategy_raw_closed_count
        assumptions_base["portfolio_skipped_closed_count"] = portfolio_summary.skipped_closed_count
        if symbols:
            assumptions_base["backtest_symbols"] = list(symbols)

        task.assumptions_json = assumptions_base
        task.finished_at = datetime.now()

        db.commit()
        logger.info(
            "回测完成: task_id=%s, status=%s, trades=%d, unclosed=%d",
            task_id, task.status, report.total_trades, report.unclosed_count,
        )

    except Exception as e:
        logger.exception("回测失败: task_id=%s, error=%s", task_id, e)
        db.rollback()
        task.status = "failed"
        task.error_message = str(e)
        task.finished_at = datetime.now()
        db.commit()
