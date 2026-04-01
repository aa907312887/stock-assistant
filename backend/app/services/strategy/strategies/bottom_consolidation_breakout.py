"""
底部盘整突破策略。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from statistics import mean
from typing import Literal

from sqlalchemy import select, and_

from app.database import SessionLocal
from app.models import StockBasic, StockDailyBar
from app.services.strategy.strategy_base import (
    BacktestResult,
    BacktestTrade,
    StockStrategy,
    StrategyCandidate,
    StrategyDescriptor,
    StrategyExecutionResult,
    StrategySignal,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Params:
    consolidation_days: int = 15
    consolidation_range: float = 0.02  # 盘整幅度 ±2%
    low_position_ratio: float = 0.5
    profit_monitor_threshold: float = 0.15
    profit_trailing_pct: float = 0.05
    stop_loss_pct: float = 0.02  # 止损比例 2%
    min_hist_days: int = 60


@dataclass
class _ConsolidationState:
    close_prices: list[Decimal] = field(default_factory=list)
    start_date: date | None = None
    status: Literal["active", "broken", "invalid"] = "active"

    @property
    def days(self) -> int:
        return len(self.close_prices)

    @property
    def base_price(self) -> Decimal | None:
        if not self.close_prices:
            return None
        return Decimal(str(mean(self.close_prices)))


@dataclass
class _BreakoutSignal:
    stock_code: str
    trigger_date: date
    base_price: Decimal
    breakout_price: Decimal
    consolidation_days: int
    buy_date: date


@dataclass
class _PositionState:
    stock_code: str
    buy_date: date
    buy_price: Decimal
    base_price: Decimal
    stop_loss_price: Decimal
    highest_close: Decimal
    in_profit_monitor: bool = False
    take_profit_trigger: Decimal | None = None


class BottomConsolidationBreakoutStrategy(StockStrategy):
    strategy_id = "bottom_consolidation_breakout"
    version = "v1.0.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="底部盘整突破",
            version=self.version,
            short_description="识别低位盘整后向上突破的个股，通过止盈止损规则控制风险收益比。",
            description="本策略在 A 股日线数据上识别处于相对低位、经历至少15个交易日盘整后向上突破的个股。",
            assumptions=[
                "当前股价必须在历史最高价的二分之一以下。",
                "盘整持续天数必须不少于15个交易日。",
                "盘整幅度：围绕基准价上下浮动不超过2%。",
                "止损：跌破基准价2%卖出。",
                "基准价格使用盘整期间收盘价的算数平均值，动态更新。",
                "止盈止损采用条件单模式模拟。",
                "本策略用于历史验证，不构成投资建议。",
            ],
            risks=[
                "盘整形态可能继续延续，突破信号可能延迟出现。",
                "极端行情下止损可能无法精确以触发价成交。",
            ],
            route_path="/strategy/bottom-consolidation-breakout",
        )

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        params = _Params()
        if as_of_date is None:
            raise ValueError("as_of_date 不能为空")
        db = SessionLocal()
        try:
            items, signals = self._select_breakout_stocks(db, as_of_date=as_of_date, p=params)
            return StrategyExecutionResult(
                as_of_date=as_of_date,
                assumptions={"data_granularity": "日线", "stock_universe": "A股全市场"},
                params={
                    "consolidation_days": params.consolidation_days,
                    "consolidation_range": params.consolidation_range,
                    "low_position_ratio": params.low_position_ratio,
                },
                items=items,
                signals=signals,
            )
        finally:
            db.close()

    def backtest(self, *, start_date: date, end_date: date) -> BacktestResult:
        params = _Params()
        db = SessionLocal()
        try:
            bars_stmt = (
                select(StockDailyBar)
                .where(
                    and_(
                        StockDailyBar.trade_date >= start_date - timedelta(days=365),
                        StockDailyBar.trade_date <= end_date,
                        StockDailyBar.close.isnot(None),
                    )
                )
                .order_by(StockDailyBar.stock_code, StockDailyBar.trade_date)
            )
            all_bars = db.execute(bars_stmt).scalars().all()
            basics_stmt = select(StockBasic)
            basics = db.execute(basics_stmt).scalars().all()
            stock_names = {b.code: b.name for b in basics}
            bars_by_code: dict[str, list[StockDailyBar]] = defaultdict(list)
            for bar in all_bars:
                bars_by_code[bar.stock_code].append(bar)
            all_signals: list[_BreakoutSignal] = []
            skipped_count = 0
            for stock_code, stock_bars in bars_by_code.items():
                hist_bars = [b for b in stock_bars if b.trade_date <= end_date]
                if len(hist_bars) < params.min_hist_days:
                    skipped_count += 1
                    continue
                signals = self._find_consolidation_breakout(stock_code, hist_bars, params, start_date)
                all_signals.extend(signals)
            trades: list[BacktestTrade] = []
            for signal in all_signals:
                trade = self._simulate_trade(signal, bars_by_code[signal.stock_code], stock_names.get(signal.stock_code), params, end_date)
                if trade:
                    trades.append(trade)
            return BacktestResult(trades=trades, skipped_count=skipped_count)
        finally:
            db.close()

    def _select_breakout_stocks(self, db, *, as_of_date: date, p: _Params) -> tuple[list[StrategyCandidate], list[StrategySignal]]:
        bars_stmt = select(StockDailyBar).where(
            and_(
                StockDailyBar.trade_date == as_of_date,
                StockDailyBar.close.isnot(None),
                StockDailyBar.cum_hist_high.isnot(None),
            )
        )
        today_bars = db.execute(bars_stmt).scalars().all()
        basics_stmt = select(StockBasic)
        basics = db.execute(basics_stmt).scalars().all()
        stock_names = {b.code: b.name for b in basics}
        stock_exchanges = {b.code: b.exchange for b in basics}
        items: list[StrategyCandidate] = []
        signals: list[StrategySignal] = []
        for bar in today_bars:
            if bar.cum_hist_high is None or bar.close > bar.cum_hist_high * Decimal(str(p.low_position_ratio)):
                continue
            hist_stmt = select(StockDailyBar).where(
                and_(
                    StockDailyBar.stock_code == bar.stock_code,
                    StockDailyBar.trade_date <= as_of_date,
                    StockDailyBar.close.isnot(None),
                )
            ).order_by(StockDailyBar.trade_date.desc()).limit(200)
            hist_bars = list(reversed(db.execute(hist_stmt).scalars().all()))
            if len(hist_bars) < p.min_hist_days:
                continue
            found_signals = self._find_consolidation_breakout(bar.stock_code, hist_bars, p, as_of_date - timedelta(days=30))
            for sig in found_signals:
                if sig.trigger_date == as_of_date:
                    items.append(StrategyCandidate(
                        stock_code=sig.stock_code,
                        stock_name=stock_names.get(sig.stock_code),
                        exchange_type=stock_exchanges.get(sig.stock_code),
                        trigger_date=sig.trigger_date,
                        summary={"base_price": float(sig.base_price), "consolidation_days": sig.consolidation_days, "breakout_price": float(sig.breakout_price), "buy_date": str(sig.buy_date)},
                    ))
                    signals.append(StrategySignal(stock_code=sig.stock_code, event_date=sig.trigger_date, event_type="trigger", payload={"base_price": float(sig.base_price), "consolidation_days": sig.consolidation_days}))
        return items, signals

    def _find_consolidation_breakout(self, stock_code: str, bars: list[StockDailyBar], p: _Params, min_trigger_date: date | None = None) -> list[_BreakoutSignal]:
        signals: list[_BreakoutSignal] = []
        state = _ConsolidationState()
        for bar in bars:
            if bar.cum_hist_high is None:
                state = _ConsolidationState()
                continue
            if bar.close > bar.cum_hist_high * Decimal(str(p.low_position_ratio)):
                state = _ConsolidationState()
                continue
            new_close_prices = state.close_prices + [bar.close]
            new_base_price = Decimal(str(mean(new_close_prices)))
            max_deviation = max(abs(p - new_base_price) / new_base_price for p in new_close_prices)
            if max_deviation > Decimal(str(p.consolidation_range)):
                if bar.close > new_base_price * (1 + Decimal(str(p.consolidation_range))):
                    if state.days >= p.consolidation_days:
                        old_base_price = state.base_price
                        if old_base_price is not None and min_trigger_date is not None and bar.trade_date >= min_trigger_date:
                            signals.append(_BreakoutSignal(stock_code=stock_code, trigger_date=bar.trade_date, base_price=old_base_price, breakout_price=bar.close, consolidation_days=state.days, buy_date=self._next_trade_date(bar.trade_date, bars)))
                state = _ConsolidationState()
            else:
                state.close_prices = new_close_prices
                if state.start_date is None:
                    state.start_date = bar.trade_date
        return signals

    def _next_trade_date(self, current_date: date, bars: list[StockDailyBar]) -> date:
        for bar in bars:
            if bar.trade_date > current_date:
                return bar.trade_date
        return current_date + timedelta(days=1)

    def _simulate_trade(self, signal: _BreakoutSignal, bars: list[StockDailyBar], stock_name: str | None, p: _Params, end_date: date) -> BacktestTrade | None:
        buy_bar = None
        for bar in bars:
            if bar.trade_date == signal.buy_date:
                buy_bar = bar
                break
        if buy_bar is None or buy_bar.open is None:
            return None
        buy_price = buy_bar.open
        position = _PositionState(stock_code=signal.stock_code, buy_date=signal.buy_date, buy_price=buy_price, base_price=signal.base_price, stop_loss_price=signal.base_price * (1 - Decimal(str(p.stop_loss_pct))), highest_close=buy_price)
        sell_date, sell_price, exit_reason = None, None, None
        for bar in bars:
            if bar.trade_date <= signal.buy_date or bar.trade_date > end_date:
                continue
            # Step 1: 检查是否进入止盈监控（涨幅 >= 15%）
            if not position.in_profit_monitor and bar.close:
                if (bar.close - buy_price) / buy_price >= Decimal(str(p.profit_monitor_threshold)):
                    position.in_profit_monitor = True
            # Step 2: 计算止盈触发价（用当前最高收盘价，即昨日的）
            if position.in_profit_monitor:
                position.take_profit_trigger = position.highest_close * (1 - Decimal(str(p.profit_trailing_pct)))
            # Step 3: 检查止损
            if bar.low and bar.low <= position.stop_loss_price:
                sell_date, sell_price, exit_reason = bar.trade_date, position.stop_loss_price, "止损（跌破支撑位）"
                break
            # Step 4: 检查止盈（用昨日最高收盘价计算的触发价）
            if position.in_profit_monitor and position.take_profit_trigger and bar.low and bar.low <= position.take_profit_trigger:
                sell_date, sell_price, exit_reason = bar.trade_date, position.take_profit_trigger, "止盈（最高价回落5%）"
                break
            # Step 5: 最后更新最高收盘价（用于明天的触发价计算）
            if bar.close and bar.close > position.highest_close:
                position.highest_close = bar.close
        if sell_date is None:
            return BacktestTrade(stock_code=signal.stock_code, stock_name=stock_name, buy_date=signal.buy_date, buy_price=float(buy_price), sell_date=None, sell_price=None, return_rate=None, trade_type="unclosed", trigger_date=signal.trigger_date, extra={
                "base_price": float(signal.base_price),
                "consolidation_days": signal.consolidation_days,
                "stop_loss_price": float(position.stop_loss_price),
                "highest_close": float(position.highest_close),
                "in_profit_monitor": position.in_profit_monitor,
            })
        return_rate = (sell_price - buy_price) / buy_price
        return BacktestTrade(stock_code=signal.stock_code, stock_name=stock_name, buy_date=signal.buy_date, buy_price=float(buy_price), sell_date=sell_date, sell_price=float(sell_price), return_rate=float(return_rate), trade_type="closed", trigger_date=signal.trigger_date, extra={
            "base_price": float(signal.base_price),
            "consolidation_days": signal.consolidation_days,
            "stop_loss_price": float(position.stop_loss_price),
            "highest_close": float(position.highest_close),
            "take_profit_trigger": float(position.take_profit_trigger) if position.take_profit_trigger else None,
            "exit_reason": exit_reason,
        })