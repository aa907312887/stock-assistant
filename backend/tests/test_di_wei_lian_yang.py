"""红三兵（strategy_id=di_wei_lian_yang）：形态判定与卖出仿真单测。"""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.services.strategy.strategies.di_wei_lian_yang import (
    _Params,
    _simulate_exit_after_buy,
    _yang_body_and_small_shadows,
    price_not_too_high,
    red_three_soldiers_pattern_ok,
    third_day_volume_vs_prior5_ok,
)


def _bar(
    d: date,
    *,
    o: float,
    h: float,
    l: float,
    c: float,
    v: float = 1e6,
    cum: float = 100.0,
    ma60: float | None = 50.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        trade_date=d,
        open=o,
        high=h,
        low=l,
        close=c,
        volume=v,
        cum_hist_high=cum,
        ma60=ma60,
        ma5=1.0,
        ma10=1.0,
        ma20=1.0,
    )


def test_red_three_pattern_ok() -> None:
    p = _Params()
    d0 = date(2026, 3, 1)
    # 实体约 1.2%～1.3%，影线占振幅比例均 < 25%
    bars = [
        _bar(d0, o=10.0, h=10.14, l=9.996, c=10.12, v=1e6, cum=30.0, ma60=12.0),
        _bar(d0 + timedelta(days=1), o=10.12, h=10.26, l=10.118, c=10.25, v=1e6, cum=30.0, ma60=12.0),
        _bar(d0 + timedelta(days=2), o=10.25, h=10.40, l=10.248, c=10.38, v=2e6, cum=30.0, ma60=12.0),
    ]
    assert red_three_soldiers_pattern_ok(bars, 2, p)


def test_red_three_fails_if_open_gap_up_over_1pct() -> None:
    p = _Params()
    d0 = date(2026, 3, 10)
    # 前两根合法，第三根开盘相对 T-1 收盘高开 >1%
    bars = [
        _bar(d0, o=10.0, h=10.14, l=9.996, c=10.12),
        _bar(d0 + timedelta(days=1), o=10.12, h=10.26, l=10.118, c=10.25),
        _bar(
            d0 + timedelta(days=2),
            o=10.25 * 1.011,
            h=10.52,
            l=10.355,
            c=10.48,
        ),
    ]
    assert not red_three_soldiers_pattern_ok(bars, 2, p)


def test_red_three_fails_if_close_not_rising() -> None:
    p = _Params()
    d0 = date(2026, 3, 1)
    bars = [
        _bar(d0, o=10.0, h=10.14, l=9.996, c=10.12),
        _bar(d0 + timedelta(days=1), o=10.12, h=10.26, l=10.118, c=10.25),
        _bar(d0 + timedelta(days=2), o=10.25, h=10.40, l=10.248, c=10.24),
    ]
    assert not red_three_soldiers_pattern_ok(bars, 2, p)


def test_yang_body_fails_below_1pct() -> None:
    p = _Params()
    assert not _yang_body_and_small_shadows(10.0, 10.08, 9.99, 10.05, p)


def test_yang_body_fails_long_upper_shadow() -> None:
    p = _Params()
    # 实体约 2%，上影线占振幅超过 25%
    assert not _yang_body_and_small_shadows(10.0, 10.5, 9.99, 10.2, p)


def test_price_not_too_high_ma60() -> None:
    p = _Params()
    b = SimpleNamespace(close=14.0, cum_hist_high=30.0, ma60=15.0)
    assert price_not_too_high(b, p)
    b2 = SimpleNamespace(close=14.6, cum_hist_high=30.0, ma60=14.5)
    assert not price_not_too_high(b2, p)


def test_third_day_volume_ok() -> None:
    p = _Params()
    d0 = date(2026, 4, 1)
    base_v = 1_000_000.0
    bars = []
    for k in range(8):
        bars.append(
            _bar(
                d0 + timedelta(days=k),
                o=10,
                h=10.2,
                l=9.9,
                c=10.05,
                v=base_v,
                cum=100.0,
                ma60=50.0,
            )
        )
    # i=7 为第三根阳；前 5 根 j∈[0,4] 均量 base_v；第三根量 1.2e6 ≥ 1.1e6
    bars[5] = _bar(d0 + timedelta(days=5), o=10.0, h=10.14, l=9.996, c=10.12, v=base_v, cum=100.0, ma60=50.0)
    bars[6] = _bar(d0 + timedelta(days=6), o=10.12, h=10.26, l=10.118, c=10.25, v=base_v, cum=100.0, ma60=50.0)
    bars[7] = _bar(
        d0 + timedelta(days=7),
        o=10.25,
        h=10.40,
        l=10.248,
        c=10.38,
        v=1_200_000.0,
        cum=100.0,
        ma60=50.0,
    )
    assert third_day_volume_vs_prior5_ok(bars, 7, p)


def _bar_exit(d: date, *, o: float, h: float, l: float, c: float) -> SimpleNamespace:
    return SimpleNamespace(trade_date=d, open=o, high=h, low=l, close=c)


def test_simulate_stop_loss_8pct() -> None:
    p = _Params()
    d0 = date(2026, 1, 5)
    bars = [
        _bar_exit(d0, o=100, h=101, l=99, c=100),
        _bar_exit(d0 + timedelta(days=1), o=100, h=100, l=90, c=91),
    ]
    sell_idx, reason, _, _ = _simulate_exit_after_buy(bars, 0, 100.0, end_date=d0 + timedelta(days=30), p=p)
    assert sell_idx == 1
    assert reason == "stop_loss_8pct"


def test_simulate_trailing_after_15pct() -> None:
    p = _Params()
    d0 = date(2026, 2, 1)
    bars = [
        _bar_exit(d0, o=100, h=100, l=99, c=100),
        _bar_exit(d0 + timedelta(days=1), o=100, h=118, l=100, c=116),
        _bar_exit(d0 + timedelta(days=2), o=115, h=120, l=113, c=114),
    ]
    sell_idx, reason, high, trailing = _simulate_exit_after_buy(
        bars, 0, 100.0, end_date=d0 + timedelta(days=30), p=p
    )
    assert sell_idx == 2
    assert reason == "trailing_stop_5pct"
    assert high == pytest.approx(120.0)
    assert trailing is True
