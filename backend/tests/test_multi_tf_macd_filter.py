"""multi_tf_macd_filter 单元测试。"""

from datetime import date

from app.services.multi_tf_macd_filter import (
    build_period_hist_index,
    codes_with_multi_tf_macd_red,
    latest_hist_leq,
    macd_red_streak_days,
    macd_red_streak_days_by_code,
)


class _Row:
    def __init__(self, stock_code: str, end, macd_hist: float, *, end_attr: str = "trade_week_end"):
        self.stock_code = stock_code
        setattr(self, end_attr, end)
        self.macd_hist = macd_hist


def test_latest_hist_leq_picks_last_bar_on_or_before_as_of():
    series = [(date(2024, 1, 5), 0.1), (date(2024, 1, 12), -0.2), (date(2024, 1, 19), 0.3)]
    assert latest_hist_leq(series, date(2024, 1, 10)) == 0.1
    assert latest_hist_leq(series, date(2024, 1, 19)) == 0.3
    assert latest_hist_leq(series, date(2024, 1, 4)) is None


def test_codes_with_multi_tf_macd_red():
    weekly = build_period_hist_index(
        [_Row("000001.SZ", date(2024, 1, 5), 0.1), _Row("000002.SZ", date(2024, 1, 5), -0.1)],
        end_attr="trade_week_end",
    )
    monthly = build_period_hist_index(
        [
            _Row("000001.SZ", date(2024, 1, 10), 0.2, end_attr="trade_month_end"),
            _Row("000002.SZ", date(2024, 1, 10), 0.2, end_attr="trade_month_end"),
        ],
        end_attr="trade_month_end",
    )
    as_of = date(2024, 1, 15)
    ok = codes_with_multi_tf_macd_red(weekly, monthly, ["000001.SZ", "000002.SZ"], as_of)
    assert ok == {"000001.SZ"}


def test_macd_red_streak_days_from_last_green():
    as_of = date(2024, 1, 10)
    series = [
        (date(2024, 1, 5), -0.1),
        (date(2024, 1, 8), 0.01),
        (date(2024, 1, 9), 0.02),
        (date(2024, 1, 10), 0.03),
    ]
    assert macd_red_streak_days(series, as_of) == 3


def test_macd_red_streak_days_stops_at_green():
    as_of = date(2024, 1, 10)
    series = [
        (date(2024, 1, 8), 0.01),
        (date(2024, 1, 9), -0.01),
        (date(2024, 1, 10), 0.02),
    ]
    assert macd_red_streak_days(series, as_of) == 1


def test_macd_red_streak_days_by_code():
    as_of = date(2024, 1, 10)
    daily = {
        "A": [(date(2024, 1, 9), 0.1), (date(2024, 1, 10), 0.2)],
        "B": [(date(2024, 1, 8), 0.1), (date(2024, 1, 9), 0.1), (date(2024, 1, 10), 0.1)],
    }
    got = macd_red_streak_days_by_code(daily, ["A", "B"], as_of)
    assert got == {"A": 2, "B": 3}
