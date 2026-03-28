"""策略注册表（strategy_id -> 策略实现）。"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.strategy.strategy_base import StockStrategy
from app.services.strategy.strategies.chong_gao_hui_luo import ChongGaoHuiLuoStrategy
from app.services.strategy.strategies.panic_pullback import PanicPullbackStrategy


@dataclass(frozen=True)
class StrategyRegistryItem:
    strategy_id: str
    strategy: StockStrategy


def list_strategies() -> list[StockStrategy]:
    """返回系统内置策略实例列表（按展示顺序）。"""
    return [
        ChongGaoHuiLuoStrategy(),
        PanicPullbackStrategy(),
    ]


def get_strategy(strategy_id: str) -> StockStrategy | None:
    for s in list_strategies():
        if s.strategy_id == strategy_id:
            return s
    return None

