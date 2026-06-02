"""多周期 MACD 共振主升浪 — 买入窗口与平仓逻辑单测。"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services.strategy.strategies.duo_zhou_qi_macd_gong_zhen import (
    _Params,
    gain_filter_ok,
    latest_hist_leq,
    multi_tf_macd_red,
    simulate_exit_after_buy,
    six_increasing_red_ends_at,
)


def _bar(
    d: date,
    *,
    open_: float,
    close: float,
    hist: float,
) -> SimpleNamespace:
    return SimpleNamespace(
        trade_date=d,
        open=open_,
        close=close,
        macd_hist=hist,
    )


def test_six_increasing_red_happy() -> None:
    # D0 绿，D1..D6 红且递增
    bars = [
        _bar(date(2024, 1, 1), open_=10, close=10, hist=-0.1),  # D0
        _bar(date(2024, 1, 2), open_=10, close=10.5, hist=0.1),
        _bar(date(2024, 1, 3), open_=10.5, close=11, hist=0.2),
        _bar(date(2024, 1, 4), open_=11, close=11.5, hist=0.3),
        _bar(date(2024, 1, 5), open_=11.5, close=12, hist=0.4),
        _bar(date(2024, 1, 8), open_=12, close=12.5, hist=0.5),
        _bar(date(2024, 1, 9), open_=12.5, close=13, hist=0.6),  # D6 i=6
    ]
    assert six_increasing_red_ends_at(bars, 6) is True


def test_six_increasing_fail_not_green_d0() -> None:
    bars = [
        _bar(date(2024, 1, 1), open_=10, close=10, hist=0.05),  # D0 仍为红
        _bar(date(2024, 1, 2), open_=10, close=10.5, hist=0.1),
        _bar(date(2024, 1, 3), open_=10.5, close=11, hist=0.2),
        _bar(date(2024, 1, 4), open_=11, close=11.5, hist=0.3),
        _bar(date(2024, 1, 5), open_=11.5, close=12, hist=0.4),
        _bar(date(2024, 1, 8), open_=12, close=12.5, hist=0.5),
        _bar(date(2024, 1, 9), open_=12.5, close=13, hist=0.6),
    ]
    assert six_increasing_red_ends_at(bars, 6) is False


def test_six_increasing_only_five_reds() -> None:
    bars = [
        _bar(date(2024, 1, 1), open_=10, close=10, hist=-0.1),
        _bar(date(2024, 1, 2), open_=10, close=10.5, hist=0.1),
        _bar(date(2024, 1, 3), open_=10.5, close=11, hist=0.2),
        _bar(date(2024, 1, 4), open_=11, close=11.5, hist=0.3),
        _bar(date(2024, 1, 5), open_=11.5, close=12, hist=0.4),
        _bar(date(2024, 1, 8), open_=12, close=12.5, hist=0.5),
    ]
    assert six_increasing_red_ends_at(bars, 5) is False


def test_gain_filter_boundary() -> None:
    bars = [
        _bar(date(2024, 1, 1), open_=10, close=10, hist=-0.1),
        _bar(date(2024, 1, 2), open_=10, close=10, hist=0.1),  # D1 open=10
        _bar(date(2024, 1, 3), open_=10, close=10, hist=0.2),
        _bar(date(2024, 1, 4), open_=10, close=10, hist=0.3),
        _bar(date(2024, 1, 5), open_=10, close=10, hist=0.4),
        _bar(date(2024, 1, 8), open_=10, close=10, hist=0.5),
        _bar(date(2024, 1, 9), open_=10, close=11.0, hist=0.6),  # exactly +10%
    ]
    assert gain_filter_ok(bars, 6, gain_filter_pct=0.10) is True


def test_exit_stop_loss_before_macd() -> None:
    p = _Params()
    buy = 100.0
    bars = [
        _bar(date(2024, 1, 9), open_=100, close=100, hist=0.6),
        _bar(date(2024, 1, 10), open_=100, close=92.0, hist=-0.1),  # -8% & 红转绿
    ]
    j, px, reason = simulate_exit_after_buy(bars, 0, buy, date(2024, 12, 31), p)
    assert j == 1
    assert reason == "stop_loss_7pct"
    assert px == 92.0


def test_exit_macd_red_to_green_while_profitable_under_10pct() -> None:
    p = _Params()
    buy = 100.0
    bars = [
        _bar(date(2024, 1, 9), open_=100, close=100, hist=0.6),
        _bar(date(2024, 1, 10), open_=100, close=105.0, hist=-0.01),  # +5%, 未满 10%
    ]
    j, px, reason = simulate_exit_after_buy(bars, 0, buy, date(2024, 12, 31), p)
    assert j == 1
    assert reason == "sell_macd_red_to_green"
    assert px == 105.0


def test_exit_trailing_only_after_arm() -> None:
    p = _Params()
    buy = 100.0
    bars = [
        _bar(date(2024, 1, 9), open_=100, close=100, hist=0.6),
        _bar(date(2024, 1, 10), open_=100, close=95.0, hist=0.5),  # -5%, 未武装
    ]
    j, _, reason = simulate_exit_after_buy(bars, 0, buy, date(2024, 12, 31), p)
    assert j is None and reason is None


def test_exit_three_down_days() -> None:
    p = _Params()
    buy = 100.0
    bars = [
        _bar(date(2024, 1, 9), open_=100, close=100, hist=0.6),
        _bar(date(2024, 1, 10), open_=100, close=99, hist=0.55),
        _bar(date(2024, 1, 11), open_=99, close=98, hist=0.5),
        _bar(date(2024, 1, 12), open_=98, close=97, hist=0.45),
    ]
    j, px, reason = simulate_exit_after_buy(bars, 0, buy, date(2024, 12, 31), p)
    assert j == 3
    assert reason == "sell_three_down_days"
    assert px == 97.0


def test_multi_tf_weekly_missing() -> None:
    weekly: dict[str, list[tuple[date, float]]] = {}
    monthly = {"000001": [(date(2024, 1, 31), 0.2)]}
    assert multi_tf_macd_red(weekly, monthly, "000001", date(2024, 1, 9)) is False


def test_latest_hist_leq() -> None:
    series = [(date(2024, 1, 5), 0.1), (date(2024, 1, 12), 0.2)]
    assert latest_hist_leq(series, date(2024, 1, 10)) == 0.1
    assert latest_hist_leq(series, date(2024, 1, 12)) == 0.2
    assert latest_hist_leq(series, date(2024, 1, 1)) is None
