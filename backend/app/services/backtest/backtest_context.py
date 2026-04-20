"""回测运行期上下文：向策略的 backtest() 传递可选标的过滤列表（个股 ts_code / 指数 ts_code）。"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Optional

_backtest_symbols: ContextVar[Optional[list[str]]] = ContextVar("backtest_symbols", default=None)


def set_backtest_symbols(codes: list[str] | None) -> Token[Optional[list[str]]]:
    """进入回测线程前设置；返回 token 供 reset。"""
    return _backtest_symbols.set(codes)


def reset_backtest_symbols(token: Token[Optional[list[str]]]) -> None:
    """回测结束（含异常路径）必须调用，避免泄漏到同线程其它请求。"""
    _backtest_symbols.reset(token)


def get_backtest_symbols() -> list[str] | None:
    """当前回测是否限定在部分标的；None 表示全市场（策略自行定义）。"""
    return _backtest_symbols.get()
