"""technical_indicator 黄金样本（pandas ewm adjust=False）。"""

import pandas as pd
import pytest

from app.services.technical_indicator import compute_ma_macd_from_close


def test_sma_ma5_last_value() -> None:
    # 1..10，最后 ma5 = mean(6..10) = 8
    s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float)
    df = compute_ma_macd_from_close(s)
    assert df["ma5"].iloc[-1] == pytest.approx(8.0)


def test_macd_hist_formula() -> None:
    s = pd.Series(range(1, 100), dtype=float)
    df = compute_ma_macd_from_close(s)
    tail = df.iloc[-30:]
    pd.testing.assert_series_equal(
        tail["macd_hist"],
        2 * (tail["macd_dif"] - tail["macd_dea"]),
        check_names=False,
    )


def test_insufficient_history_nan() -> None:
    s = pd.Series([1.0, 2.0, 3.0], dtype=float)
    df = compute_ma_macd_from_close(s)
    assert pd.isna(df["ma60"].iloc[-1])
