"""回测与历史模拟共用的交易维度筛选与指标复算（基于已落库明细）。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, TypeVar

from sqlalchemy import or_
from sqlalchemy.orm import Query

from app.schemas.backtest import BacktestFilteredMetrics, BacktestYearlyStatItem

# 具备 buy_date、trade_type、return_rate、market_temp_level、market、exchange 字段的 ORM 模型
ModelT = TypeVar("ModelT")


def apply_trade_dimension_filters(
    query: Query,
    model: type[ModelT],
    *,
    trade_type: str | None,
    market_temp_levels: list[str],
    markets: list[str],
    exchanges: list[str],
    buy_year: int | None = None,
) -> Query:
    """在交易查询上统一应用筛选条件（同维 OR、跨维 AND），与 backtest.api 原语义一致。"""
    empty_token = "__EMPTY__"

    if buy_year is not None:
        query = query.filter(
            model.buy_date >= date(buy_year, 1, 1),
            model.buy_date <= date(buy_year, 12, 31),
        )

    if trade_type:
        query = query.filter(model.trade_type == trade_type)
    if market_temp_levels:
        query = query.filter(model.market_temp_level.in_(market_temp_levels))
    if markets:
        has_empty = empty_token in markets
        normal_markets = [m for m in markets if m != empty_token]
        if has_empty and normal_markets:
            query = query.filter(
                or_(
                    model.market.in_(normal_markets),
                    model.market.is_(None),
                    model.market == "",
                )
            )
        elif has_empty:
            query = query.filter(
                or_(
                    model.market.is_(None),
                    model.market == "",
                )
            )
        else:
            query = query.filter(model.market.in_(normal_markets))
    if exchanges:
        query = query.filter(model.exchange.in_(exchanges))
    return query


def calculate_metrics_from_trade_rows(rows: list[Any]) -> BacktestFilteredMetrics:
    """与 backtest.api._calculate_metrics_from_rows 一致：已平仓且有收益率计入胜率分母。"""
    matched_count = len(rows)
    closed = [r for r in rows if r.trade_type == "closed" and r.return_rate is not None]
    unclosed_count = len([r for r in rows if r.trade_type == "unclosed"])
    returns = [float(r.return_rate) for r in closed]
    if not closed:
        return BacktestFilteredMetrics(
            total_trades=0,
            win_trades=0,
            lose_trades=0,
            win_rate=0.0,
            total_return=0.0,
            avg_return=0.0,
            max_win=0.0,
            max_loss=0.0,
            unclosed_count=unclosed_count,
            matched_count=matched_count,
        )

    win_trades = len([x for x in returns if x > 0])
    lose_trades = len(returns) - win_trades
    total_trades = len(returns)
    return BacktestFilteredMetrics(
        total_trades=total_trades,
        win_trades=win_trades,
        lose_trades=lose_trades,
        win_rate=win_trades / total_trades,
        total_return=sum(returns),
        avg_return=sum(returns) / total_trades,
        max_win=max(returns),
        max_loss=min(returns),
        unclosed_count=unclosed_count,
        matched_count=matched_count,
    )


def yearly_aggregate_from_rows(rows: list[Any]) -> list[BacktestYearlyStatItem]:
    """按买入日自然年聚合，与 backtest yearly-analysis 一致。"""
    by_year: dict[int, list[Any]] = defaultdict(list)
    for r in rows:
        by_year[r.buy_date.year].append(r)

    items: list[BacktestYearlyStatItem] = []
    for y in sorted(by_year.keys()):
        m = calculate_metrics_from_trade_rows(by_year[y])
        items.append(
            BacktestYearlyStatItem(
                year=y,
                matched_count=m.matched_count,
                total_trades=m.total_trades,
                win_trades=m.win_trades,
                lose_trades=m.lose_trades,
                win_rate=m.win_rate,
                total_return=m.total_return,
                avg_return=m.avg_return,
            )
        )
    return items
