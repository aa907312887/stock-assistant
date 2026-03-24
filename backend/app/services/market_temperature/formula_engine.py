"""大盘温度公式计算引擎（v1.0.0）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def _d(v: float) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return (sum((x - m) ** 2 for x in values) / len(values)) ** 0.5


def _rolling_mean(values: list[float], n: int, idx: int) -> float:
    if idx + 1 < n:
        return _mean(values[: idx + 1])
    return _mean(values[idx - n + 1 : idx + 1])


def _percentile_rank(series: list[float], value: float) -> float:
    if not series:
        return 0.5
    less = sum(1 for v in series if v < value)
    eq = sum(1 for v in series if v == value)
    return (less + 0.5 * eq) / len(series)


def calculate_scores_for_dates(quotes_by_code: dict[str, list[dict[str, Any]]]) -> dict[date, dict[str, Decimal | str]]:
    """
    输入：按指数分组、按 trade_date 升序的行情序列。
    输出：按 trade_date 的总分与三因子分项。
    """
    per_code: dict[str, dict[date, dict[str, float]]] = {}
    for code, rows in quotes_by_code.items():
        closes = [float(r["close"]) for r in rows]
        amounts = [float(r.get("amount") or 0) for r in rows]
        vols = [float(r.get("vol") or 0) for r in rows]
        dates = [r["trade_date"] for r in rows]
        values: dict[date, dict[str, float]] = {}
        returns: list[float] = []
        for i, td in enumerate(dates):
            c = closes[i]
            ma20 = _rolling_mean(closes, 20, i)
            ma60 = _rolling_mean(closes, 60, i)
            trend_raw = 0.6 * (c / ma20 - 1 if ma20 else 0) + 0.4 * (ma20 / ma60 - 1 if ma60 else 0)

            amt_ma20 = _rolling_mean(amounts, 20, i)
            vol_ma20 = _rolling_mean(vols, 20, i)
            liq_raw = 0.7 * (amounts[i] / amt_ma20 if amt_ma20 else 0) + 0.3 * (vols[i] / vol_ma20 if vol_ma20 else 0)

            if i > 0 and closes[i - 1] > 0:
                returns.append(c / closes[i - 1] - 1)
            window_returns = returns[max(0, len(returns) - 20) :]
            vol20 = _std(window_returns)
            amp = float((float(rows[i]["high"]) - float(rows[i]["low"])) / c) if c else 0
            risk_raw = 0.7 * vol20 + 0.3 * amp

            values[td] = {"trend_raw": trend_raw, "liq_raw": liq_raw, "risk_raw": risk_raw}
        per_code[code] = values

    all_dates = sorted(set().union(*[set(v.keys()) for v in per_code.values()]))
    trend_series: list[float] = []
    liq_series: list[float] = []
    risk_series: list[float] = []
    out: dict[date, dict[str, Decimal | str]] = {}
    prev_score = 0.0
    for td in all_dates:
        tr = _mean([v[td]["trend_raw"] for v in per_code.values() if td in v])
        lr = _mean([v[td]["liq_raw"] for v in per_code.values() if td in v])
        rr = _mean([v[td]["risk_raw"] for v in per_code.values() if td in v])
        trend_series.append(tr)
        liq_series.append(lr)
        risk_series.append(rr)

        w_tr = trend_series[max(0, len(trend_series) - 756) :]
        w_lq = liq_series[max(0, len(liq_series) - 756) :]
        w_rk = risk_series[max(0, len(risk_series) - 756) :]
        trend_score = _percentile_rank(w_tr, tr) * 100
        liq_score = _percentile_rank(w_lq, lr) * 100
        risk_score = (1 - _percentile_rank(w_rk, rr)) * 100
        total = 0.4 * trend_score + 0.3 * liq_score + 0.3 * risk_score

        delta = total - prev_score
        if delta >= 2:
            trend_flag = "升温"
        elif delta <= -2:
            trend_flag = "降温"
        else:
            trend_flag = "持平"

        out[td] = {
            "trend_score": _d(trend_score),
            "liquidity_score": _d(liq_score),
            "risk_score": _d(risk_score),
            "temperature_score": _d(total),
            "delta_score": _d(delta),
            "trend_flag": trend_flag,
        }
        prev_score = total
    return out


def map_level(score: Decimal) -> str:
    s = float(score)
    if s <= 20:
        return "极冷"
    if s <= 40:
        return "偏冷"
    if s <= 60:
        return "中性"
    if s <= 80:
        return "偏热"
    return "过热"
