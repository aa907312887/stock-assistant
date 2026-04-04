"""
大阳回落法（内置回测策略）。

【策略名称】：大阳回落法
【目标】：在低位股票中，识别放量大阳线，次日阴线回落但收盘价在阳线实体 1/3 之上，
         以回落日收盘价买入；盈利 10% 止盈，跌至大阳线开盘价止损。

【适用范围】：
- 市场：A 股全市场（剔除 ST/*ST）
- 数据粒度：日线
- 依赖字段：open / high / low / close / volume / prev_close / pct_change / cum_hist_high / trade_date
            （来自 stock_daily_bar）

【核心规则】：
1) 低位约束：收盘价不超过截至当日累计历史最高价的一半。
2) 近期无大涨：触发日前 20 个交易日内无单日涨幅超过 5%（pct_change > 5.0）。
3) 大阳触发（Day T）：
   - 涨幅 >= 8%：(close - prev_close) / prev_close >= 0.08 且阳线（close > open）。
   - 放量：当日成交量 >= 前一交易日成交量 × 2。
4) 买入确认（Day T+1）：
   - 阴线收盘：close < open。
   - 收盘价在阳线实体 1/3 之上：close_T1 > open_T + (close_T - open_T) × (1 - pullback_body_ratio)。
   - 以 T+1 收盘价买入。
5) 卖出规则：
   - 止损：盘中最低价触及大阳线开盘价（Day T 的 open）→ 以大阳线开盘价卖出。
   - 止盈：盘中最高价触及 买入价 × 1.10 → 以 买入价 × 1.10 卖出。
   - 同日同时触发时，止损优先。

【输出】：extra 含 exit_reason；BacktestTrade.trigger_date 为大阳日 T。
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
    low_position_ratio: float = 0.5       # 收盘价 <= 历史最高价 * 0.5
    no_big_gain_lookback: int = 20        # 前 20 个交易日
    no_big_gain_threshold: float = 5.0    # pct_change 单位百分比点（5.0 = 5%）
    yang_gain_pct: float = 0.08           # 大阳涨幅 >= 8%
    volume_multiplier: float = 2.0        # 成交量 >= 前一日 2 倍
    pullback_body_ratio: float = 1 / 3    # 阴线收盘价须在阳线实体上 1/3 之内
    profit_pct: float = 0.10              # 止盈 10%


class DaYangHuiLuoStrategy(StockStrategy):
    """大阳回落法策略实现。"""

    strategy_id = "da_yang_hui_luo"
    version = "v1.1.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="大阳回落法",
            version=self.version,
            short_description="低位大阳线放量，次日阴线回落且收盘在阳线实体1/3之上，以收盘价买入；10%止盈、跌至大阳线开盘价止损。",
            description=(
                "本策略在 A 股日线数据上识别以下形态：\n"
                "1) 低位约束：收盘价不超过截至当日累计历史最高价的一半。\n"
                "2) 近期无大涨：触发日前 20 个交易日内无单日涨幅超 5%。\n"
                "3) 大阳触发（Day T）：涨幅 ≥ 8% 且成交量 ≥ 前一日 2 倍。\n"
                "4) 买入确认（Day T+1）：阴线收盘，收盘价在阳线实体 1/3 之上，以收盘价买入。\n"
                "5) 盈利 10% 止盈，跌至大阳线开盘价止损。"
            ),
            assumptions=[
                "低位约束：收盘价不超过截至当日历史最高价的一半。",
                "近期无大涨：触发日前20个交易日内无单日涨幅超过5%的交易日。",
                "大阳线定义：收盘价较前收涨幅≥8%，且当日为阳线（收盘>开盘）。",
                "放量：当日成交量≥前一交易日成交量的2倍。",
                "买入条件：次日以阴线收盘（收盘<开盘），且收盘价在阳线实体的上1/3区间内。",
                "买入价：T+1 收盘价。",
                "止盈：盘中最高价触及买入价×1.10时，以买入价×1.10卖出。",
                "止损：盘中最低价触及大阳线开盘价时，以大阳线开盘价卖出。",
                "同日同时触发止盈止损时，止损优先。",
                "pct_change 字段单位为百分比点（5.0 = 5%）。",
                "剔除ST/*ST股票。",
                "本策略用于历史验证，不构成投资建议。",
            ],
            risks=[
                "低位大阳后可能继续下跌，回落可能是趋势延续而非暂停。",
                "震荡行情中可能频繁触发止损。",
                "数据缺失、停牌会影响回测结果准确性。",
            ],
            route_path="/strategy/da-yang-hui-luo",
        )

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        """单日选股：筛选 as_of_date 当日满足大阳线触发条件的股票（不要求 T+1 形态）。"""
        p = _Params()
        if as_of_date is None:
            raise ValueError("as_of_date 不能为空")

        db = SessionLocal()
        try:
            items, signals = self._scan_yang_signals(db, as_of_date=as_of_date, p=p)
            return StrategyExecutionResult(
                as_of_date=as_of_date,
                assumptions={
                    "data_granularity": "日线",
                    "price_type": "仅筛选当日大阳线信号，不含买入操作",
                    "pattern": "低位+近期无大涨+大阳放量",
                    "universe": "非 ST/*ST 全市场",
                },
                params={
                    "low_position_ratio": p.low_position_ratio,
                    "no_big_gain_lookback": p.no_big_gain_lookback,
                    "no_big_gain_threshold": p.no_big_gain_threshold,
                    "yang_gain_pct": p.yang_gain_pct,
                    "volume_multiplier": p.volume_multiplier,
                },
                items=items,
                signals=signals,
            )
        finally:
            db.close()

    @staticmethod
    def _scan_yang_signals(
        db, *, as_of_date: date, p: _Params
    ) -> tuple[list[StrategyCandidate], list[StrategySignal]]:
        """扫描 as_of_date 当日满足大阳线条件的股票（Day T 信号）。"""
        lookback_start = as_of_date - timedelta(days=60)

        stmt = (
            select(
                StockDailyBar.stock_code,
                StockDailyBar.trade_date,
                StockDailyBar.open,
                StockDailyBar.high,
                StockDailyBar.low,
                StockDailyBar.close,
                StockDailyBar.volume,
                StockDailyBar.prev_close,
                StockDailyBar.pct_change,
                StockDailyBar.cum_hist_high,
            )
            .where(StockDailyBar.trade_date.between(lookback_start, as_of_date))
            .order_by(StockDailyBar.stock_code, StockDailyBar.trade_date)
        )
        try:
            rows = db.execute(stmt).all()
        except (OperationalError, ProgrammingError) as e:
            raw = str(getattr(e, "orig", e))
            combined = f"{e!s} {raw}"
            if "cum_hist_high" in combined or "1054" in combined or "does not exist" in combined.lower():
                raise RuntimeError(
                    "大阳回落法需 stock_daily_bar.cum_hist_high 字段。请执行相关数据库迁移脚本。"
                    "原始错误: " + raw[:500]
                ) from e
            raise

        stock_info: dict[str, str | None] = dict(
            db.query(StockBasic.code, StockBasic.name).all()
        )
        st_codes = {
            code
            for code, name in stock_info.items()
            if name and (name.startswith("ST") or name.startswith("*ST"))
        }

        stock_bars: dict[str, list[Any]] = defaultdict(list)
        for row in rows:
            if row.stock_code in st_codes:
                continue
            stock_bars[row.stock_code].append(row)

        items: list[StrategyCandidate] = []
        signals: list[StrategySignal] = []

        for code, bars_list in stock_bars.items():
            stock_name = stock_info.get(code)

            for i in range(p.no_big_gain_lookback, len(bars_list)):
                bar_t = bars_list[i]
                if bar_t.trade_date != as_of_date:
                    continue

                # ---- Day T: 基本数据有效性 ----
                if not (
                    bar_t.open
                    and bar_t.close
                    and bar_t.prev_close
                    and bar_t.volume
                    and bar_t.cum_hist_high
                ):
                    continue
                o_t = float(bar_t.open)
                c_t = float(bar_t.close)
                pc_t = float(bar_t.prev_close)
                vol_t = float(bar_t.volume)
                cum_h = float(bar_t.cum_hist_high)
                if o_t <= 0 or c_t <= 0 or pc_t <= 0 or vol_t <= 0 or cum_h <= 0:
                    continue

                # ---- 1) 低位约束 ----
                if c_t > cum_h * p.low_position_ratio:
                    continue

                # ---- 2) 大阳线：涨幅 >= 8% 且阳线 ----
                yang_gain = (c_t - pc_t) / pc_t
                if yang_gain < p.yang_gain_pct:
                    continue
                if c_t <= o_t:
                    continue

                # ---- 3) 放量：成交量 >= 前一日 2 倍 ----
                if i < 1:
                    continue
                bar_prev = bars_list[i - 1]
                if not bar_prev.volume or float(bar_prev.volume) <= 0:
                    continue
                vol_prev = float(bar_prev.volume)
                if vol_t < vol_prev * p.volume_multiplier:
                    continue

                # ---- 4) 近期无大涨：前 20 个交易日 pct_change <= 5.0 ----
                has_big_gain = False
                for j in range(i - p.no_big_gain_lookback, i):
                    bj = bars_list[j]
                    if bj.pct_change is not None and float(bj.pct_change) > p.no_big_gain_threshold:
                        has_big_gain = True
                        break
                if has_big_gain:
                    continue

                # ---- 当日大阳线信号确认 ----
                volume_ratio = round(vol_t / vol_prev, 4)
                summary: dict[str, Any] = {
                    "yang_open": round(o_t, 4),
                    "yang_close": round(c_t, 4),
                    "yang_gain_pct": round(yang_gain * 100, 4),
                    "yang_volume": round(vol_t, 2),
                    "prev_volume": round(vol_prev, 2),
                    "volume_ratio": volume_ratio,
                    "cum_hist_high": round(cum_h, 4),
                    "close_to_cum_hist_high_ratio": round(c_t / cum_h, 6),
                }

                items.append(
                    StrategyCandidate(
                        stock_code=code,
                        stock_name=stock_name,
                        exchange_type=None,
                        trigger_date=as_of_date,
                        summary=summary,
                    ),
                )
                signals.append(
                    StrategySignal(
                        stock_code=code,
                        event_date=as_of_date,
                        event_type="trigger",
                        payload=summary,
                    ),
                )

        return items, signals

    def backtest(self, *, start_date: date, end_date: date) -> BacktestResult:
        p = _Params()
        db = SessionLocal()
        try:
            return self._run_backtest(db, start_date=start_date, end_date=end_date, p=p)
        finally:
            db.close()

    @staticmethod
    def _run_backtest(
        db, *, start_date: date, end_date: date, p: _Params
    ) -> BacktestResult:
        extended_start = start_date - timedelta(days=60)
        extended_end = end_date + timedelta(days=120)

        stmt = (
            select(
                StockDailyBar.stock_code,
                StockDailyBar.trade_date,
                StockDailyBar.open,
                StockDailyBar.high,
                StockDailyBar.low,
                StockDailyBar.close,
                StockDailyBar.volume,
                StockDailyBar.prev_close,
                StockDailyBar.pct_change,
                StockDailyBar.cum_hist_high,
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
                    "大阳回落法需 stock_daily_bar.cum_hist_high 字段。请执行相关数据库迁移脚本。"
                    "原始错误: " + raw[:500]
                ) from e
            raise

        logger.info("大阳回落法回测数据加载完成: %d 条日线记录", len(rows))

        stock_info: dict[str, str | None] = dict(
            db.query(StockBasic.code, StockBasic.name).all()
        )
        st_codes = {
            code
            for code, name in stock_info.items()
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

            for i in range(p.no_big_gain_lookback, len(bars_list) - 1):
                bar_t = bars_list[i]
                trigger_date = bar_t.trade_date
                if trigger_date < start_date or trigger_date > end_date:
                    continue

                # ---- Day T: 基本数据有效性 ----
                if not (
                    bar_t.open
                    and bar_t.close
                    and bar_t.prev_close
                    and bar_t.volume
                    and bar_t.cum_hist_high
                ):
                    continue
                o_t = float(bar_t.open)
                c_t = float(bar_t.close)
                pc_t = float(bar_t.prev_close)
                vol_t = float(bar_t.volume)
                cum_h = float(bar_t.cum_hist_high)
                if o_t <= 0 or c_t <= 0 or pc_t <= 0 or vol_t <= 0 or cum_h <= 0:
                    continue

                # ---- 1) 低位约束 ----
                if c_t > cum_h * p.low_position_ratio:
                    continue

                # ---- 2) 大阳线：涨幅 >= 8% 且阳线 ----
                yang_gain = (c_t - pc_t) / pc_t
                if yang_gain < p.yang_gain_pct:
                    continue
                if c_t <= o_t:
                    continue

                # ---- 3) 放量：成交量 >= 前一日 2 倍 ----
                bar_prev = bars_list[i - 1]
                if not bar_prev.volume or float(bar_prev.volume) <= 0:
                    continue
                vol_prev = float(bar_prev.volume)
                if vol_t < vol_prev * p.volume_multiplier:
                    continue

                # ---- 4) 近期无大涨：前 20 个交易日 pct_change <= 5.0 ----
                has_big_gain = False
                for j in range(i - p.no_big_gain_lookback, i):
                    bj = bars_list[j]
                    if bj.pct_change is not None and float(bj.pct_change) > p.no_big_gain_threshold:
                        has_big_gain = True
                        break
                if has_big_gain:
                    continue

                # ---- 5) Day T+1: 买入确认 ----
                bar_t1 = bars_list[i + 1]
                if not (bar_t1.open and bar_t1.close):
                    continue
                o_t1 = float(bar_t1.open)
                c_t1 = float(bar_t1.close)
                if o_t1 <= 0 or c_t1 <= 0:
                    continue

                # 阴线：收盘 < 开盘
                if c_t1 >= o_t1:
                    continue

                # 收盘价在阳线实体 1/3 之上
                yang_body_one_third = o_t + (c_t - o_t) * p.pullback_body_ratio
                if c_t1 <= yang_body_one_third:
                    continue

                # ---- 信号确认，以 T+1 收盘价买入 ----
                buy_date = bar_t1.trade_date
                buy_price = round(c_t1, 4)
                profit_price = round(buy_price * (1 + p.profit_pct), 4)
                # 止损价 = 大阳线开盘价
                stop_loss_price = round(o_t, 4)
                volume_ratio = round(vol_t / vol_prev, 4)

                extra_base: dict[str, Any] = {
                    "yang_date": trigger_date.isoformat(),
                    "yang_open": round(o_t, 4),
                    "yang_close": round(c_t, 4),
                    "yang_gain_pct": round(yang_gain * 100, 4),
                    "yang_volume": round(vol_t, 2),
                    "prev_volume": round(vol_prev, 2),
                    "volume_ratio": volume_ratio,
                    "pullback_close": round(c_t1, 4),
                    "pullback_open": round(o_t1, 4),
                    "yang_body_one_third_line": round(yang_body_one_third, 4),
                    "cum_hist_high": round(cum_h, 4),
                    "close_to_cum_hist_high_ratio": round(c_t / cum_h, 6),
                    "profit_price": profit_price,
                    "stop_loss_price": stop_loss_price,
                }

                # ---- 交易模拟：止盈止损 ----
                sell_idx: int | None = None
                exit_reason: str | None = None

                for k in range(i + 2, len(bars_list)):
                    bk = bars_list[k]
                    if bk.trade_date > extended_end:
                        break
                    if not (bk.high and bk.low):
                        continue

                    # 止损优先：跌至大阳线开盘价
                    if float(bk.low) <= stop_loss_price:
                        sell_idx = k
                        exit_reason = "止损（跌至大阳线开盘价）"
                        break

                    # 止盈：盈利 10%
                    if float(bk.high) >= profit_price:
                        sell_idx = k
                        exit_reason = f"止盈（盈利{int(p.profit_pct * 100)}%）"
                        break

                if sell_idx is None:
                    trades.append(
                        BacktestTrade(
                            stock_code=code,
                            stock_name=stock_name,
                            buy_date=buy_date,
                            buy_price=buy_price,
                            trade_type="unclosed",
                            trigger_date=trigger_date,
                            extra=extra_base,
                        ),
                    )
                    continue

                sell_bar = bars_list[sell_idx]
                sell_date = sell_bar.trade_date

                if "止损" in exit_reason:
                    sell_price = stop_loss_price
                    return_rate = round((stop_loss_price - buy_price) / buy_price, 4)
                else:
                    sell_price = profit_price
                    return_rate = round(p.profit_pct, 4)

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
                        extra={
                            **extra_base,
                            "exit_reason": exit_reason,
                        },
                    ),
                )

        logger.info("大阳回落法回测扫描完成: trades=%d", len(trades))
        return BacktestResult(trades=trades, skipped_count=0, skip_reasons=[])
