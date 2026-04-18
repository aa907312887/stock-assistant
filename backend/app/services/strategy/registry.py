"""策略注册表（strategy_id -> 策略实现）。"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.strategy.strategy_base import StockStrategy
from app.services.strategy.strategies.bottom_consolidation_breakout import BottomConsolidationBreakoutStrategy
from app.services.strategy.strategies.chong_gao_hui_luo import ChongGaoHuiLuoStrategy
from app.services.strategy.strategies.ma60_slope_buy import Ma60SlopeBuyStrategy
from app.services.strategy.strategies.ma_golden_cross import MAGoldenCrossStrategy
from app.services.strategy.strategies.panic_pullback import PanicPullbackStrategy
from app.services.strategy.strategies.shu_guang_chu_xian import ShuGuangChuXianStrategy
from app.services.strategy.strategies.da_yang_hui_luo import DaYangHuiLuoStrategy
from app.services.strategy.strategies.pe_value_investment import PeValueInvestmentStrategy
from app.services.strategy.strategies.zao_chen_shi_zi_xing import ZaoChenShiZiXingStrategy
from app.services.strategy.strategies.duo_tou_pai_lie import DuoTouPaiLieStrategy
from app.services.strategy.strategies.pe_zao_chen_shi_zi_xing import PeZaoChenShiZiXingStrategy
from app.services.strategy.strategies.di_wei_lian_yang import DiWeiLianYangStrategy


@dataclass(frozen=True)
class StrategyRegistryItem:
    strategy_id: str
    strategy: StockStrategy


def list_strategies() -> list[StockStrategy]:
    """返回系统内置策略实例列表（按展示顺序）。"""
    return [
        ChongGaoHuiLuoStrategy(),
        PanicPullbackStrategy(),
        ShuGuangChuXianStrategy(),
        ZaoChenShiZiXingStrategy(),
        DiWeiLianYangStrategy(),
        PeZaoChenShiZiXingStrategy(),
        BottomConsolidationBreakoutStrategy(),
        MAGoldenCrossStrategy(),
        Ma60SlopeBuyStrategy(),
        DaYangHuiLuoStrategy(),
        PeValueInvestmentStrategy(),
        DuoTouPaiLieStrategy(),
    ]


def get_strategy(strategy_id: str) -> StockStrategy | None:
    for s in list_strategies():
        if s.strategy_id == strategy_id:
            return s
    return None

