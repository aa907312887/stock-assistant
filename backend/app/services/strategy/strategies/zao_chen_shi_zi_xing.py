"""
早晨十字星（内置回测策略）。

【策略名称】：早晨十字星（跌势末期三根 K 线反转；买入/止盈同曙光初现，止损为 8%）

【目标】：在**跌势后期**识别 **T−2 大阴线 → T−1 锤头 → T 阳线** 的三日组合（**不校验成交量放大**）；自阳线日 **T** 起等待收盘价**站上 MA5** 买入；持仓后：**收盘价≤买入价×0.92** 则无条件 **8%** 止损、**成交价固定买入价×0.92**（「曙光初现」为 10% / ×0.90）；**收盘价较买入涨幅 ≥10%** 则**当日按收盘价**止盈；未触发则持有至回测结束。

【适用范围】：A 股日线（前复权口径与库表一致）；剔除 ST/*ST。

【依赖字段】：open、high、low、close、ma5、ma10、ma20、cum_hist_high、trade_date（stock_daily_bar）；volume 仅用于明细 optional 展示

【核心规则】：
1) **跌势后期**（信号日为第三根阳线日 **T**，对应索引 **i**）：在 **T−9 … T−3** 共 7 个交易日中阴线（close<open）天数 ≥ 5；且 **(close_{T−3}/close_{T−9} − 1) ≤ −10%**；**T** 日 **MA5<MA10<MA20** 且 **close<MA20**。
2) **三根 K 线**：**T−2** 阴线且 **(close_{T−2}/close_{T−3} − 1) ≤ −2%**；**T−1** 为锤头（见下方口径）且 **|close_{T−1}/close_{T−2} − 1| ≤ 1%**；**T** 为阳线且实体涨幅 **(close−open)/open ≥ 3%**。
3) **高位**：**close_T ≤ 0.5×cum_hist_high_T**（**不强制 T 日放量**，与曙光初现不同）。
4) **买入**：自 **T** 日（含）起首次 **close>MA5**，以当日收盘价买入。
5) **卖出**：先止损再止盈（顺序同曙光初现）；**止损为本策略 8%**（≤买入×0.92 固定×0.92），**非**曙光初现的 10%；收盘≥买入×1.1→当日收盘止盈。

【锤头口径】：记 body=|close−open|，upper=high−max(open,close)，lower=min(open,close)−low，range_=high−low；实体上端：min(open,close) ≥ low+0.5×range_；body 极小时用 lower/upper 占 range_ 比例判定，否则 lower≥2×body 且 upper≤body。

【输出】：`BacktestTrade.trigger_date` 为 **T**（第三根阳线日）；`extra` 含三日日期与 `exit_reason`。
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


def is_hammer_bar(
    open_: float,
    high: float,
    low: float,
    close: float,
) -> bool:
    """锤头线数值判定（与 specs/016-早晨十字星/research.md 一致）。"""
    body = abs(close - open_)
    upper = high - max(open_, close)
    lower = min(open_, close) - low
    range_ = high - low
    if range_ <= 0:
        return False
    body_bottom = min(open_, close)
    if body_bottom < low + 0.5 * range_:
        return False
    ref = max(abs(close), 1.0)
    if body < ref * 1e-8:
        return lower >= 0.55 * range_ and upper <= 0.15 * range_
    return lower >= 2.0 * body and upper <= body


@dataclass(frozen=True)
class _Params:
    """早晨十字星阈值（与 spec / research 一致）。"""

    min_first_yin_drop_pct: float = 0.02
    # 止损 8%（曙光初现策略为 10%）
    stop_loss_pct: float = 0.08
    arm_profit_pct: float = 0.10
    max_close_to_cum_hist_high_ratio: float = 0.5
    weak_lookback_days: int = 7
    min_bearish_days_in_lookback: int = 5
    min_prior_window_cumulative_drop_pct: float = 0.10
    min_yang_body_gain_pct: float = 0.03
    max_hammer_day_close_move_pct: float = 0.01
    # 前期 7 日对应索引 j ∈ [i-9, i-3]，在 Python 中写作 range(i-9, i-2)
    prior_weak_range_stop_offset: int = 2


class ZaoChenShiZiXingStrategy(StockStrategy):
    strategy_id = "zao_chen_shi_zi_xing"
    version = "v1.7.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="早晨十字星",
            version=self.version,
            short_description=(
                "跌势末期三根K线：T−2大阴(跌≥2%)→T−1锤头(相对T−2涨跌≤1%)→T阳线(实体≥3%)；"
                "前期T−9…T−3至少5阴且累计跌≥10%；T日跌势MA+收盘≤历史高50%（不强制放量）；"
                "站上MA5买入；本策略止损8%固定×0.92（曙光初现为10%）；收盘≥买入×1.1当日止盈。"
            ),
            description=(
                "与「曙光初现」的差异：**形态为连续三根 K 线**（大阴线—锤头—阳线），信号触发日为第三根**阳线日 T**，"
                "而非「前一日阴线 + 当日阳线」的单日组合。"
                "跌势统计窗口在形态第一根之前：**T−9…T−3** 七日中至少五日阴线，且 **T−3 相对 T−9 收盘累计跌幅至少 10%**。"
                "第一根（T−2）须为阴线且相对 T−3 收盘跌幅至少 2%；第二根（T−1）须为锤头线且相对 T−2 收盘涨跌幅绝对值不超过 1%；"
                "第三根（T）须为阳线且实体涨幅（相对开盘）至少 3%。"
                "T 日须为跌势结构（MA5<MA10<MA20 且收盘仍低于 MA20），收盘价不高于当日 cum_hist_high 的 50%。"
                "**本策略不校验阳线放量**（与曙光初现的 1.5 倍均量条件不同）。"
                "**买入与止盈规则与曙光初现一致**；**止损仅本策略为 8%**（曙光初现为 10%）：自 T 日起首次收盘价站上 MA5 买入；"
                "持仓后收盘价≤买入价×0.92 则无条件止损，卖出价固定买入价×0.92（亏损恒 8%）；"
                "若收盘价≥买入价×1.10，则当日按收盘价卖出（止盈）；否则持有至回测结束可能未平仓。"
            ),
            assumptions=[
                "剔除 ST/*ST；买卖价均为日线收盘价。",
                "触发日 T 为第三根阳线日；买入日为自 T 日起首次 close>MA5 的日期。",
                "锤头判定见策略代码 is_hammer_bar（实体偏上、下影显著长于实体等）。",
                "不对 T 日成交量相对前 7 日均量做强制要求。",
                "止损为 8% 固定（曙光初现策略为 10%）；止盈与曙光初现一致。",
                "同一标的出现未平仓笔后不再扫描该标的后续形态。",
            ],
            risks=[
                "均线滞后；震荡行情反复穿线。",
                "数据缺失或停牌可能导致无法成交或长期未平仓。",
            ],
            route_path="/strategy/zao-chen-shi-zi-xing",
        )

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        """单日扫描：返回 as_of_date 当日**买入**的候选（与回测口径一致）。"""
        p = _Params()
        db = SessionLocal()
        try:
            dd = as_of_date or get_latest_bar_date(db, "daily")
            if dd is None:
                raise RuntimeError("日线数据为空，无法执行早晨十字星选股")
            result = self._run_backtest(db, start_date=dd, end_date=dd, p=p)
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
                    "price_type": "买入日为首次 close>MA5 的收盘价；止损时卖价固定买入×0.92；止盈时卖价为触发日收盘价（≥买入×1.1）",
                    "pattern": "T−2大阴+T−1锤头+T阳线；跌势窗口T−9…T−3；收盘≤历史高50%；不强制放量；买入=首次 close>MA5",
                    "universe": "非 ST/*ST 全市场",
                },
                params={
                    "min_first_yin_drop_pct": p.min_first_yin_drop_pct,
                    "stop_loss_pct": p.stop_loss_pct,
                    "arm_profit_pct": p.arm_profit_pct,
                    "max_close_to_cum_hist_high_ratio": p.max_close_to_cum_hist_high_ratio,
                    "weak_lookback_days": p.weak_lookback_days,
                    "min_bearish_days_in_lookback": p.min_bearish_days_in_lookback,
                    "min_prior_window_cumulative_drop_pct": p.min_prior_window_cumulative_drop_pct,
                    "min_yang_body_gain_pct": p.min_yang_body_gain_pct,
                    "max_hammer_day_close_move_pct": p.max_hammer_day_close_move_pct,
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
            return self._run_backtest(db, start_date=start_date, end_date=end_date, p=p)
        finally:
            db.close()

    @staticmethod
    def _run_backtest(db, *, start_date: date, end_date: date, p: _Params) -> BacktestResult:
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
                    "早晨十字星需 stock_daily_bar.cum_hist_high 字段。请执行 backend/scripts/add_stock_daily_bar_cum_hist.sql "
                    "并运行 python -m app.scripts.recompute_hist_extrema_full。原始错误: "
                    + raw[:500]
                ) from e
            raise
        logger.info("早晨十字星回测数据加载完成: %d 条日线记录", len(rows))

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

                bar_hammer = bars_list[i - 1]
                bar_yin = bars_list[i - 2]
                bar_t3 = bars_list[i - 3]

                if not (
                    bar_t.open
                    and bar_t.close
                    and bar_hammer.open
                    and bar_hammer.high
                    and bar_hammer.low
                    and bar_hammer.close
                    and bar_yin.open
                    and bar_yin.close
                    and bar_t3.close
                ):
                    continue

                o_t, c_t = float(bar_t.open), float(bar_t.close)
                o_h, h_h, l_h, c_h = (
                    float(bar_hammer.open),
                    float(bar_hammer.high),
                    float(bar_hammer.low),
                    float(bar_hammer.close),
                )
                o_y, c_y = float(bar_yin.open), float(bar_yin.close)
                c_t3 = float(bar_t3.close)

                if (
                    c_t3 <= 0
                    or o_t <= 0
                    or c_t <= 0
                    or o_h <= 0
                    or h_h <= 0
                    or l_h <= 0
                    or c_h <= 0
                    or o_y <= 0
                    or c_y <= 0
                ):
                    continue

                if not (c_t > o_t):
                    continue
                yang_body_gain = (c_t - o_t) / o_t
                if yang_body_gain < p.min_yang_body_gain_pct:
                    continue

                if not (c_y < o_y):
                    continue
                first_yin_drop = c_y / c_t3 - 1.0
                if first_yin_drop > -p.min_first_yin_drop_pct:
                    continue

                if not is_hammer_bar(o_h, h_h, l_h, c_h):
                    continue
                hammer_move = c_h / c_y - 1.0
                if abs(hammer_move) > p.max_hammer_day_close_move_pct:
                    continue

                if not bar_t.cum_hist_high or float(bar_t.cum_hist_high) <= 0:
                    continue
                cum_h = float(bar_t.cum_hist_high)
                max_allowed = p.max_close_to_cum_hist_high_ratio * cum_h
                if c_t > max_allowed:
                    continue

                if not (bar_t.ma5 and bar_t.ma10 and bar_t.ma20):
                    continue
                m5t, m10t, m20t = float(bar_t.ma5), float(bar_t.ma10), float(bar_t.ma20)
                if not (m5t < m10t < m20t):
                    continue
                if not (c_t < m20t):
                    continue

                bearish_days = 0
                prior_weak_ok = True
                for j in range(i - 9, i - p.prior_weak_range_stop_offset):
                    bday = bars_list[j]
                    if not (bday.open and bday.close):
                        prior_weak_ok = False
                        break
                    if float(bday.close) < float(bday.open):
                        bearish_days += 1
                if not prior_weak_ok or bearish_days < p.min_bearish_days_in_lookback:
                    continue

                bar_t9 = bars_list[i - 9]
                if not bar_t9.close:
                    continue
                c_t9 = float(bar_t9.close)
                if c_t9 <= 0:
                    continue
                c_i3 = float(bars_list[i - 3].close)
                cum_prior_seg = c_i3 / c_t9 - 1.0
                if cum_prior_seg > -p.min_prior_window_cumulative_drop_pct:
                    continue

                buy_idx: int | None = None
                for j in range(i, len(bars_list)):
                    bj = bars_list[j]
                    if not (bj.close and bj.ma5):
                        continue
                    cj = float(bj.close)
                    m5 = float(bj.ma5)
                    if cj > m5:
                        buy_idx = j
                        break

                if buy_idx is None:
                    continue

                buy_bar = bars_list[buy_idx]
                buy_date = buy_bar.trade_date
                if buy_date > end_date:
                    continue

                buy_price = round(float(buy_bar.close), 4)
                sl_px = round(buy_price * (1.0 - p.stop_loss_pct), 4)
                arm_px = round(buy_price * (1.0 + p.arm_profit_pct), 4)

                sell_idx: int | None = None
                exit_reason: str | None = None
                for k in range(buy_idx + 1, len(bars_list)):
                    bk = bars_list[k]
                    if bk.trade_date > end_date:
                        break
                    if not bk.close:
                        continue
                    ck = float(bk.close)
                    if ck <= buy_price * (1.0 - p.stop_loss_pct):
                        sell_idx = k
                        exit_reason = "stop_loss_8pct"
                        break
                    if ck >= buy_price * (1.0 + p.arm_profit_pct):
                        sell_idx = k
                        exit_reason = "take_profit_10pct"
                        break

                pattern_yin_date = bar_yin.trade_date
                pattern_hammer_date = bar_hammer.trade_date
                pattern_yang_date = bar_t.trade_date

                vol_diag: dict[str, Any] = {"volume_surge_filter": "disabled"}
                if bar_t.volume is not None and float(bar_t.volume) > 0:
                    vol_diag["yang_volume"] = round(float(bar_t.volume), 2)
                    pv_sum = 0.0
                    pv_ok = True
                    for j in range(i - 7, i):
                        bvj = bars_list[j]
                        if bvj.volume is None or float(bvj.volume) <= 0:
                            pv_ok = False
                            break
                        pv_sum += float(bvj.volume)
                    if pv_ok and pv_sum > 0:
                        avg_v = pv_sum / 7.0
                        vol_diag["prior_7_volume_avg"] = round(avg_v, 2)
                        vol_diag["yang_volume_vs_prior7_avg_ratio"] = round(float(bar_t.volume) / avg_v, 4)

                extra_base: dict[str, Any] = {
                    "pattern_yin_date": pattern_yin_date.isoformat(),
                    "pattern_hammer_date": pattern_hammer_date.isoformat(),
                    "pattern_yang_date": pattern_yang_date.isoformat(),
                    "pattern_yang_date_iso": trigger_date.isoformat(),
                    "yang_body_gain_pct": round(yang_body_gain * 100, 4),
                    "min_yang_body_gain_pct": p.min_yang_body_gain_pct,
                    "first_yin_drop_pct": round(first_yin_drop * 100, 4),
                    "min_first_yin_drop_pct": p.min_first_yin_drop_pct,
                    "hammer_close_move_pct": round(hammer_move * 100, 4),
                    "max_hammer_day_close_move_pct": p.max_hammer_day_close_move_pct,
                    "yang_ma5": round(m5t, 4),
                    "yang_ma10": round(m10t, 4),
                    "yang_ma20": round(m20t, 4),
                    "yang_close_below_ma20": True,
                    "downtrend_ma_bearish": True,
                    "bearish_days_in_prior_t9_to_t3": bearish_days,
                    "prior_t9_to_t3_window": "T-9..T-3",
                    "prior_t3_to_t9_close_to_close_return_pct": round(cum_prior_seg * 100, 4),
                    "min_prior_window_cumulative_drop_pct": p.min_prior_window_cumulative_drop_pct,
                    "cum_hist_high": round(cum_h, 4),
                    "yang_close_to_cum_hist_high_ratio": round(c_t / cum_h, 6),
                    "max_close_to_cum_hist_high_ratio": p.max_close_to_cum_hist_high_ratio,
                    "buy_rule": "first_close_above_ma5_from_yang_day",
                    "stop_loss_pct": p.stop_loss_pct,
                    "stop_loss_price": sl_px,
                    "arm_profit_pct": p.arm_profit_pct,
                    "arm_profit_price": arm_px,
                    "sell_rule": "stop_loss_fixed_minus_8pct_or_take_profit_10pct_at_close",
                    "stop_loss_fill_at_limit_price": True,
                    **vol_diag,
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
                    "buy_ma5": round(float(buy_bar.ma5), 4) if buy_bar.ma5 else None,
                    "buy_ma20": round(float(buy_bar.ma20), 4) if buy_bar.ma20 else None,
                    "sell_ma20": round(float(sell_bar.ma20), 4) if sell_bar.ma20 else None,
                    "sell_ma5": round(float(sell_bar.ma5), 4) if sell_bar.ma5 else None,
                }
                if exit_reason == "stop_loss_8pct":
                    closed_extra["trigger_day_close"] = round(close_raw, 4)
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

        logger.info("早晨十字星回测扫描完成: trades=%d", len(trades))
        return BacktestResult(trades=trades, skipped_count=0, skip_reasons=[])
