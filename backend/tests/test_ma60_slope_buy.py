"""60 日均线买入法（ma60_slope_buy）：三负一正 + 均线多头 + 次日开盘买 + 止盈止损单测。"""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.strategy.strategies.ma60_slope_buy import (
    _Params,
    ma60_signal_next_open_ok,
    simulate_exit_close_only,
)


def _bar(
    d: date,
    *,
    o: float,
    c: float,
    ma60: float,
    ma5: float,
    ma10: float,
    ma20: float,
) -> SimpleNamespace:
    return SimpleNamespace(
        trade_date=d,
        open=Decimal(str(o)),
        close=Decimal(str(c)),
        ma60=Decimal(str(ma60)),
        ma5=Decimal(str(ma5)),
        ma10=Decimal(str(ma10)),
        ma20=Decimal(str(ma20)),
    )


def _valid_six_bars() -> list[SimpleNamespace]:
    """信号日 i=4：s1,s2,s3<0，s4>0；当日 MA5>MA10>MA20；次日 i=5 开盘买。"""
    d0 = date(2026, 6, 2)
    # ma60: 100, 99.5, 99.3, 99.25, 99.35 -> slopes at 1..4
    return [
        _bar(d0, o=10, c=10, ma60=100.0, ma5=9, ma10=9, ma20=9),
        _bar(d0 + timedelta(days=1), o=10, c=10, ma60=99.5, ma5=9, ma10=9, ma20=9),
        _bar(d0 + timedelta(days=2), o=10, c=10, ma60=99.3, ma5=9, ma10=9, ma20=9),
        _bar(d0 + timedelta(days=3), o=10, c=10, ma60=99.25, ma5=9, ma10=9, ma20=9),
        _bar(d0 + timedelta(days=4), o=10, c=10, ma60=99.35, ma5=11.0, ma10=10.0, ma20=9.0),
        _bar(d0 + timedelta(days=5), o=10.5, c=10.2, ma60=99.4, ma5=11, ma10=10, ma20=9),
    ]


def test_signal_ok_basic() -> None:
    bars = _valid_six_bars()
    assert ma60_signal_next_open_ok(bars, 4)


def test_signal_fails_if_day_minus1_slope_not_negative() -> None:
    """使 s(i−1) 即 s(3) 非负，破坏「前 3 日斜率为负」。"""
    bars = _valid_six_bars()
    b = bars[3]
    bars[3] = SimpleNamespace(
        trade_date=b.trade_date,
        open=b.open,
        close=b.close,
        ma60=Decimal("99.35"),
        ma5=b.ma5,
        ma10=b.ma10,
        ma20=b.ma20,
    )
    assert not ma60_signal_next_open_ok(bars, 4)


def test_signal_fails_if_not_ma_bull() -> None:
    bars = _valid_six_bars()
    b = bars[4]
    bars[4] = SimpleNamespace(
        trade_date=b.trade_date,
        open=b.open,
        close=b.close,
        ma60=b.ma60,
        ma5=Decimal("9"),
        ma10=Decimal("10"),
        ma20=Decimal("11"),
    )
    assert not ma60_signal_next_open_ok(bars, 4)


def test_signal_requires_room_for_next_bar() -> None:
    bars = _valid_six_bars()[:5]
    assert not ma60_signal_next_open_ok(bars, 4)


def test_simulate_exit_stop_loss_first_day() -> None:
    p = _Params()
    d0 = date(2026, 3, 1)
    bars = [
        _bar(d0, o=10, c=100, ma60=50, ma5=1, ma10=1, ma20=1),
        _bar(d0 + timedelta(days=1), o=10, c=91.99, ma60=50.1, ma5=1, ma10=1, ma20=1),
    ]
    j, px, reason = simulate_exit_close_only(bars, 0, 100.0, p)
    assert j == 1 and reason == "stop_loss_8pct"


def test_simulate_exit_take_profit() -> None:
    p = _Params()
    d0 = date(2026, 3, 10)
    bars = [
        _bar(d0, o=10, c=100, ma60=50, ma5=1, ma10=1, ma20=1),
        _bar(d0 + timedelta(days=1), o=10, c=100.5, ma60=50.1, ma5=1, ma10=1, ma20=1),
        _bar(d0 + timedelta(days=2), o=10, c=115, ma60=50.2, ma5=1, ma10=1, ma20=1),
    ]
    j, px, reason = simulate_exit_close_only(bars, 0, 100.0, p)
    assert j == 2 and reason == "take_profit_15pct"


def test_simulate_exit_unclosed() -> None:
    p = _Params()
    d0 = date(2026, 5, 1)
    bars = [
        _bar(d0, o=10, c=100, ma60=50, ma5=1, ma10=1, ma20=1),
        _bar(d0 + timedelta(days=1), o=10, c=100.5, ma60=50.1, ma5=1, ma10=1, ma20=1),
    ]
    assert simulate_exit_close_only(bars, 0, 100.0, p) == (None, None, None)
