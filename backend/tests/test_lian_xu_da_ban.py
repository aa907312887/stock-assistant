"""连续打板 — 买入窗口与平仓逻辑单测。"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services.strategy.strategies.lian_xu_da_ban import (
    _Params,
    buy_signal_at,
    is_first_board_pick,
    is_green_to_red,
    is_limit_up_first_board,
    is_limit_up_follow_board,
    is_limit_up_day,
    is_macd_green_to_red_day,
    is_macd_red_to_green_day,
    simulate_exit_after_buy,
)


def _bar(
    d: date,
    *,
    close: float,
    prev_close: float | None = None,
    hist: float = 0.5,
    pct_change: float | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        trade_date=d,
        close=close,
        prev_close=prev_close,
        macd_hist=hist,
        pct_change=pct_change,
    )


def test_limit_up_first_board_requires_10pct() -> None:
    assert is_limit_up_first_board(_bar(date(2024, 1, 2), close=11.0, prev_close=10.0)) is True
    assert is_limit_up_first_board(_bar(date(2024, 1, 2), close=10.99, prev_close=10.0)) is False
    assert is_limit_up_first_board(_bar(date(2024, 1, 2), close=10.0, pct_change=10.0)) is True
    assert is_limit_up_first_board(_bar(date(2024, 1, 2), close=10.0, pct_change=9.99)) is False


def test_limit_up_follow_board_gt_95pct() -> None:
    assert is_limit_up_follow_board(_bar(date(2024, 1, 2), close=10.96, prev_close=10.0)) is True
    assert is_limit_up_follow_board(_bar(date(2024, 1, 2), close=10.95, prev_close=10.0)) is False
    assert is_limit_up_follow_board(_bar(date(2024, 1, 2), close=11.0, prev_close=10.0)) is True


def test_limit_up_day_either_tier() -> None:
    assert is_limit_up_day(_bar(date(2024, 1, 2), close=11.0, prev_close=10.0)) is True
    assert is_limit_up_day(_bar(date(2024, 1, 2), close=10.96, prev_close=10.0)) is True
    assert is_limit_up_day(_bar(date(2024, 1, 2), close=10.5, prev_close=10.0)) is False


def test_macd_green_to_red_pair() -> None:
    prev = _bar(date(2024, 1, 1), close=10, hist=-0.1)
    cur = _bar(date(2024, 1, 2), close=10.5, hist=0.1)
    assert is_macd_green_to_red_day(prev, cur) is True
    assert is_macd_green_to_red_day(cur, prev) is False


def test_first_board_pick_happy() -> None:
    prev = _bar(date(2024, 1, 3), close=10, hist=-0.05)
    today = _bar(date(2024, 1, 4), close=11.0, prev_close=10, hist=0.2)
    assert is_first_board_pick(prev, today) is True


def test_first_board_pick_fail_not_limit_up() -> None:
    prev = _bar(date(2024, 1, 3), close=10, hist=-0.05)
    today = _bar(date(2024, 1, 4), close=10.5, prev_close=10, hist=0.2)
    assert is_first_board_pick(prev, today) is False


def test_first_board_pick_fail_not_green_to_red() -> None:
    prev = _bar(date(2024, 1, 3), close=10, hist=0.1)
    today = _bar(date(2024, 1, 4), close=11.0, prev_close=10, hist=0.2)
    assert is_first_board_pick(prev, today) is False


def test_first_board_pick_fail_only_96pct() -> None:
    """9.6% 仅满足续板，不满足选股首板 10%。"""
    prev = _bar(date(2024, 1, 3), close=10, hist=-0.05)
    today = _bar(date(2024, 1, 4), close=10.96, prev_close=10, hist=0.2)
    assert is_first_board_pick(prev, today) is False


def test_first_board_pick_fail_prev_was_limit() -> None:
    """昨首板、今二板形态（绿转红在二板日）不应入选选股。"""
    prev = _bar(date(2024, 1, 3), close=11.0, prev_close=10, hist=-0.05)
    today = _bar(date(2024, 1, 4), close=12.06, prev_close=11.0, hist=0.2)
    assert is_first_board_pick(prev, today) is False


def test_buy_signal_second_board_96pct_ok() -> None:
    """二板 9.6% 可触发回测，首板仍须 10%。"""
    bars = [
        _bar(date(2024, 1, 1), close=10, prev_close=9.5, hist=-0.1),
        _bar(date(2024, 1, 2), close=10, prev_close=10, hist=-0.05),
        _bar(date(2024, 1, 3), close=10.5, prev_close=10, hist=0.1),
        _bar(date(2024, 1, 4), close=11.55, prev_close=10.5, hist=0.2),
        _bar(date(2024, 1, 5), close=12.66, prev_close=11.55, hist=0.3),
    ]
    ok, _ = buy_signal_at(bars, 4, window_days=2)
    assert ok is True


def test_buy_signal_second_board_95pct_fail() -> None:
    bars = [
        _bar(date(2024, 1, 1), close=10, prev_close=9.5, hist=-0.1),
        _bar(date(2024, 1, 2), close=10, prev_close=10, hist=-0.05),
        _bar(date(2024, 1, 3), close=10.5, prev_close=10, hist=0.1),
        _bar(date(2024, 1, 4), close=11.55, prev_close=10.5, hist=0.2),
        _bar(date(2024, 1, 5), close=12.64, prev_close=11.55, hist=0.3),
    ]
    ok, _ = buy_signal_at(bars, 4, window_days=2)
    assert ok is False


def test_green_to_red() -> None:
    bars = [
        _bar(date(2024, 1, 1), close=10, hist=-0.1),
        _bar(date(2024, 1, 2), close=10.5, hist=0.1),
    ]
    assert is_green_to_red(bars, 1) is True
    assert is_green_to_red(bars, 0) is False


def test_buy_signal_happy_g_plus_1_g_plus_2() -> None:
    # G 绿转红；G+1 首板；G+2 二板
    bars = [
        _bar(date(2024, 1, 1), close=10, prev_close=9.5, hist=-0.1),  # 前日
        _bar(date(2024, 1, 2), close=10, prev_close=10, hist=-0.05),  # G-1 绿
        _bar(date(2024, 1, 3), close=10.5, prev_close=10, hist=0.1),  # G 绿转红
        _bar(date(2024, 1, 4), close=11.55, prev_close=10.5, hist=0.2),  # 首板
        _bar(date(2024, 1, 5), close=12.71, prev_close=11.55, hist=0.3),  # 二板 i=4
    ]
    ok, g_idx = buy_signal_at(bars, 4, window_days=2)
    assert ok is True
    assert g_idx == 2


def test_buy_signal_g_is_first_board() -> None:
    # G 绿转红且首板；G+1 二板
    bars = [
        _bar(date(2024, 1, 1), close=10, prev_close=9.5, hist=-0.1),
        _bar(date(2024, 1, 2), close=10, prev_close=10, hist=-0.05),
        _bar(date(2024, 1, 3), close=11.0, prev_close=10, hist=0.1),  # G 首板
        _bar(date(2024, 1, 4), close=12.1, prev_close=11.0, hist=0.2),  # 二板 i=3
    ]
    ok, g_idx = buy_signal_at(bars, 3, window_days=2)
    assert ok is True
    assert g_idx == 2


def test_buy_signal_fail_window_too_late() -> None:
    # G 绿转红；间隔过长，第 4 日才二板
    bars = [
        _bar(date(2024, 1, 1), close=10, prev_close=9.5, hist=-0.1),
        _bar(date(2024, 1, 2), close=10, prev_close=10, hist=-0.05),
        _bar(date(2024, 1, 3), close=10.5, prev_close=10, hist=0.1),  # G
        _bar(date(2024, 1, 4), close=10.6, prev_close=10.5, hist=0.15),
        _bar(date(2024, 1, 5), close=10.7, prev_close=10.6, hist=0.2),
        _bar(date(2024, 1, 8), close=11.77, prev_close=10.7, hist=0.25),  # 首板
        _bar(date(2024, 1, 9), close=12.95, prev_close=11.77, hist=0.3),  # 二板 i=6
    ]
    ok, _ = buy_signal_at(bars, 6, window_days=2)
    assert ok is False


def test_buy_signal_fail_not_consecutive() -> None:
    bars = [
        _bar(date(2024, 1, 1), close=10, prev_close=9.5, hist=-0.1),
        _bar(date(2024, 1, 2), close=10, prev_close=10, hist=-0.05),
        _bar(date(2024, 1, 3), close=11.0, prev_close=10, hist=0.1),
        _bar(date(2024, 1, 4), close=11.1, prev_close=11.0, hist=0.2),  # 非涨停
        _bar(date(2024, 1, 5), close=12.21, prev_close=11.1, hist=0.3),
    ]
    ok, _ = buy_signal_at(bars, 4, window_days=2)
    assert ok is False


def test_exit_trailing_from_peak_5pct() -> None:
    p = _Params()
    buy = 100.0
    bars = [
        _bar(date(2024, 1, 5), close=100, hist=0.3),
        _bar(date(2024, 1, 8), close=120, hist=0.5),
        _bar(date(2024, 1, 9), close=114, hist=0.45),  # peak 120, 114 <= 114
    ]
    j, px, reason = simulate_exit_after_buy(bars, 0, buy, date(2024, 12, 31), p)
    assert j == 2
    assert reason == "trailing_stop_from_peak_5pct"
    assert px == 114.0


def test_exit_trailing_not_from_buy_price_alone() -> None:
    """相对买入价仍盈利，但从峰值回落 5% 仍卖。"""
    p = _Params()
    buy = 100.0
    bars = [
        _bar(date(2024, 1, 5), close=100, hist=0.3),
        _bar(date(2024, 1, 8), close=130, hist=0.5),
        _bar(date(2024, 1, 9), close=123.4, hist=0.45),
    ]
    j, _, reason = simulate_exit_after_buy(bars, 0, buy, date(2024, 12, 31), p)
    assert j == 2
    assert reason == "trailing_stop_from_peak_5pct"


def test_exit_macd_red_to_green() -> None:
    p = _Params()
    buy = 100.0
    bars = [
        _bar(date(2024, 1, 5), close=100, hist=0.3),
        _bar(date(2024, 1, 8), close=105, hist=-0.01),
    ]
    j, px, reason = simulate_exit_after_buy(bars, 0, buy, date(2024, 12, 31), p)
    assert j == 1
    assert reason == "sell_macd_red_to_green"
    assert px == 105.0


def test_exit_macd_before_trailing_same_day() -> None:
    p = _Params()
    buy = 100.0
    bars = [
        _bar(date(2024, 1, 5), close=100, hist=0.3),
        _bar(date(2024, 1, 8), close=114, hist=-0.01),  # 新 peak 114 且红转绿
    ]
    j, _, reason = simulate_exit_after_buy(bars, 0, buy, date(2024, 12, 31), p)
    assert j == 1
    assert reason == "sell_macd_red_to_green"


def test_macd_red_to_green_pair() -> None:
    prev = _bar(date(2024, 1, 1), close=10, hist=0.2)
    cur = _bar(date(2024, 1, 2), close=10, hist=-0.1)
    assert is_macd_red_to_green_day(prev, cur) is True
