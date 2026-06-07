"""月 MACD 翻红 — 买入窗口与平仓逻辑单测。"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services.strategy.strategies.yue_macd_fan_hong import (
    _Params,
    build_month_last_trade_dates,
    is_last_trading_day_of_month,
    monthly_green_to_red_at_as_of,
    is_first_red_month_pick_at_as_of,
    monthly_green_to_red_pairs,
    monthly_red_to_green_at,
    simulate_exit_after_buy,
)


def _bar(d: date, *, close: float) -> SimpleNamespace:
    return SimpleNamespace(trade_date=d, close=close)


def test_monthly_green_to_red_detect() -> None:
    series = [
        (date(2024, 1, 31), -0.1),
        (date(2024, 2, 29), 0.2),
    ]
    pairs = monthly_green_to_red_pairs(series)
    assert pairs == [(0, 1)]


def test_no_buy_missing_prev_month() -> None:
    series = [(date(2024, 1, 31), 0.2)]
    assert monthly_green_to_red_pairs(series) == []


def test_buy_on_month_last_trade_day() -> None:
    series = [
        (date(2024, 1, 31), -0.1),
        (date(2024, 2, 29), 0.2),
    ]
    bars = [
        _bar(date(2024, 2, 26), close=10.0),
        _bar(date(2024, 2, 27), close=10.1),
        _bar(date(2024, 2, 28), close=10.2),
        _bar(date(2024, 2, 29), close=10.3),
    ]
    month_last = build_month_last_trade_dates(bars, series)
    assert month_last[date(2024, 2, 29)] == date(2024, 2, 29)
    # 2 月 26–28 对齐到 1 月 bar（trade_month_end≤D 的最近一根为 1/31）
    assert month_last[date(2024, 1, 31)] == date(2024, 2, 28)


def test_exit_take_profit_20() -> None:
    buy_idx = 0
    buy_price = 10.0
    bars = [
        _bar(date(2024, 3, 1), close=10.0),
        _bar(date(2024, 3, 4), close=12.0),
    ]
    monthly = [
        (date(2024, 2, 29), 0.2),
        (date(2024, 3, 31), 0.3),
    ]
    month_last = build_month_last_trade_dates(bars, monthly)
    j, px, reason = simulate_exit_after_buy(
        bars,
        buy_idx,
        buy_price,
        date(2024, 12, 31),
        monthly,
        date(2024, 2, 29),
        month_last,
        _Params(),
    )
    assert j == 1
    assert px == 12.0
    assert reason == "take_profit_20pct"


def test_exit_stop_loss_20() -> None:
    buy_idx = 0
    buy_price = 10.0
    bars = [
        _bar(date(2024, 3, 1), close=10.0),
        _bar(date(2024, 3, 4), close=7.9),
    ]
    monthly = [
        (date(2024, 2, 29), 0.2),
        (date(2024, 3, 31), 0.3),
    ]
    month_last = build_month_last_trade_dates(bars, monthly)
    j, px, reason = simulate_exit_after_buy(
        bars,
        buy_idx,
        buy_price,
        date(2024, 12, 31),
        monthly,
        date(2024, 2, 29),
        month_last,
        _Params(),
    )
    assert j == 1
    assert px == 7.9
    assert reason == "stop_loss_20pct"


def test_exit_monthly_red_to_green() -> None:
    buy_idx = 0
    buy_price = 10.0
    monthly = [
        (date(2024, 1, 31), -0.1),
        (date(2024, 2, 29), 0.2),
        (date(2024, 3, 31), 0.3),
        (date(2024, 4, 30), -0.05),
    ]
    bars = [
        _bar(date(2024, 2, 29), close=10.0),
        _bar(date(2024, 3, 15), close=10.5),
        _bar(date(2024, 3, 29), close=10.4),
        _bar(date(2024, 4, 30), close=10.2),
    ]
    month_last = build_month_last_trade_dates(bars, monthly)
    assert monthly_red_to_green_at(monthly, date(2024, 4, 30)) is True
    j, px, reason = simulate_exit_after_buy(
        bars,
        buy_idx,
        buy_price,
        date(2024, 12, 31),
        monthly,
        date(2024, 2, 29),
        month_last,
        _Params(),
    )
    assert j == 3
    assert px == 10.2
    assert reason == "sell_monthly_macd_red_to_green"


def test_exit_priority_loss_before_macd_green() -> None:
    """同日 −20% 与月线红转绿 → 记 stop_loss_20pct。"""
    buy_idx = 0
    buy_price = 10.0
    monthly = [
        (date(2024, 2, 29), 0.2),
        (date(2024, 3, 31), -0.1),
    ]
    bars = [
        _bar(date(2024, 2, 29), close=10.0),
        _bar(date(2024, 3, 29), close=8.0),
    ]
    month_last = build_month_last_trade_dates(bars, monthly)
    j, _, reason = simulate_exit_after_buy(
        bars,
        buy_idx,
        buy_price,
        date(2024, 12, 31),
        monthly,
        date(2024, 2, 29),
        month_last,
        _Params(),
    )
    assert j == 1
    assert reason == "stop_loss_20pct"


def test_no_macd_sell_in_buy_month() -> None:
    """买入月之后的月末才判 MACD 红转绿。"""
    monthly = [
        (date(2024, 1, 31), -0.1),
        (date(2024, 2, 29), 0.2),
    ]
    bars = [
        _bar(date(2024, 2, 28), close=10.0),
        _bar(date(2024, 2, 29), close=10.0),
    ]
    month_last = build_month_last_trade_dates(bars, monthly)
    assert is_last_trading_day_of_month(date(2024, 2, 29), month_last, monthly) is True
    j, _, reason = simulate_exit_after_buy(
        bars,
        1,
        10.0,
        date(2024, 12, 31),
        monthly,
        date(2024, 2, 29),
        month_last,
        _Params(),
    )
    assert j is None
    assert reason is None


def test_monthly_red_to_green_requires_prev_red() -> None:
    series = [
        (date(2024, 1, 31), -0.1),
        (date(2024, 2, 29), -0.05),
    ]
    assert monthly_red_to_green_at(series, date(2024, 2, 29)) is False


def test_monthly_green_to_red_at_as_of_happy() -> None:
    series = [
        (date(2024, 1, 31), -0.1),
        (date(2024, 2, 29), 0.2),
        (date(2024, 3, 31), 0.3),
    ]
    r = is_first_red_month_pick_at_as_of(series, date(2024, 2, 29))
    assert r is not None
    assert r[0] == date(2024, 1, 31)
    assert r[2] == date(2024, 2, 29)


def test_monthly_green_to_red_at_as_of_before_bar_lands() -> None:
    series = [
        (date(2024, 1, 31), -0.1),
        (date(2024, 2, 29), 0.2),
    ]
    assert is_first_red_month_pick_at_as_of(series, date(2024, 2, 15)) is None


def test_monthly_green_to_red_at_as_of_fail_prev_still_red() -> None:
    series = [
        (date(2024, 1, 31), 0.1),
        (date(2024, 2, 29), 0.2),
    ]
    assert monthly_green_to_red_at_as_of(series, date(2024, 2, 15)) is None


def test_monthly_green_to_red_at_as_of_after_next_month() -> None:
    """进入次自然月后，不再视为首红柱月选股。"""
    series = [
        (date(2024, 1, 31), -0.1),
        (date(2024, 2, 29), 0.2),
        (date(2024, 3, 31), 0.25),
    ]
    assert is_first_red_month_pick_at_as_of(series, date(2024, 3, 15)) is None
