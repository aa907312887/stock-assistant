"""模拟引擎：执行历史模拟主流程（后台线程调用）。

与回测引擎 (backtest_engine) 的区别：
- 不做单仓位资金仿真（无 position_amount / reserve_amount）
- 不产生 not_traded 类型交易
- 存储到独立的 simulation_task / simulation_trade 表
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.simulation_task import SimulationTask
from app.models.simulation_trade import SimulationTrade as SimulationTradeModel
from app.services.backtest.backtest_engine import (
    enrich_trades_with_stock_dimension,
    enrich_trades_with_temperature,
)
from app.services.backtest.backtest_report import (
    calculate_exchange_stats,
    calculate_market_stats,
    calculate_temp_level_stats,
)
from app.services.strategy.registry import get_strategy
from app.services.strategy.strategy_descriptions import STRATEGY_DESCRIPTIONS

logger = logging.getLogger(__name__)


def run_simulation(
    db: Session,
    *,
    task_id: str,
    strategy_id: str,
    start_date,
    end_date,
) -> None:
    """后台线程中执行的模拟主流程。"""
    task = db.query(SimulationTask).filter(SimulationTask.task_id == task_id).one()

    task.strategy_description = STRATEGY_DESCRIPTIONS.get(strategy_id)

    try:
        strategy = get_strategy(strategy_id)
        if strategy is None:
            raise ValueError(f"策略不存在: {strategy_id}")

        logger.info("模拟开始: task_id=%s, strategy=%s, %s ~ %s", task_id, strategy_id, start_date, end_date)

        result = strategy.backtest(start_date=start_date, end_date=end_date)

        # 与回测一致：先补大盘温度，再补交易所/板块
        enriched_trades = enrich_trades_with_temperature(db, result.trades)
        enriched_trades = enrich_trades_with_stock_dimension(db, enriched_trades)

        # 只保留 closed 和 unclosed（模拟不产生 not_traded）
        trades_to_save = [t for t in enriched_trades if t.trade_type in ("closed", "unclosed")]

        # 按买入日期排序
        trades_to_save.sort(key=lambda t: (t.buy_date, t.stock_code or ""))

        # 写入交易明细
        for trade in trades_to_save:
            score = trade.market_temp_score
            db.add(SimulationTradeModel(
                task_id=task_id,
                stock_code=trade.stock_code,
                stock_name=trade.stock_name,
                buy_date=trade.buy_date,
                buy_price=trade.buy_price,
                sell_date=trade.sell_date,
                sell_price=trade.sell_price,
                return_rate=trade.return_rate,
                trade_type=trade.trade_type,
                exchange=trade.exchange,
                market=trade.market,
                market_temp_score=Decimal(str(score)) if score is not None else None,
                market_temp_level=trade.market_temp_level,
                extra_json=trade.extra if trade.extra else None,
            ))

        # 计算简化指标
        closed_trades = [t for t in trades_to_save if t.trade_type == "closed" and t.return_rate is not None]
        unclosed_count = len([t for t in trades_to_save if t.trade_type == "unclosed"])

        if closed_trades:
            returns = [t.return_rate for t in closed_trades]
            total_trades = len(returns)
            win_trades = len([r for r in returns if r > 0])
            lose_trades = total_trades - win_trades
            win_rate = win_trades / total_trades
            avg_return = sum(returns) / total_trades
            max_win = max(returns)
            max_loss = min(returns)
        else:
            total_trades = 0
            win_trades = 0
            lose_trades = 0
            win_rate = 0.0
            avg_return = 0.0
            max_win = 0.0
            max_loss = 0.0

        # 生成结论
        conclusion = _generate_conclusion(
            total_trades, win_rate, avg_return, max_win, max_loss,
            unclosed_count, start_date, end_date,
        )

        temp_stats = calculate_temp_level_stats(trades_to_save)
        exchange_stats = calculate_exchange_stats(trades_to_save)
        market_stats = calculate_market_stats(trades_to_save)

        # 更新任务
        task.status = "completed" if unclosed_count == 0 else "incomplete"
        task.total_trades = total_trades
        task.win_trades = win_trades
        task.lose_trades = lose_trades
        task.win_rate = win_rate
        task.avg_return = avg_return
        task.max_win = max_win
        task.max_loss = max_loss
        task.unclosed_count = unclosed_count
        task.skipped_count = result.skipped_count

        task.assumptions_json = {
            "price_type": "日线收盘价",
            "data_source": "tushare",
            "fee_model": "无手续费",
            "conclusion": conclusion,
            "skip_reasons": result.skip_reasons,
            "portfolio_simulation_applied": False,
            "temp_level_stats": temp_stats,
            "exchange_stats": exchange_stats,
            "market_stats": market_stats,
        }
        task.finished_at = datetime.now()

        db.commit()
        logger.info(
            "模拟完成: task_id=%s, status=%s, trades=%d, unclosed=%d",
            task_id, task.status, total_trades, unclosed_count,
        )

    except Exception as e:
        logger.exception("模拟失败: task_id=%s, error=%s", task_id, e)
        db.rollback()
        task.status = "failed"
        task.error_message = str(e)
        task.finished_at = datetime.now()
        db.commit()


def _generate_conclusion(
    total_trades: int,
    win_rate: float,
    avg_return: float,
    max_win: float,
    max_loss: float,
    unclosed_count: int,
    start_date,
    end_date,
) -> str:
    """生成模拟结论文本。"""
    if total_trades == 0:
        return f"在 {start_date} 至 {end_date} 期间未产生已平仓交易。"

    parts = [
        f"在 {start_date} 至 {end_date} 期间共产生 {total_trades} 笔已平仓交易，",
        f"胜率 {win_rate * 100:.1f}%，",
        f"平均收益率 {avg_return * 100:.2f}%，",
        f"最大盈利 {max_win * 100:.2f}%，",
        f"最大亏损 {max_loss * 100:.2f}%。",
    ]
    if unclosed_count > 0:
        parts.append(f"另有 {unclosed_count} 笔未平仓。")

    return "".join(parts)
