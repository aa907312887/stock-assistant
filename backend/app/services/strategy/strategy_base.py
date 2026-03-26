"""策略接口定义（代码实现策略的统一约束）。"""

from __future__ import annotations

from dataclasses import dataclass
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


class StockStrategy(Protocol):
    """
    策略接口（强约束）。

    说明：
    - 策略以代码交付，用户不可在界面配置策略逻辑。
    - 后续回测会直接调用策略的“选股/买入/卖出”逻辑推进交易，因此策略必须在接口层稳定。
    """

    strategy_id: str
    version: str

    def describe(self) -> StrategyDescriptor: ...

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult: ...

