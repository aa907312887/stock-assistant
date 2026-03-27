"""策略接口定义（代码实现策略的统一约束）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol


@dataclass(frozen=True)
class StrategyDescriptor:
    """用于前端展示的策略说明。"""

    strategy_id: str
    name: str
    version: str
    short_description: str
    description: str
    assumptions: list[str]
    risks: list[str]
    route_path: str


@dataclass(frozen=True)
class StrategyCandidate:
    """策略筛选出的候选（用于落库与响应）。"""

    stock_code: str
    stock_name: str | None
    exchange_type: str | None
    trigger_date: date
    summary: dict[str, Any]


@dataclass(frozen=True)
class StrategySignal:
    """策略产生的操作现场事件（用于回放/复现）。"""

    stock_code: str
    event_date: date
    event_type: str  # trigger/entry/exit/filter/note
    payload: dict[str, Any]


@dataclass(frozen=True)
class StrategyExecutionResult:
    """策略执行结果（不含 DB 写入信息）。"""

    as_of_date: date
    assumptions: dict[str, Any]
    params: dict[str, Any]
    items: list[StrategyCandidate]
    signals: list[StrategySignal]


@dataclass(frozen=True)
class BacktestTrade:
    """回测中的单笔模拟交易。"""

    stock_code: str
    stock_name: str | None
    buy_date: date
    buy_price: float
    sell_date: date | None = None
    sell_price: float | None = None
    return_rate: float | None = None
    trade_type: str = "closed"
    exchange: str | None = None
    market: str | None = None
    market_temp_score: float | None = None
    market_temp_level: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BacktestResult:
    """策略 backtest() 方法的返回值。"""

    trades: list[BacktestTrade]
    skipped_count: int = 0
    skip_reasons: list[str] = field(default_factory=list)


class StockStrategy(Protocol):
    """
    策略接口（强约束）。

    说明：
    - 策略以代码交付，用户不可在界面配置策略逻辑。
    - 后续回测会直接调用策略的"选股/买入/卖出"逻辑推进交易，因此策略必须在接口层稳定。
    """

    strategy_id: str
    version: str

    def describe(self) -> StrategyDescriptor: ...

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult: ...

    def backtest(self, *, start_date: date, end_date: date) -> BacktestResult: ...
