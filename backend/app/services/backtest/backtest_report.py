"""回测绩效指标计算与温度分组统计。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

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


def generate_conclusion(total_return: float, start_date: date, end_date: date) -> str:
    """根据总收益率生成盈亏结论文案。"""
    if total_return > 0:
        return f"该策略在 {start_date} 至 {end_date} 期间总体盈利 {total_return:.2%}"
    elif total_return < 0:
        return f"该策略在 {start_date} 至 {end_date} 期间总体亏损 {abs(total_return):.2%}"
    else:
        return f"该策略在 {start_date} 至 {end_date} 期间收益持平"
