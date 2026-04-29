"""首月观察窗口指标纯函数测试（无数据库）。"""

from datetime import date

from app.services.backtest.simulation_month_metrics import compute_month_window_metrics


def test_path_b_target_before_stop():
    # 先涨到目标，后跌到止损
    bars = [
        (date(2024, 1, 2), 100.0),
        (date(2024, 1, 3), 109.0),  # >= 108 tp
        (date(2024, 1, 4), 90.0),  # <= 92 sl
    ]
    m = compute_month_window_metrics(
        window_bars=bars,
        buy_price=100.0,
        gain_threshold_pct=0.08,
        stop_threshold_pct=0.08,
    )
    assert m["month_path_kind"] == "b"
    assert m["month_target_met"] is True
    assert m["month_stop_line_hit"] is True


def test_path_a_stop_before_target():
    bars = [
        (date(2024, 1, 2), 100.0),
        (date(2024, 1, 3), 91.0),  # sl first
        (date(2024, 1, 4), 110.0),
    ]
    m = compute_month_window_metrics(
        window_bars=bars,
        buy_price=100.0,
        gain_threshold_pct=0.08,
        stop_threshold_pct=0.08,
    )
    assert m["month_path_kind"] == "a"
    assert m["month_target_met"] is True


def test_path_c_stop_only():
    bars = [
        (date(2024, 1, 2), 100.0),
        (date(2024, 1, 3), 91.0),
        (date(2024, 1, 4), 95.0),
    ]
    m = compute_month_window_metrics(
        window_bars=bars,
        buy_price=100.0,
        gain_threshold_pct=0.08,
        stop_threshold_pct=0.08,
    )
    assert m["month_path_kind"] == "c"
    assert m["month_target_met"] is False


def test_classic_mdd_negative():
    bars = [
        (date(2024, 1, 2), 100.0),
        (date(2024, 1, 3), 110.0),
        (date(2024, 1, 4), 99.0),
    ]
    m = compute_month_window_metrics(
        window_bars=bars,
        buy_price=100.0,
        gain_threshold_pct=0.08,
        stop_threshold_pct=0.08,
    )
    assert m["month_classic_max_drawdown_pct"] is not None
    assert m["month_classic_max_drawdown_pct"] < 0
    assert abs(m["month_max_gain_pct"] - 0.1) < 1e-9
