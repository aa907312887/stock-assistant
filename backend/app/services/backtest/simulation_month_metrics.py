"""历史模拟：买入后固定自然日窗口内的观察指标（用于明细列与任务汇总）。

口径：
- 窗口：买入日起连续 30 个自然日（含买入当日），仅统计窗口内有收盘价样本的交易日序列。
- 目标涨幅 / 止损线：相对买入价的收盘价比率阈值（默认与破 60 日均线法一致为 ±8%），可按 strategy_id 配置。
- 「经典最大回撤」：在窗口内按收盘价做 running peak，取各日 (close/peak-1) 的最小值（一般为负）。
- 交易结果类型 a/b/c/d（写入 `extra_json.month_path_kind`）：均以买入价为锚，在窗口内比较「首次触及止损收盘价」与「首次触及目标收盘价」的日期先后。
  - **a**：两类阈值都曾可达到，且**首次触及止损早于首次达标**（之后窗口内仍可能再次收涨至目标）。
  - **b**：首次达标早于止损；或仅达标而未触及止损收盘价。
  - **c**：曾触及止损收盘价，且窗口内从未出现达标收盘价。
  - **d**：窗口内两类阈值均未触及；或无足够收盘价样本（`month_data_ok=false` 时亦为 d）。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.stock_daily_bar import StockDailyBar
from app.models.simulation_trade import SimulationTrade as SimulationTradeModel


# (目标涨幅比例, 止损比例)，均为相对买入价的收盘价阈值
_MONTH_THRESHOLDS_BY_STRATEGY: dict[str, tuple[float, float]] = {
    "ma60_five_day_break": (0.08, 0.08),
}


def get_month_thresholds_for_strategy(strategy_id: str) -> tuple[float, float]:
    """返回 (take_profit_ratio, stop_loss_ratio)，如 (0.08, 0.08)。"""
    return _MONTH_THRESHOLDS_BY_STRATEGY.get(strategy_id, (0.08, 0.08))


def compute_month_window_metrics(
    *,
    window_bars: list[tuple[date, float]],
    buy_price: float,
    gain_threshold_pct: float,
    stop_threshold_pct: float,
) -> dict[str, Any]:
    """根据窗口内（按日期升序）的收盘价序列计算单月观察指标。"""
    out: dict[str, Any] = {
        "month_window_calendar_days": 30,
        "month_gain_threshold_pct": gain_threshold_pct,
        "month_stop_threshold_pct": stop_threshold_pct,
        "month_data_ok": False,
        "month_target_met": False,
        "month_classic_max_drawdown_pct": None,
        "month_max_gain_pct": None,
        "month_stop_line_hit": False,
        "month_path_kind": None,
    }
    if buy_price <= 0 or not window_bars:
        out["month_path_kind"] = "d"
        return out

    tp_price = buy_price * (1.0 + gain_threshold_pct)
    sl_price = buy_price * (1.0 - stop_threshold_pct)

    first_tp_date: date | None = None
    first_sl_date: date | None = None
    for d, c in window_bars:
        if first_tp_date is None and c >= tp_price:
            first_tp_date = d
        if first_sl_date is None and c <= sl_price:
            first_sl_date = d

    if first_tp_date is not None and first_sl_date is not None:
        if first_tp_date < first_sl_date:
            kind = "b"
        elif first_sl_date < first_tp_date:
            kind = "a"
        else:
            kind = "b"
    elif first_tp_date is not None:
        kind = "b"
    elif first_sl_date is not None:
        kind = "c"
    else:
        kind = "d"

    peak = window_bars[0][1]
    min_dd = 0.0
    for _, c in window_bars:
        peak = max(peak, c)
        if peak > 0:
            dd = (c - peak) / peak
            min_dd = min(min_dd, dd)

    max_gain = max(c / buy_price - 1.0 for _, c in window_bars)
    target_met = any(c >= tp_price for _, c in window_bars)
    stop_hit = any(c <= sl_price for _, c in window_bars)

    out["month_data_ok"] = True
    out["month_target_met"] = target_met
    out["month_classic_max_drawdown_pct"] = float(min_dd)
    out["month_max_gain_pct"] = float(max_gain)
    out["month_stop_line_hit"] = stop_hit
    out["month_path_kind"] = kind
    return out


def _window_slice(
    bars: list[tuple[date, float]],
    buy_date: date,
    end_inclusive: date,
) -> list[tuple[date, float]]:
    return [(d, c) for d, c in bars if buy_date <= d <= end_inclusive]


def enrich_task_trades_month_window(
    db: Session,
    *,
    task_id: str,
    strategy_id: str,
) -> dict[str, Any]:
    """为任务下已平仓交易补充 extra_json 中的首月观察字段，并返回汇总结构供写入 assumptions_json。"""
    gain_th, stop_th = get_month_thresholds_for_strategy(strategy_id)
    rows = (
        db.query(SimulationTradeModel)
        .filter(
            SimulationTradeModel.task_id == task_id,
            SimulationTradeModel.trade_type == "closed",
        )
        .all()
    )
    empty_summary: dict[str, Any] = {
        "window_calendar_days": 30,
        "gain_threshold_pct": gain_th,
        "stop_threshold_pct": stop_th,
        "ignore_volatility_success_ratio": 0.0,
        "worst_single_mdd_pct": 0.0,
        "avg_mdd_pct": 0.0,
        "path_a_count": 0,
        "path_b_count": 0,
        "path_c_count": 0,
        "path_d_count": 0,
        "path_a_ratio": 0.0,
        "path_b_ratio": 0.0,
        "path_c_ratio": 0.0,
        "path_d_ratio": 0.0,
        "trades_with_metrics": 0,
    }
    if not rows:
        return {"month_window_stats": empty_summary}

    by_code: dict[str, list[SimulationTradeModel]] = defaultdict(list)
    for r in rows:
        by_code[r.stock_code].append(r)

    code_bars: dict[str, list[tuple[date, float]]] = {}
    for code, rlist in by_code.items():
        min_buy = min(x.buy_date for x in rlist)
        max_end = max(x.buy_date + timedelta(days=29) for x in rlist)
        stmt = (
            select(StockDailyBar.trade_date, StockDailyBar.close)
            .where(
                StockDailyBar.stock_code == code,
                StockDailyBar.trade_date >= min_buy,
                StockDailyBar.trade_date <= max_end,
                StockDailyBar.close.isnot(None),
            )
            .order_by(StockDailyBar.trade_date)
        )
        raw = list(db.execute(stmt).all())
        code_bars[code] = [(d, float(c)) for d, c in raw]

    path_counts = {"a": 0, "b": 0, "c": 0, "d": 0}
    mdd_list: list[float] = []
    target_met_count = 0

    for r in rows:
        bars = code_bars.get(r.stock_code, [])
        buy_date = r.buy_date
        end_date = buy_date + timedelta(days=29)
        window = _window_slice(bars, buy_date, end_date)
        metrics = compute_month_window_metrics(
            window_bars=window,
            buy_price=float(r.buy_price),
            gain_threshold_pct=gain_th,
            stop_threshold_pct=stop_th,
        )
        extra = dict(r.extra_json or {})
        extra.update(metrics)
        r.extra_json = extra

        pk = metrics.get("month_path_kind")
        if isinstance(pk, str) and pk in path_counts:
            path_counts[pk] += 1

        if metrics.get("month_data_ok"):
            mdd = metrics.get("month_classic_max_drawdown_pct")
            if isinstance(mdd, (int, float)):
                mdd_list.append(float(mdd))
            if metrics.get("month_target_met"):
                target_met_count += 1

    n = len(rows)
    # 不考虑中途下跌成功率：分子为窗口内曾达标（收盘价）的笔数，分母为任务内已平仓笔数（闭仓总数）
    ratio_met = (target_met_count / n) if n else 0.0
    worst_mdd = min(mdd_list) if mdd_list else 0.0
    avg_mdd = (sum(mdd_list) / len(mdd_list)) if mdd_list else 0.0

    def _pc(k: str) -> int:
        return int(path_counts.get(k, 0))

    summary = {
        "window_calendar_days": 30,
        "gain_threshold_pct": gain_th,
        "stop_threshold_pct": stop_th,
        "ignore_volatility_success_ratio": round(float(ratio_met), 6),
        "worst_single_mdd_pct": round(float(worst_mdd), 6),
        "avg_mdd_pct": round(float(avg_mdd), 6),
        "path_a_count": _pc("a"),
        "path_b_count": _pc("b"),
        "path_c_count": _pc("c"),
        "path_d_count": _pc("d"),
        "path_a_ratio": round(_pc("a") / n, 6) if n else 0.0,
        "path_b_ratio": round(_pc("b") / n, 6) if n else 0.0,
        "path_c_ratio": round(_pc("c") / n, 6) if n else 0.0,
        "path_d_ratio": round(_pc("d") / n, 6) if n else 0.0,
        "trades_with_metrics": n,
    }
    return {"month_window_stats": summary}
