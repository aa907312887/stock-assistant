"""
早晨十字星（简化版）（内置回测策略）。

【策略名称】：早晨十字星（简化版）

【目标】：复用与「早晨十字星」**相同的三日 K 线数值形态**（大阴—锤头—阳线及锤头算法）；**不**要求主策略的**跌势结构**。信号日 **T** 收盘相对累计历史高上限 **80%**；**T+1 开盘价**买入；卖出以**日线收盘价**监测：相对买入价**亏损达 8%** 或**盈利达 10%** 时，于**首次触发日的收盘价**平仓（先判止损再判止盈）。

【适用范围】：A 股日线；剔除 ST/*ST。

【依赖字段】：open、high、low、close、cum_hist_high、trade_date；**均线非触发必填**（可选写入 extra）；volume 仅作明细参考。

【核心规则】：
1) **三日形态（与主策略数值一致）**：T−2 相对 T−3 跌幅≥2%、阴线；T−1 锤头（`is_hammer_bar`）且相对 T−2 收盘涨跌≤1%；T 阳线实体≥3%。**不校验** T 日 MA 排列与收盘 vs MA20；**不统计** T−9…T−3。
2) **价位**：**close_T ≤ 0.8×cum_hist_high_T**。
3) **买入**：**T+1** 起寻找第一个**有效开盘价**（>0）的交易日，以**开盘价**成交；中间日无有效 open 则顺延（停牌跳过）。
4) **卖出**：自买入次日起逐日看**收盘价**；先判止损再判止盈。**止损触发**：**close ≤ 买入×(1−8%)**；**止盈触发**：**close ≥ 买入×(1+10%)**；**成交价均为触发当日的收盘价**（不因阈值另行改写成交价为固定倍数价）。

【边界与异常】：无下一根可买 K 线则该信号不成交；`cum_hist_high` 无效则跳过；缺列时抛 `RuntimeError`（文案含「早晨十字星（简化版）」）。

【输出】：`trigger_date` 为 **T**；`extra.exit_reason`：`stop_loss_8pct` / `take_profit_10pct`；`buy_rule`=`t_plus_one_open`。

【示例】：T+1 开盘买入后，某日收盘 ≤ 买×0.92 → 按该日 **close** 记止损离场；或某日收盘 ≥ 买×1.10 → 按该日 **close** 记止盈离场。
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
from app.services.strategy.strategies.zao_chen_shi_zi_xing import is_hammer_bar
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
    """早晨十字星（简化版）阈值；仅三日形态阈值 + 价位线；无跌势窗口参数。"""

    min_first_yin_drop_pct: float = 0.02
    # 止损触发阈值 8%；卖出价为触发日收盘价
    stop_loss_pct: float = 0.08
    # 止盈触发阈值 10%；卖出价为触发日收盘价
    take_profit_pct: float = 0.10
    max_close_to_cum_hist_high_ratio: float = 0.8
    min_yang_body_gain_pct: float = 0.03
    max_hammer_day_close_move_pct: float = 0.01


def run_morning_star_jian_hua_backtest(
    db,
    *,
    start_date: date,
    end_date: date,
    p: _Params,
) -> BacktestResult:
    """
    早晨十字星（简化版）全区间回测：三日形态、无跌势结构、0.8 历史高；T+1 开盘买；收盘监测 ±8% / +10%，触发日以收盘价卖出。
    """
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
            StockDailyBar.pe_percentile,
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
                "早晨十字星（简化版）需 stock_daily_bar.cum_hist_high 字段。请执行 backend/scripts/add_stock_daily_bar_cum_hist.sql "
                "并运行 python -m app.scripts.recompute_hist_extrema_full。原始错误: "
                + raw[:500]
            ) from e
        raise
    logger.info("早晨十字星（简化版）回测数据加载完成: %d 条日线记录", len(rows))

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
    # 仅需 T−3…T 共四根 K 线参与形态判定（索引 i 为 T）
    min_i = 3

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

            # 不设跌势结构：不要求 T 日均线空头、不要求 T−9…T−3 阴线统计与累计跌幅（见 specs/026）

            # T+1 开盘买入；无效 open 顺延至下一根
            buy_idx: int | None = None
            j = i + 1
            while j < len(bars_list):
                bj = bars_list[j]
                if bj.open and float(bj.open) > 0:
                    buy_idx = j
                    break
                j += 1

            if buy_idx is None:
                continue

            buy_bar = bars_list[buy_idx]
            buy_date = buy_bar.trade_date
            if buy_date > end_date:
                continue

            buy_price = round(float(buy_bar.open), 4)
            sl_px = round(buy_price * (1.0 - p.stop_loss_pct), 4)
            tp_trigger_px = round(buy_price * (1.0 + p.take_profit_pct), 4)

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
                if ck >= buy_price * (1.0 + p.take_profit_pct):
                    sell_idx = k
                    exit_reason = "take_profit_10pct"
                    break

            pattern_yin_date = bar_yin.trade_date
            pattern_hammer_date = bar_hammer.trade_date
            pattern_yang_date = bar_t.trade_date

            vol_diag: dict[str, Any] = {"volume_surge_filter": "disabled"}
            if bar_t.volume is not None and float(bar_t.volume) > 0:
                vol_diag["yang_volume"] = round(float(bar_t.volume), 2)
                if i >= 7:
                    pv_sum = 0.0
                    pv_ok = True
                    for jj in range(i - 7, i):
                        bvj = bars_list[jj]
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
                "yang_ma5": round(float(bar_t.ma5), 4) if bar_t.ma5 else None,
                "yang_ma10": round(float(bar_t.ma10), 4) if bar_t.ma10 else None,
                "yang_ma20": round(float(bar_t.ma20), 4) if bar_t.ma20 else None,
                "downtrend_structure_filter": "disabled",
                "cum_hist_high": round(cum_h, 4),
                "yang_close_to_cum_hist_high_ratio": round(c_t / cum_h, 6),
                "max_close_to_cum_hist_high_ratio": p.max_close_to_cum_hist_high_ratio,
                "buy_rule": "t_plus_one_open",
                "stop_loss_pct": p.stop_loss_pct,
                "stop_loss_price": sl_px,
                "take_profit_pct": p.take_profit_pct,
                "take_profit_trigger_price": tp_trigger_px,
                "sell_rule": "close_on_trigger_stop_8pct_take_profit_10pct",
                "stop_loss_fill_at_limit_price": False,
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
            # 止盈与止损均在触发日按收盘价成交（同一口径）
            sell_price = round(close_raw, 4)
            return_rate = round((close_raw - buy_price) / buy_price, 4)
            closed_extra: dict[str, Any] = {
                **extra_base,
                "exit_reason": exit_reason,
                "buy_ma5": round(float(buy_bar.ma5), 4) if buy_bar.ma5 else None,
                "buy_ma20": round(float(buy_bar.ma20), 4) if buy_bar.ma20 else None,
                "sell_ma20": round(float(sell_bar.ma20), 4) if sell_bar.ma20 else None,
                "sell_ma5": round(float(sell_bar.ma5), 4) if sell_bar.ma5 else None,
                "trigger_day_close": round(close_raw, 4),
            }
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

    logger.info("早晨十字星（简化版）回测扫描完成: trades=%d", len(trades))
    return BacktestResult(trades=trades, skipped_count=0, skip_reasons=[])


class ZaoChenShiZiXingJianHuaStrategy(StockStrategy):
    strategy_id = "zao_chen_shi_zi_xing_jian_hua"
    version = "v1.2.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="早晨十字星（简化版）",
            version=self.version,
            short_description=(
                "三日形态同早晨十字星数值口径；无跌势结构；收盘≤历史高80%；T+1开盘买；收盘监测−8%/+10%，触发日收盘价卖。"
            ),
            description=(
                "**三日 K 线**：与「早晨十字星」相同的数值判定；**不要求**跌势结构与均线空头。"
                "**价位**：信号日 **T** 收盘 ≤ 累计历史高 **×80%**。"
                "**买入**：**T+1**（停牌顺延）**开盘价**。"
                "**卖出**：买入次日起逐日看**收盘价**；先止损后止盈——若收盘 ≤ 买入×0.92 则**当日收盘价**平仓（约 −8% 亏损）；"
                "否则若收盘 ≥ 买入×1.10 则**当日收盘价**平仓（约 +10% 盈利）；触发阈值均以收盘价判定，**卖价均为该日收盘价**。"
            ),
            assumptions=[
                "剔除 ST/*ST；买入价为 T+1（或顺延）开盘价。",
                "触发日 T 为第三根阳线日；止盈与止损成交均为触发日的日线收盘价。",
                "锤头判定与主策略相同；均线不作为买入触发条件。",
                "同一标的出现未平仓笔后不再扫描该标的后续形态。",
            ],
            risks=[
                "开盘价跳空可能影响买入价；触发止损/止盈当日收盘价可能偏离阈值对应的理论价（大跌大涨时亏损或盈利幅度可超过 −8% / +10%）。",
            ],
            route_path="/strategy/zao-chen-shi-zi-xing-jian-hua",
        )

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        """单日扫描：返回 as_of_date 当日**实际开盘买入**的候选（与回测一致）。"""
        p = _Params()
        db = SessionLocal()
        try:
            dd = as_of_date or get_latest_bar_date(db, "daily")
            if dd is None:
                raise RuntimeError("日线数据为空，无法执行早晨十字星（简化版）选股")
            result = run_morning_star_jian_hua_backtest(db, start_date=dd, end_date=dd, p=p)
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
                    "price_type": "买入日为 T+1（或顺延）开盘价；止盈与止损均在触发条件满足当日按收盘价卖出",
                    "pattern": "三日K线数值同早晨十字星；无跌势结构；收盘≤历史高80%；买入=T+1 open",
                    "universe": "非 ST/*ST 全市场",
                },
                params={
                    "min_first_yin_drop_pct": p.min_first_yin_drop_pct,
                    "stop_loss_pct": p.stop_loss_pct,
                    "take_profit_pct": p.take_profit_pct,
                    "max_close_to_cum_hist_high_ratio": p.max_close_to_cum_hist_high_ratio,
                    "min_yang_body_gain_pct": p.min_yang_body_gain_pct,
                    "max_hammer_day_close_move_pct": p.max_hammer_day_close_move_pct,
                    "downtrend_structure_filter": False,
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
            return run_morning_star_jian_hua_backtest(db, start_date=start_date, end_date=end_date, p=p)
        finally:
            db.close()
