"""破 60 日均线买入法（ma60_five_day_break）：五日在下、突破、次日开买、±8% 收盘价单测。"""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.services.strategy.strategies.ma60_five_day_break import (
    _Params,
    entry_open_at_signal_index,
    ma60_five_below_and_breakout_at,
    ma60_five_below_then_break_ok,
    simulate_exit_close_8_8,
)


def _bar(
    d: date,
    *,
    o: float,
    c: float,
    ma60: float,
) -> SimpleNamespace:
    return SimpleNamespace(
        trade_date=d,
        open=Decimal(str(o)),
        close=Decimal(str(c)),
        ma60=Decimal(str(ma60)),
    )


def _valid_signal_bars() -> list[SimpleNamespace]:
    """
    下标 0～4 收盘 < 当日 ma60，下标 5 为信号日且收盘 > ma60，下标 6 为买入日，开盘价可成交。
    """
    d0 = date(2026, 1, 4)
    return [
        _bar(d0, o=1, c=9.0, ma60=10.0),  # 0
        _bar(d0 + timedelta(days=1), o=1, c=9.0, ma60=10.0),  # 1
        _bar(d0 + timedelta(days=2), o=1, c=9.0, ma60=10.0),  # 2
        _bar(d0 + timedelta(days=3), o=1, c=9.0, ma60=10.0),  # 3
        _bar(d0 + timedelta(days=4), o=1, c=9.0, ma60=10.0),  # 4
        _bar(d0 + timedelta(days=5), o=1, c=11.0, ma60=10.0),  # 5 信号
        _bar(d0 + timedelta(days=6), o=10.0, c=10.0, ma60=10.1),  # 6 买
    ]


def test_signal_ok_basic() -> None:
    bars = _valid_signal_bars()
    assert ma60_five_below_and_breakout_at(bars, 5)
    assert ma60_five_below_then_break_ok(bars, 5)
    assert entry_open_at_signal_index(bars, 5) == 10.0


def test_breakout_on_last_bar_without_next_day() -> None:
    """仅 6 根 K：i=5 为信号日且库中无 D+1，形态仍成立，但回测/次日开买不成立。"""
    d0 = date(2026, 1, 4)
    six = [
        _bar(d0, o=1, c=9.0, ma60=10.0),
        _bar(d0 + timedelta(days=1), o=1, c=9.0, ma60=10.0),
        _bar(d0 + timedelta(days=2), o=1, c=9.0, ma60=10.0),
        _bar(d0 + timedelta(days=3), o=1, c=9.0, ma60=10.0),
        _bar(d0 + timedelta(days=4), o=1, c=9.0, ma60=10.0),
        _bar(d0 + timedelta(days=5), o=1, c=11.0, ma60=10.0),
    ]
    assert ma60_five_below_and_breakout_at(six, 5)
    assert not ma60_five_below_then_break_ok(six, 5)
    assert entry_open_at_signal_index(six, 5) is None


def test_signal_fails_if_five_prev_not_all_below() -> None:
    bars = _valid_signal_bars()
    b = bars[2]
    bars[2] = _bar(b.trade_date, o=1, c=11.0, ma60=10.0)
    assert not ma60_five_below_then_break_ok(bars, 5)
    assert entry_open_at_signal_index(bars, 5) is None


def test_signal_fails_if_not_breakout() -> None:
    bars = _valid_signal_bars()
    b = bars[5]
    bars[5] = _bar(b.trade_date, o=1, c=9.0, ma60=10.0)
    assert not ma60_five_below_then_break_ok(bars, 5)


def test_entry_skips_invalid_open() -> None:
    bars = _valid_signal_bars()
    b = bars[6]
    bars[6] = _bar(b.trade_date, o=0.0, c=10.0, ma60=10.1)
    assert entry_open_at_signal_index(bars, 5) is None


def test_entry_skips_open_none() -> None:
    bars = _valid_signal_bars()
    b = bars[6]
    bars[6] = SimpleNamespace(
        trade_date=b.trade_date,
        open=None,
        close=b.close,
        ma60=b.ma60,
    )
    assert entry_open_at_signal_index(bars, 5) is None


def test_simulate_exit_stop_loss_8pct_first() -> None:
    p = _Params()
    d0 = date(2026, 2, 1)
    # buy_idx=0, buy=100, 次日起监测；首日收盘触发 −8%（先损）
    bars = [
        _bar(d0, o=10, c=10, ma60=50),  # buy
        _bar(d0 + timedelta(days=1), o=10, c=91.0, ma60=50.1),  # 100*0.92=92, 91<=92
    ]
    j, px, reason = simulate_exit_close_8_8(bars, 0, 100.0, p)
    assert j == 1 and reason == "stop_loss_8pct" and float(px) == 91.0


def test_simulate_exit_take_profit_8pct() -> None:
    p = _Params()
    d0 = date(2026, 2, 10)
    bars = [
        _bar(d0, o=10, c=10, ma60=50),
        _bar(d0 + timedelta(days=1), o=10, c=100.5, ma60=50.1),
        _bar(d0 + timedelta(days=2), o=10, c=109.0, ma60=50.2),  # 100*1.08=108
    ]
    j, px, reason = simulate_exit_close_8_8(bars, 0, 100.0, p)
    assert j == 2 and reason == "take_profit_8pct" and float(px) == 109.0


def test_simulate_exit_same_day_both_prices_favors_stop() -> None:
    """同价只可能满足一侧；若满足止损侧则出止损（先判止损）。"""
    p = _Params()
    d0 = date(2026, 3, 1)
    bars = [
        _bar(d0, o=10, c=10, ma60=50),
        _bar(d0 + timedelta(days=1), o=10, c=50.0, ma60=50.1),  # 对买价 100 而言极低，必止损
    ]
    j, _, reason = simulate_exit_close_8_8(bars, 0, 100.0, p)
    assert j == 1 and reason == "stop_loss_8pct"


def test_pure_functions_idempotent() -> None:
    bars = _valid_signal_bars()
    a = ma60_five_below_then_break_ok(bars, 5)
    b = ma60_five_below_then_break_ok(bars, 5)
    assert a is b and a
