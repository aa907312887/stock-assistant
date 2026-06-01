"""纯正均线多头排列（chun_zheng_ma_duotou）：三线判定与离场复用单测。"""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.services.strategy.strategies.chun_zheng_ma_duotou import is_pure_ma_bull_order_bar
from app.services.strategy.strategies.ma60_five_day_break import _Params, simulate_exit_close_8_8


def test_pure_bull_true() -> None:
    bar = SimpleNamespace(ma5=Decimal("12"), ma10=Decimal("11"), ma20=Decimal("10"))
    assert is_pure_ma_bull_order_bar(bar)


def test_pure_bull_false_equal() -> None:
    bar = SimpleNamespace(ma5=Decimal("10"), ma10=Decimal("10"), ma20=Decimal("9"))
    assert not is_pure_ma_bull_order_bar(bar)


def test_pure_bull_false_none() -> None:
    bar = SimpleNamespace(ma5=Decimal("12"), ma10=None, ma20=Decimal("10"))
    assert not is_pure_ma_bull_order_bar(bar)


def test_exit_after_buy_uses_close_8_8() -> None:
    """信号后次日开盘买，随后收盘触达 ±8%（先损）。"""
    p = _Params()
    d0 = date(2026, 2, 2)
    bars = [
        SimpleNamespace(
            trade_date=d0,
            open=Decimal("10"),
            high=Decimal("10"),
            low=Decimal("10"),
            close=Decimal("10"),
            ma5=Decimal("3"),
            ma10=Decimal("2"),
            ma20=Decimal("1"),
        ),
        SimpleNamespace(
            trade_date=d0 + timedelta(days=1),
            open=Decimal("10"),
            high=Decimal("10"),
            low=Decimal("10"),
            close=Decimal("10"),
            ma5=Decimal("4"),
            ma10=Decimal("3"),
            ma20=Decimal("2"),
        ),
        SimpleNamespace(
            trade_date=d0 + timedelta(days=2),
            open=Decimal("10"),
            high=Decimal("10"),
            low=Decimal("8"),
            close=Decimal("9"),
            ma5=Decimal("4"),
            ma10=Decimal("3"),
            ma20=Decimal("2"),
        ),
    ]
    buy_price = 10.0
    sell_j, sell_px, reason = simulate_exit_close_8_8(bars, 1, buy_price, p)
    assert sell_j == 2
    assert reason == "stop_loss_8pct"
    assert sell_px == 9.0
