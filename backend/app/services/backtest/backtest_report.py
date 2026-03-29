"""回测绩效指标计算与温度分组统计。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.services.backtest.portfolio_simulation import PortfolioCapitalSummary
from app.services.strategy.strategy_base import BacktestTrade


@dataclass
class ReportMetrics:
    """绩效报告指标集合。"""

    total_trades: int
    win_trades: int
    lose_trades: int
    win_rate: float
    total_return: float
    avg_return: float
    max_win: float
    max_loss: float
    unclosed_count: int


def calculate_report(trades: list[BacktestTrade]) -> ReportMetrics:
    """根据交易列表计算绩效报告指标（仅统计已平仓交易）。"""
    closed = [t for t in trades if t.trade_type == "closed"]
    unclosed = [t for t in trades if t.trade_type == "unclosed"]

    total = len(closed)
    if total == 0:
        return ReportMetrics(
            total_trades=0,
            win_trades=0,
            lose_trades=0,
            win_rate=0.0,
            total_return=0.0,
            avg_return=0.0,
            max_win=0.0,
            max_loss=0.0,
            unclosed_count=len(unclosed),
        )

    wins = [t for t in closed if (t.return_rate or 0) > 0]
    losses = [t for t in closed if (t.return_rate or 0) <= 0]
    returns = [t.return_rate or 0 for t in closed]

    return ReportMetrics(
        total_trades=total,
        win_trades=len(wins),
        lose_trades=len(losses),
        win_rate=len(wins) / total,
        total_return=sum(returns),
        avg_return=sum(returns) / total,
        max_win=max(returns),
        max_loss=min(returns),
        unclosed_count=len(unclosed),
    )


def calculate_temp_level_stats(trades: list[BacktestTrade]) -> list[dict]:
    """按大盘温度级别分组统计胜率与平均收益。"""
    closed = [t for t in trades if t.trade_type == "closed" and t.market_temp_level]
    groups: dict[str, list[BacktestTrade]] = {}
    for t in closed:
        groups.setdefault(t.market_temp_level, []).append(t)  # type: ignore[arg-type]

    stats = []
    for level, group in groups.items():
        wins = [t for t in group if (t.return_rate or 0) > 0]
        returns = [t.return_rate or 0 for t in group]
        stats.append({
            "level": level,
            "total": len(group),
            "wins": len(wins),
            "win_rate": round(len(wins) / len(group), 4),
            "avg_return": round(sum(returns) / len(group), 4),
        })
    return sorted(stats, key=lambda s: s["total"], reverse=True)


def _calculate_group_stats(trades: list[BacktestTrade], key_getter) -> list[dict]:
    closed = [t for t in trades if t.trade_type == "closed" and key_getter(t)]
    groups: dict[str, list[BacktestTrade]] = {}
    for t in closed:
        key = key_getter(t)
        if not key:
            continue
        groups.setdefault(key, []).append(t)

    stats = []
    for key, group in groups.items():
        wins = [t for t in group if (t.return_rate or 0) > 0]
        returns = [t.return_rate or 0 for t in group]
        stats.append({
            "name": key,
            "total": len(group),
            "wins": len(wins),
            "win_rate": round(len(wins) / len(group), 4),
            "avg_return": round(sum(returns) / len(group), 4),
        })
    return sorted(stats, key=lambda s: s["total"], reverse=True)


def calculate_exchange_stats(trades: list[BacktestTrade]) -> list[dict]:
    """按交易所分组统计胜率与平均收益。"""
    return _calculate_group_stats(trades, lambda t: t.exchange)


def calculate_market_stats(trades: list[BacktestTrade]) -> list[dict]:
    """按板块分组统计胜率与平均收益。"""
    return _calculate_group_stats(trades, lambda t: t.market)


def generate_conclusion(
    total_return: float,
    start_date: date,
    end_date: date,
    *,
    portfolio: PortfolioCapitalSummary | None = None,
) -> str:
    """根据总收益率生成盈亏结论文案；若提供 portfolio 则按资金约束口径描述权益与双账户余额。"""
    if portfolio is not None:
        if portfolio.executed_closed_count == 0 and portfolio.strategy_raw_closed_count > 0:
            pa = portfolio.position_size
            cal = (
                "同日仅一笔，且早于上一笔卖出日不可买（恐慌口径下卖出当日可再买他股）"
                if portfolio.allow_rebuy_same_day_as_prior_sell
                else "同日仅一笔，且须上一笔卖出日之后方可买（卖出当日不得换股）"
            )
            return (
                f"该策略在 {start_date} 至 {end_date} 期间共产生 "
                f"{portfolio.strategy_raw_closed_count} 笔可平仓信号，但在持仓 {pa:,.0f} 元、"
                f"{cal} 的约束下实际成交 0 笔；本金与补仓池未动用，"
                f"合计权益仍为 {portfolio.initial_principal + portfolio.initial_reserve:,.0f} 元。"
            )
        tp = portfolio.total_profit
        r = portfolio.total_return_on_initial_total
        if tp > 0:
            profit_part = f"合计权益较初始增加约 {tp:,.0f} 元（相对本金+预备金合计收益率 {r:+.2%}）"
        elif tp < 0:
            profit_part = f"合计权益较初始减少约 {abs(tp):,.0f} 元（相对本金+预备金合计收益率 {r:+.2%}）"
        else:
            profit_part = f"合计权益与初始持平（收益率 {r:+.2%}）"
        pa = portfolio.position_size
        return (
            f"该策略在 {start_date} 至 {end_date} 期间，按持仓 {pa:,.0f} 元/笔、补仓池补仓规则模拟："
            f"{profit_part}；期末本金账户约 {portfolio.final_principal:,.0f} 元，补仓资金池约 {portfolio.final_reserve:,.0f} 元。"
        )
    if total_return > 0:
        return f"该策略在 {start_date} 至 {end_date} 期间总体盈利 {total_return:.2%}"
    elif total_return < 0:
        return f"该策略在 {start_date} 至 {end_date} 期间总体亏损 {abs(total_return):.2%}"
    else:
        return f"该策略在 {start_date} 至 {end_date} 期间收益持平"
