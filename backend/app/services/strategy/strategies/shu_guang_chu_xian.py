"""
曙光初现（内置回测策略）。

【策略名称】：曙光初现（站上 MA5 入场 + 亏损 6% 止损 / 盈利达 10% 后按 MA5 离场）

【目标】：在**跌势结构**中识别「前一日大跌阴线 + 次日阳线」，自阳线当日起等待收盘价**站上 MA5** 即买入；持仓后：亏损达 **6%** 止损；**曾达收盘 +10% 后**改按收盘价跌破 MA5 离场；未触发则持有至回测结束（可能 unclosed）。

【依赖字段】：open、close、volume、ma5、ma10、ma20、cum_hist_high、trade_date（stock_daily_bar）

【核心规则】：
1) 形态（信号阳线日 T）：同前版，并增加 **成交量**：T 日成交量 ≥ **T 之前连续 7 个交易日**成交量算术平均值 × **1.5**（即比该均值高出二分之一）；前 7 日及 T 日须均有有效成交量。另：前 7 天至少 5 阴、T-7～T-1 累计跌≥10%、跌势 MA、前阴跌≥3%、阳线实体≥3%、收盘≤cum_hist_high 50% 等。
2) **买入**：自 T 日（含）起，首次满足 close > MA5，以**当日收盘价**买入（不要求 MA20）。
3) **卖出**：自买入日**次日**起逐日（仅考虑到 end_date），用**收盘价**判定是否触发；顺序如下：
   - **止损**：若当日 close ≤ 买入价 × (1−6%)，则记为触发止损（`stop_loss_6pct`），**卖出价固定为买入价 × 0.94**（收益率恰好 −6%），不按触发日收盘价——对应条件单/限价止损在 −6% 成交的假设；
   - **武装后破 MA5**：否则若此前已有某日收盘 ≥ 买入价 × (1+10%)，且当日 close < MA5，则按**当日收盘价**卖出（`break_ma5_after_arm`）；
   - 同一日先判止损，再更新「是否已达 +10%」，再判 MA5；**止损优先**。
4) 未平仓：end_date 前未触发上述条件则 unclosed。

【输出】：extra 含 exit_reason；`BacktestTrade.trigger_date` 为信号阳线日 T。
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
    min_prev_bearish_drop_pct: float = 0.03
    # 止损：相对买入价亏损达到该比例（6%）
    stop_loss_pct: float = 0.06
    # 口语「盈利 10 个点」：收盘价较买入价涨幅达到该比例后，后续按 MA5 破位离场
    arm_profit_pct: float = 0.10
    max_close_to_cum_hist_high_ratio: float = 0.5
    weak_lookback_days: int = 7
    min_bearish_days_in_lookback: int = 5
    min_prior_window_cumulative_drop_pct: float = 0.10
    min_yang_body_gain_pct: float = 0.03
    # 阳线日成交量 ≥ 前 7 个交易日成交量算术平均 × 该倍数（1.5 = 比均值高二分之一）
    min_yang_volume_vs_prior7_avg_ratio: float = 1.5


class ShuGuangChuXianStrategy(StockStrategy):
    strategy_id = "shu_guang_chu_xian"
    version = "v2.10.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="曙光初现",
            version=self.version,
            short_description="前7天≥5阴+累计跌超10%+跌势MA+前阴跌≥3%+阳线实体≥3%+收盘≤历史高50%+阳线量≥前7日均量×1.5；站上MA5买入；止损触发后固定买入价×0.94；达+10%后破MA5按收盘卖。",
            description=(
                "形态：前一日阴线且较前一日收盘至少跌 3%，当日阳线且阳线实体涨幅（相对开盘）至少 3%；"
                "且当日须为跌势结构：MA5<MA10<MA20，且阳线收盘仍低于 MA20；"
                "且收盘价不高于截至当日的累计历史最高价（cum_hist_high）的 50%；"
                "且信号日之前 7 个交易日中至少 5 天为阴线；且 T-7 收盘至 T-1 收盘累计跌幅超过 10%；"
                "且阳线当日成交量不低于此前 7 个交易日成交量算术平均的 1.5 倍（放量显著）。"
                "自阳线当日起，首次出现收盘价站上 MA5 时以收盘价买入。"
                "持仓后：若某日收盘价触及买入价×0.94 以下则触发止损，成交价为买入价×0.94（固定 −6%，模拟条件单）；"
                "若已有收盘≥买入价×1.10，则之后可按收盘价跌破 MA5 卖出。"
                "回测结束仍未触发则未平仓。"
            ),
            assumptions=[
                "剔除 ST/*ST；买卖价均为日线收盘价。",
                "站上 MA5 指 close>MA5；武装后跌破 MA5 指 close 低于当日 MA5。",
                "止损触发：收盘价 ≤ 买入价×0.94；成交价为买入价×0.94（−6%），非触发日收盘价。",
                "「盈利 10 个点」指收盘价较买入价涨幅≥10%；达此后离场规则切换为跌破 MA5。",
                "同一标的出现未平仓笔后不再扫描该标的后续形态。",
                "cum_hist_high 为截至该交易日（含）的扩展历史最高价；高位过滤取阳线当日行。",
                "跌势判定：阳线当日 MA5<MA10<MA20 且 close<MA20；排除已呈多头排列或阳线已站上长均线的样本。",
                "前期弱势：阳线日之前 7 个交易日（不含阳线当日）中至少 5 根阴线；"
                "且 T-7 与 T-1 两日收盘价之间累计跌幅须超过 10%。",
                "阳线实体涨幅指 (收盘-开盘)/开盘 ≥ 3%（百分点）。",
                "阳线日成交量须 ≥ 前 7 个交易日（T-7…T-1）成交量算术平均值 × 1.5；各日 volume 须有效。",
            ],
            risks=[
                "均线滞后；震荡行情反复穿线。",
                "数据缺失或停牌可能导致无法成交或长期未平仓。",
            ],
            route_path="/strategy/shu-guang-chu-xian",
        )

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        """单日扫描：返回 as_of_date 当日**买入**的候选（与回测口径一致）。"""
        p = _Params()
        db = SessionLocal()
        try:
            dd = as_of_date or get_latest_bar_date(db, "daily")
            if dd is None:
                raise RuntimeError("日线数据为空，无法执行曙光初现选股")
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
                    "price_type": "买入日为首次 close>MA5 的收盘价；止损触发后卖价固定为买入价×0.94；武装后破 MA5 为当日收盘价",
                    "pattern": "前7天≥5阴+T-7至T-1累计跌>10%+跌势MA+阳线<MA20+前阴跌≥3%+阳线实体≥3%+收盘≤cum_hist_high×50%+阳线量≥前7日均量×1.5；买入=首次 close>MA5",
                    "universe": "非 ST/*ST 全市场",
                },
                params={
                    "min_prev_bearish_drop_pct": p.min_prev_bearish_drop_pct,
                    "stop_loss_pct": p.stop_loss_pct,
                    "arm_profit_pct": p.arm_profit_pct,
                    "max_close_to_cum_hist_high_ratio": p.max_close_to_cum_hist_high_ratio,
                    "weak_lookback_days": p.weak_lookback_days,
                    "min_bearish_days_in_lookback": p.min_bearish_days_in_lookback,
                    "min_prior_window_cumulative_drop_pct": p.min_prior_window_cumulative_drop_pct,
                    "min_yang_body_gain_pct": p.min_yang_body_gain_pct,
                    "min_yang_volume_vs_prior7_avg_ratio": p.min_yang_volume_vs_prior7_avg_ratio,
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
                    "曙光初现需 stock_daily_bar.cum_hist_high 字段。请执行 backend/scripts/add_stock_daily_bar_cum_hist.sql "
                    "并运行 python -m app.scripts.recompute_hist_extrema_full。原始错误: "
                    + raw[:500]
                ) from e
            raise
        logger.info("曙光初现回测数据加载完成: %d 条日线记录", len(rows))

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

        for code, bars_list in stock_bars.items():
            stock_name = stock_info.get(code)
            last_block = -1
            min_i = max(2, p.weak_lookback_days)
            for i in range(min_i, len(bars_list)):
                if i <= last_block:
                    continue

                bar_t = bars_list[i]
                trigger_date = bar_t.trade_date
                if trigger_date < start_date or trigger_date > end_date:
                    continue

                bar_prev = bars_list[i - 1]
                bar_pp = bars_list[i - 2]
                if not (
                    bar_prev.open
                    and bar_prev.close
                    and bar_pp.close
                    and bar_t.open
                    and bar_t.close
                ):
                    continue

                c_pp = float(bar_pp.close)
                o_p, c_p = float(bar_prev.open), float(bar_prev.close)
                o_t, c_t = float(bar_t.open), float(bar_t.close)
                if c_pp <= 0 or o_p <= 0 or c_p <= 0 or o_t <= 0 or c_t <= 0:
                    continue

                if not (c_p < o_p):
                    continue
                if not (c_t > o_t):
                    continue
                yang_body_gain = (c_t - o_t) / o_t
                if yang_body_gain < p.min_yang_body_gain_pct:
                    continue

                drop_pct = c_p / c_pp - 1.0
                if drop_pct > -p.min_prev_bearish_drop_pct:
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
                for j in range(i - p.weak_lookback_days, i):
                    bday = bars_list[j]
                    if not (bday.open and bday.close):
                        prior_weak_ok = False
                        break
                    if float(bday.close) < float(bday.open):
                        bearish_days += 1
                if not prior_weak_ok or bearish_days < p.min_bearish_days_in_lookback:
                    continue

                bar_t7 = bars_list[i - 7]
                if not bar_t7.close:
                    continue
                c_t7 = float(bar_t7.close)
                if c_t7 <= 0:
                    continue
                cum_ret_t7_to_t1 = c_p / c_t7 - 1.0
                if cum_ret_t7_to_t1 > -p.min_prior_window_cumulative_drop_pct:
                    continue

                prior_vol_sum = 0.0
                prior_vol_ok = True
                for j in range(i - 7, i):
                    bvj = bars_list[j]
                    if bvj.volume is None or float(bvj.volume) <= 0:
                        prior_vol_ok = False
                        break
                    prior_vol_sum += float(bvj.volume)
                if not prior_vol_ok:
                    continue
                avg_vol_prior7 = prior_vol_sum / 7.0
                if bar_t.volume is None or float(bar_t.volume) <= 0:
                    continue
                vol_t = float(bar_t.volume)
                if vol_t < avg_vol_prior7 * p.min_yang_volume_vs_prior7_avg_ratio:
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
                armed = False
                for k in range(buy_idx + 1, len(bars_list)):
                    bk = bars_list[k]
                    if bk.trade_date > end_date:
                        break
                    if not bk.close:
                        continue
                    ck = float(bk.close)
                    if ck <= buy_price * (1.0 - p.stop_loss_pct):
                        sell_idx = k
                        exit_reason = "stop_loss_6pct"
                        break
                    if ck >= buy_price * (1.0 + p.arm_profit_pct):
                        armed = True
                    if armed and bk.ma5 and ck < float(bk.ma5):
                        sell_idx = k
                        exit_reason = "break_ma5_after_arm"
                        break

                prev_drop_pct = round(drop_pct * 100, 4)
                extra_base: dict[str, Any] = {
                    "pattern_yang_date": trigger_date.isoformat(),
                    "yang_body_gain_pct": round(yang_body_gain * 100, 4),
                    "min_yang_body_gain_pct": p.min_yang_body_gain_pct,
                    "yang_ma5": round(m5t, 4),
                    "yang_ma10": round(m10t, 4),
                    "yang_ma20": round(m20t, 4),
                    "yang_close_below_ma20": True,
                    "downtrend_ma_bearish": True,
                    "bearish_days_in_prior_7": bearish_days,
                    "weak_lookback_days": p.weak_lookback_days,
                    "min_bearish_days_in_lookback": p.min_bearish_days_in_lookback,
                    "prior_t7_to_t1_close_to_close_return_pct": round(cum_ret_t7_to_t1 * 100, 4),
                    "min_prior_window_cumulative_drop_pct": p.min_prior_window_cumulative_drop_pct,
                    "cum_hist_high": round(cum_h, 4),
                    "yang_close_to_cum_hist_high_ratio": round(c_t / cum_h, 6),
                    "max_close_to_cum_hist_high_ratio": p.max_close_to_cum_hist_high_ratio,
                    "prev_bearish_drop_pct_points": prev_drop_pct,
                    "min_prev_bearish_drop_pct_points": round(p.min_prev_bearish_drop_pct * 100, 2),
                    "yang_volume": round(vol_t, 2),
                    "prior_7_volume_avg": round(avg_vol_prior7, 2),
                    "yang_volume_vs_prior7_avg_ratio": round(vol_t / avg_vol_prior7, 4),
                    "min_yang_volume_vs_prior7_avg_ratio": p.min_yang_volume_vs_prior7_avg_ratio,
                    "buy_rule": "first_close_above_ma5_from_yang_day",
                    "stop_loss_pct": p.stop_loss_pct,
                    "stop_loss_price": sl_px,
                    "arm_profit_pct": p.arm_profit_pct,
                    "arm_profit_price": arm_px,
                    "sell_rule": "stop_loss_fixed_minus_6pct_fill_or_break_ma5_after_arm_at_close",
                    "stop_loss_fill_at_limit_price": True,
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
                if exit_reason == "stop_loss_6pct":
                    sell_price = sl_px
                    return_rate = round(-p.stop_loss_pct, 4)
                else:
                    sell_price = round(float(sell_bar.close), 4)
                    return_rate = round((sell_price - buy_price) / buy_price, 4)
                closed_extra: dict[str, Any] = {
                    **extra_base,
                    "exit_reason": exit_reason,
                    "buy_ma5": round(float(buy_bar.ma5), 4) if buy_bar.ma5 else None,
                    "buy_ma20": round(float(buy_bar.ma20), 4) if buy_bar.ma20 else None,
                    "sell_ma20": round(float(sell_bar.ma20), 4) if sell_bar.ma20 else None,
                    "sell_ma5": round(float(sell_bar.ma5), 4) if sell_bar.ma5 else None,
                }
                if exit_reason == "stop_loss_6pct":
                    closed_extra["trigger_day_close"] = round(float(sell_bar.close), 4)
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

        logger.info("曙光初现回测扫描完成: trades=%d", len(trades))
        return BacktestResult(trades=trades, skipped_count=0, skip_reasons=[])
