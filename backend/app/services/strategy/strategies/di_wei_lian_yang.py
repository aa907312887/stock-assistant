"""
红三兵（内置回测策略，`strategy_id` 仍为 `di_wei_lian_yang` 以兼容既有回测记录）。

【策略名称】：红三兵（低价区 + 温和放量）

【目标】：在**股价相对历史不高**的前提下，识别标准 **红三兵**（三连小阳、收盘逐级抬高、**不跳空高开逾 1%**），
**T+1 日开盘价**买入；卖出与「早晨十字星」一致：8% 固定止损、15% 激活后从最高价回撤 5% 移动止盈。

【适用范围】：A 股日线；剔除 ST/*ST。

【依赖字段】：open、high、low、close、ma60（可选）、cum_hist_high、volume、trade_date。

【核心规则】：
1) **红三兵（完成日 T = 索引 i）**：T−2、T−1、T 均为阳线；每日实体 **min_yang_body_pct ≤ (close−open)/open ≤ max_small_yang_body_pct**（默认每根实体 **≥1%** 且 **≤5%**）；
   **上影线、下影线相对全日振幅**（high−low）占比均 **≤ max_shadow_to_range**（默认各不超过 **25%**）；
   **close_{T−2} < close_{T−1} < close_T**；且 **open_{T−1} ≤ close_{T−2}×(1+max_open_gap_up_pct)**、**open_T ≤ close_{T−1}×(1+max_open_gap_up_pct)**（默认 **1%**，禁止三连阳中出现「相对前收高开逾 1%」的跳空）。
2) **股价不太高**：**close_T ≤ max_close_to_cum_hist_high_ratio × cum_hist_high_T**（默认 50%）；且若 **MA60** 有效则 **close_T < MA60**（中期下方，避免已大幅拉升）。
3) **温和放量（推荐过滤）**：**volume_T ≥ prior_5d_avg_volume × volume_surge_ratio**（默认前 5 日均量 ×1.1；前 5 日指 T−7…T−3 共 5 根）。
4) **买入**：**T+1** 开盘价；**卖出**：同早晨十字星持仓仿真。

【输出】：`trigger_date` = T；`extra.pattern_path` = `red_three_soldiers`。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.database import SessionLocal
from app.models import StockBasic, StockDailyBar
from app.services.screening_service import get_latest_bar_date
from app.services.strategy.strategy_base import (
    BacktestResult,
    BacktestTrade,
    StockStrategy,
    StrategyCandidate,
    StrategyDescriptor,
    StrategyExecutionResult,
    StrategySignal,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Params:
    """红三兵 + 价位与量能阈值（可按回测效果微调）。"""

    stop_loss_pct: float = 0.08
    arm_profit_trigger_pct: float = 0.15
    trailing_stop_pct: float = 0.05
    # 相对历史最高价：默认半价以内视为「不太高」
    max_close_to_cum_hist_high_ratio: float = 0.5
    # 每根阳线实体下限/上限（相对各自开盘价）：不低于 1%、不超过 5%
    min_yang_body_pct: float = 0.01
    max_small_yang_body_pct: float = 0.05
    # 上/下影线占 (high−low) 比例上限（相对全日振幅）
    max_shadow_to_range: float = 0.25
    # T−1、T 日开盘相对前一日收盘的最大允许高开比例（禁止跳空高开超过该值，默认 1%）
    max_open_gap_up_pct: float = 0.01
    # 第三根成交量 vs 前 5 日均量（T−7…T−3）
    volume_surge_ratio: float = 1.1


def _yang_body_and_small_shadows(o: float, h: float, l: float, c: float, p: _Params) -> bool:
    """单根阳线：实体在 [min_yang_body_pct, max_small_yang_body_pct]，且上下影线占振幅比例不超过 max_shadow_to_range。"""
    if not (c > o and h > l):
        return False
    body = (c - o) / o
    if not (p.min_yang_body_pct - 1e-12 <= body <= p.max_small_yang_body_pct + 1e-12):
        return False
    rng = h - l
    upper = h - max(o, c)
    lower = min(o, c) - l
    if upper / rng > p.max_shadow_to_range + 1e-12:
        return False
    if lower / rng > p.max_shadow_to_range + 1e-12:
        return False
    return True


def red_three_soldiers_pattern_ok(bars_list: list[Any], i: int, p: _Params) -> bool:
    """
    三连阳红三兵：实体逐日有限、收盘递增、影线占比与开盘跳空约束、次日开盘价策略依赖的 T 日三根 K 线。
    索引 i 为完成日 T（第三根阳线）。
    """
    if i < 2:
        return False
    bf, bm, bt = bars_list[i - 2], bars_list[i - 1], bars_list[i]
    for b in (bf, bm, bt):
        if not (b.open and b.high and b.low and b.close):
            return False
    o_f, h_f, l_f, c_f = float(bf.open), float(bf.high), float(bf.low), float(bf.close)
    o_m, h_m, l_m, c_m = float(bm.open), float(bm.high), float(bm.low), float(bm.close)
    o_t, h_t, l_t, c_t = float(bt.open), float(bt.high), float(bt.low), float(bt.close)
    if min(o_f, o_m, o_t, c_f, c_m, c_t) <= 0:
        return False
    if not _yang_body_and_small_shadows(o_f, h_f, l_f, c_f, p):
        return False
    if not _yang_body_and_small_shadows(o_m, h_m, l_m, c_m, p):
        return False
    if not _yang_body_and_small_shadows(o_t, h_t, l_t, c_t, p):
        return False
    if not (c_f < c_m < c_t):
        return False
    cap_f = c_f * (1.0 + p.max_open_gap_up_pct) + 1e-9
    cap_m = c_m * (1.0 + p.max_open_gap_up_pct) + 1e-9
    if o_m > cap_f:
        return False
    if o_t > cap_m:
        return False
    return True


def price_not_too_high(bar_t: Any, p: _Params) -> bool:
    """相对历史高点不高；若 MA60 有效则仍在其中期均线之下。"""
    if not bar_t.close:
        return False
    c_t = float(bar_t.close)
    if not bar_t.cum_hist_high or float(bar_t.cum_hist_high) <= 0:
        return False
    cum_h = float(bar_t.cum_hist_high)
    if c_t > p.max_close_to_cum_hist_high_ratio * cum_h + 1e-9:
        return False
    if bar_t.ma60 is not None and float(bar_t.ma60) > 0:
        if not (c_t < float(bar_t.ma60)):
            return False
    return True


def third_day_volume_vs_prior5_ok(bars_list: list[Any], i: int, p: _Params) -> bool:
    """第三根（索引 i）成交量 ≥ 前 5 根（i−7…i−3）日均量 × volume_surge_ratio。"""
    bt = bars_list[i]
    if bt.volume is None or float(bt.volume) <= 0:
        return False
    s = 0.0
    n = 0
    for j in range(i - 7, i - 2):
        bj = bars_list[j]
        if bj.volume is None or float(bj.volume) <= 0:
            return False
        s += float(bj.volume)
        n += 1
    if n != 5:
        return False
    avg5 = s / 5.0
    if avg5 <= 0:
        return False
    return float(bt.volume) >= avg5 * p.volume_surge_ratio - 1e-9


def _simulate_exit_after_buy(
    bars_list: list[Any],
    buy_idx: int,
    buy_price: float,
    end_date: date,
    p: _Params,
) -> tuple[int | None, str | None, float, bool]:
    """与早晨十字星 buy 后持仓循环一致。"""
    sell_idx: int | None = None
    exit_reason: str | None = None
    holding_high: float = buy_price
    trailing_active: bool = False
    arm_trigger_px = round(buy_price * (1.0 + p.arm_profit_trigger_pct), 4)

    for k in range(buy_idx + 1, len(bars_list)):
        bk = bars_list[k]
        if bk.trade_date > end_date:
            break
        if not (bk.close and bk.high):
            continue
        ck = float(bk.close)
        hk = float(bk.high)

        if hk > holding_high:
            holding_high = hk

        if ck <= buy_price * (1.0 - p.stop_loss_pct):
            sell_idx = k
            exit_reason = "stop_loss_8pct"
            break

        if ck >= arm_trigger_px:
            trailing_active = True

        if trailing_active:
            trailing_stop_px = holding_high * (1.0 - p.trailing_stop_pct)
            if ck <= trailing_stop_px:
                sell_idx = k
                exit_reason = "trailing_stop_5pct"
                break

    return sell_idx, exit_reason, holding_high, trailing_active


def run_di_wei_lian_yang_backtest(
    db,
    *,
    start_date: date,
    end_date: date,
    p: _Params,
) -> BacktestResult:
    """红三兵全市场回测扫描。"""
    extended_start = start_date - timedelta(days=60)
    extended_end = end_date + timedelta(days=400)

    stmt = (
        select(
            StockDailyBar.stock_code,
            StockDailyBar.trade_date,
            StockDailyBar.open,
            StockDailyBar.high,
            StockDailyBar.low,
            StockDailyBar.close,
            StockDailyBar.ma5,
            StockDailyBar.ma10,
            StockDailyBar.ma20,
            StockDailyBar.ma60,
            StockDailyBar.cum_hist_high,
            StockDailyBar.volume,
        )
        .where(StockDailyBar.trade_date.between(extended_start, extended_end))
        .order_by(StockDailyBar.stock_code, StockDailyBar.trade_date)
    )
    try:
        rows = db.execute(stmt).all()
    except (OperationalError, ProgrammingError) as e:
        raw = str(getattr(e, "orig", e))
        combined = f"{e!s} {raw}"
        if "cum_hist_high" in combined or "1054" in combined or "does not exist" in combined.lower():
            raise RuntimeError(
                "红三兵策略需 stock_daily_bar.cum_hist_high 字段。请执行 backend/scripts/add_stock_daily_bar_cum_hist.sql "
                "并运行 python -m app.scripts.recompute_hist_extrema_full。原始错误: "
                + raw[:500]
            ) from e
        raise
    logger.info("红三兵回测数据加载完成: %d 条日线记录", len(rows))

    stock_info: dict[str, str | None] = dict(db.query(StockBasic.code, StockBasic.name).all())
    st_codes = {
        code for code, name in stock_info.items()
        if name and (name.startswith("ST") or name.startswith("*ST"))
    }

    stock_bars: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        if row.stock_code in st_codes:
            continue
        stock_bars[row.stock_code].append(row)

    trades: list[BacktestTrade] = []
    min_i = 9

    for code, bars_list in stock_bars.items():
        stock_name = stock_info.get(code)
        last_block = -1
        for i in range(min_i, len(bars_list)):
            if i <= last_block:
                continue

            bar_t = bars_list[i]
            trigger_date = bar_t.trade_date
            if trigger_date < start_date or trigger_date > end_date:
                continue

            if not red_three_soldiers_pattern_ok(bars_list, i, p):
                continue
            if not price_not_too_high(bar_t, p):
                continue
            if not third_day_volume_vs_prior5_ok(bars_list, i, p):
                continue

            if i + 1 >= len(bars_list):
                continue
            buy_idx = i + 1
            bn = bars_list[buy_idx]
            if bn.trade_date > end_date:
                continue
            if not bn.open or float(bn.open) <= 0:
                continue

            buy_bar = bn
            buy_date = buy_bar.trade_date
            buy_price = round(float(buy_bar.open), 4)

            sl_px = round(buy_price * (1.0 - p.stop_loss_pct), 4)
            arm_trigger_px = round(buy_price * (1.0 + p.arm_profit_trigger_pct), 4)

            sell_idx, exit_reason, holding_high, trailing_active = _simulate_exit_after_buy(
                bars_list, buy_idx, buy_price, end_date, p
            )

            bar_f = bars_list[i - 2]
            bar_m = bars_list[i - 1]
            d2 = bar_f.trade_date.isoformat()
            d1 = bar_m.trade_date.isoformat()
            d0 = bar_t.trade_date.isoformat()
            c_t = float(bar_t.close)
            cum_h = float(bar_t.cum_hist_high) if bar_t.cum_hist_high else 0.0
            v_t = float(bar_t.volume) if bar_t.volume else 0.0
            prior5_sum = sum(float(bars_list[j].volume) for j in range(i - 7, i - 2))
            prior5_avg = prior5_sum / 5.0
            vol_ratio = v_t / prior5_avg if prior5_avg > 0 else None
            ma60v = float(bar_t.ma60) if bar_t.ma60 else None

            extra_base: dict[str, Any] = {
                "pattern_path": "red_three_soldiers",
                "pattern_bar_t_minus_2_date": d2,
                "pattern_bar_t_minus_1_date": d1,
                "pattern_bar_t_date": d0,
                "pattern_yin_date": d2,
                "pattern_mid_date": d1,
                "pattern_yang_date": d0,
                "mid_bar_kind": None,
                "buy_rule": "open_next_trading_day_after_pattern",
                "stop_loss_pct": p.stop_loss_pct,
                "stop_loss_price": sl_px,
                "arm_profit_trigger_pct": p.arm_profit_trigger_pct,
                "arm_profit_trigger_price": arm_trigger_px,
                "trailing_stop_pct": p.trailing_stop_pct,
                "sell_rule": "stop_loss_fixed_8pct_or_trailing_stop_5pct_after_15pct_gain",
                "stop_loss_fill_at_limit_price": True,
                "min_yang_body_pct": p.min_yang_body_pct,
                "max_small_yang_body_pct": p.max_small_yang_body_pct,
                "max_shadow_to_range": p.max_shadow_to_range,
                "max_open_gap_up_pct": p.max_open_gap_up_pct,
                "max_close_to_cum_hist_high_ratio": p.max_close_to_cum_hist_high_ratio,
                "close_to_cum_hist_high_ratio": round(c_t / cum_h, 6) if cum_h > 0 else None,
                "below_ma60": bool(ma60v is not None and c_t < ma60v),
                "ma60_at_signal": round(ma60v, 4) if ma60v is not None else None,
                "third_day_volume": round(v_t, 2),
                "prior_5d_avg_volume": round(prior5_avg, 4),
                "third_day_volume_vs_prior5d_avg_ratio": round(vol_ratio, 4) if vol_ratio is not None else None,
                "volume_surge_ratio_threshold": p.volume_surge_ratio,
                "cum_hist_high": round(cum_h, 4),
            }

            if sell_idx is None or exit_reason is None:
                trades.append(
                    BacktestTrade(
                        stock_code=code,
                        stock_name=stock_name,
                        buy_date=buy_date,
                        buy_price=buy_price,
                        trade_type="unclosed",
                        trigger_date=trigger_date,
                        extra={
                            **extra_base,
                            "buy_ma5": round(float(buy_bar.ma5), 4) if buy_bar.ma5 else None,
                            "buy_ma20": round(float(buy_bar.ma20), 4) if buy_bar.ma20 else None,
                        },
                    ),
                )
                last_block = len(bars_list)
                break

            sell_bar = bars_list[sell_idx]
            sell_date = sell_bar.trade_date
            close_raw = float(sell_bar.close)
            if exit_reason == "stop_loss_8pct":
                sell_price = sl_px
                return_rate = round(-p.stop_loss_pct, 4)
            else:
                sell_price = round(close_raw, 4)
                return_rate = round((close_raw - buy_price) / buy_price, 4)
            closed_extra: dict[str, Any] = {
                **extra_base,
                "exit_reason": exit_reason,
                "holding_high": round(holding_high, 4),
                "trailing_active": trailing_active,
                "buy_ma5": round(float(buy_bar.ma5), 4) if buy_bar.ma5 else None,
                "buy_ma20": round(float(buy_bar.ma20), 4) if buy_bar.ma20 else None,
                "sell_ma20": round(float(sell_bar.ma20), 4) if sell_bar.ma20 else None,
                "sell_ma5": round(float(sell_bar.ma5), 4) if sell_bar.ma5 else None,
            }
            if exit_reason == "stop_loss_8pct":
                closed_extra["trigger_day_close"] = round(close_raw, 4)
            if exit_reason == "trailing_stop_5pct":
                closed_extra["trailing_stop_triggered_price"] = round(
                    holding_high * (1.0 - p.trailing_stop_pct), 4
                )
            trades.append(
                BacktestTrade(
                    stock_code=code,
                    stock_name=stock_name,
                    buy_date=buy_date,
                    buy_price=buy_price,
                    sell_date=sell_date,
                    sell_price=sell_price,
                    return_rate=return_rate,
                    trade_type="closed",
                    trigger_date=trigger_date,
                    extra=closed_extra,
                ),
            )
            last_block = sell_idx

    logger.info("红三兵回测扫描完成: trades=%d", len(trades))
    return BacktestResult(trades=trades, skipped_count=0, skip_reasons=[])


class DiWeiLianYangStrategy(StockStrategy):
    strategy_id = "di_wei_lian_yang"
    version = "v2.0.4"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="红三兵",
            version=self.version,
            short_description=(
                "三连阳：实体1%～5%，影线占振幅≤25%；收盘逐级抬高；"
                "T−1、T 开盘相对前收高开≤1%（禁跳空高开逾 1%）；"
                "收盘≤历史高50%且低于MA60（若有）；第三日量≥前5日均×1.1；T+1开盘买；"
                "止损8%×0.92；涨幅≥15%后从最高回落5%止盈。"
            ),
            description=(
                "**形态（完成日 T）**：连续三根阳线；每日实体涨幅 **≥1% 且 ≤5%**（相对当日开盘）；"
                "**上影线**与**下影线**各占全日振幅 **(high−low)** 的比例均 **≤25%**；"
                "且 **收盘三连升**；**open_{T−1} ≤ close_{T−2}×(1+1%)**、**open_T ≤ close_{T−1}×(1+1%)**，"
                "即第二、三根开盘价相对前一日收盘**不得高开超过 1%**（避免跳空高开过猛）。\n"
                "**股价不太高**：**收盘_T ≤ 当日累计历史最高价 × 50%**；若 **MA60** 字段有效，还须 **收盘_T < MA60**（仍在周级别成本线之下，过滤已大幅拉升标的）。\n"
                "**量能**：第三根阳线成交量 **≥** 前五个交易日（T−7…T−3）成交量算术均值 **× 1.1**，过滤无量假突破。\n"
                "**买入**：**T+1** 以**开盘价**买入；下一日无数据或超出回测区间则不成交。\n"
                "**卖出**：与「早晨十字星」一致——**收盘 ≤ 买入×0.92** 则止损，卖价固定 **买入×0.92**；"
                "若收盘曾 **≥ 买入×1.15**，则从持仓最高价回撤 **5%** 时按**当日收盘价**止盈。"
            ),
            assumptions=[
                "剔除 ST/*ST；日线前复权与库表一致。",
                "MA60 若为空则仅按「相对历史半价」过滤，不强制要求 MA60。",
                "同一标的存在未平仓回测笔时，不再扫描该标的后续信号。",
            ],
            risks=[
                "红三兵后亦可能继续下跌；止损与移动止盈为机械规则。",
                "T+1 开盘价成交与盘中止损语义不同。",
            ],
            route_path="/strategy/di-wei-lian-yang",
        )

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        """单日扫描：返回 as_of_date 当日买入的候选。"""
        p = _Params()
        db = SessionLocal()
        try:
            dd = as_of_date or get_latest_bar_date(db, "daily")
            if dd is None:
                raise RuntimeError("日线数据为空，无法执行红三兵选股")
            result = run_di_wei_lian_yang_backtest(db, start_date=dd, end_date=dd, p=p)
            items: list[StrategyCandidate] = []
            signals: list[StrategySignal] = []
            for t in result.trades:
                if t.buy_date != dd:
                    continue
                summary: dict[str, Any] = dict(t.extra or {})
                if t.trade_type == "closed" and t.return_rate is not None:
                    summary["return_rate"] = t.return_rate
                    if t.sell_date is not None:
                        summary["sell_date"] = t.sell_date.isoformat()
                    if t.sell_price is not None:
                        summary["sell_price"] = t.sell_price
                td = t.trigger_date or t.buy_date
                items.append(
                    StrategyCandidate(
                        stock_code=t.stock_code,
                        stock_name=t.stock_name,
                        exchange_type=None,
                        trigger_date=td,
                        summary=summary,
                    ),
                )
                signals.append(
                    StrategySignal(
                        stock_code=t.stock_code,
                        event_date=t.buy_date,
                        event_type="entry",
                        payload=t.extra or {},
                    ),
                )
            return StrategyExecutionResult(
                as_of_date=dd,
                assumptions={
                    "data_granularity": "日线",
                    "pattern": "红三兵：实体1%～5%、影线≤25%振幅、收盘升、T−1/T开盘相对前收高开≤1%；+价位与量能；T+1 开盘价买入",
                    "universe": "非 ST/*ST 全市场",
                },
                params={
                    "stop_loss_pct": p.stop_loss_pct,
                    "arm_profit_trigger_pct": p.arm_profit_trigger_pct,
                    "trailing_stop_pct": p.trailing_stop_pct,
                    "min_yang_body_pct": p.min_yang_body_pct,
                    "max_small_yang_body_pct": p.max_small_yang_body_pct,
                    "max_shadow_to_range": p.max_shadow_to_range,
                    "max_close_to_cum_hist_high_ratio": p.max_close_to_cum_hist_high_ratio,
                    "volume_surge_ratio": p.volume_surge_ratio,
                    "max_open_gap_up_pct": p.max_open_gap_up_pct,
                },
                items=items,
                signals=signals,
            )
        finally:
            db.close()

    def backtest(self, *, start_date: date, end_date: date) -> BacktestResult:
        p = _Params()
        db = SessionLocal()
        try:
            return run_di_wei_lian_yang_backtest(db, start_date=start_date, end_date=end_date, p=p)
        finally:
            db.close()
