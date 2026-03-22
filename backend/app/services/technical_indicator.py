"""均线（SMA）与 MACD（12/26/9）纯计算，与 specs/006-技术指标扩展/data-model.md 一致。"""

from __future__ import annotations

import pandas as pd

# 与 pandas ewm(span=n, adjust=False) 一致，便于与主流行情软件对齐


def compute_ma_macd_from_close(close: pd.Series) -> pd.DataFrame:
    """
    对收盘价序列计算 SMA5/10/20/60 与 MACD。

    均线在**本序列内**滚动：不要求库中存在「最早一根 K 线之前」的历史。
    例如 MA60 需满 60 根有效收盘——前 59 根位置为 NaN，第 60 根起为前 60 根收盘的均值；
    周/月周期同理为「前 59 根周/月 K 无 ma60」，而非日历上的「60 个自然日」。

    :param close: 按时间升序；可为 float 或可转数值；缺失为 NaN
    :return: 与 close 等长的 DataFrame，列名 ma5, ma10, ma20, ma60, macd_dif, macd_dea, macd_hist
    """
    s = pd.to_numeric(close, errors="coerce").astype(float)
    ma5 = s.rolling(5, min_periods=5).mean()
    ma10 = s.rolling(10, min_periods=10).mean()
    ma20 = s.rolling(20, min_periods=20).mean()
    ma60 = s.rolling(60, min_periods=60).mean()
    ema12 = s.ewm(span=12, adjust=False).mean()
    ema26 = s.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    hist = 2 * (dif - dea)
    return pd.DataFrame(
        {
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "ma60": ma60,
            "macd_dif": dif,
            "macd_dea": dea,
            "macd_hist": hist,
        }
    )
