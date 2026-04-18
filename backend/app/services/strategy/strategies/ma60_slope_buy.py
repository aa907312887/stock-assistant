"""
60 日均线买入法（内置策略，`strategy_id`=`ma60_slope_buy`）。

【策略名称】：60 日均线买入法（简化版）

【目标】：当 MA60 斜率 **前 3 个交易日均为负**、**当日斜率转正为正**，且当日 **MA5>MA10>MA20 多头排列** 时，在 **下一交易日开盘价** 入场；以 **+15% 止盈** 与 **-8% 止损**（买入后按 **收盘价** 监测与成交）管理持仓。

【适用范围】：
- 市场：A 股全市场（与现有历史回测默认范围一致），剔除 **ST / *ST** 名称证券。
- 数据粒度：日线。
- 依赖字段：`trade_date`、`open`、`close`、`ma60`、`ma5`、`ma10`、`ma20`（均来自 `stock_daily_bar` 预计算字段）。

【核心规则】：
1) **MA60 斜率**：交易日下标 \(i\) 的斜率 \(s(i)=MA60(i)-MA60(i-1)\)（`ma60` 相邻日差分）；\(s(i)>0\) 为向上，\(s(i)<0\) 为向下；**等于 0 不满足**正/负判定。
2) **信号日（下标 \(i\)）**须同时满足：
   - **前 3 日斜率为负**：\(s(i-3)<0\)、\(s(i-2)<0\)、\(s(i-1)<0\)；
   - **当日转正**：\(s(i)>0\)；
   - **多头排列**：当日 `ma5 > ma10 > ma20`（均非空）。
3) **买入**：**信号日下一根 K 线**的 **开盘价**；若次日无数据、`open` 为空或 \(\le 0\)，则**不成交**、不生成该笔。
4) **卖出**：自**买入日次日**起逐日仅用 **收盘价** 相对买入价；**先止损**（\(\le\) 买入×0.92）再 **止盈**（\(\ge\) 买入×1.15），卖出价为触发日 **收盘价**。

【关键口径】：
- 止盈 +15%、止损 −8%（相对买入价，收盘价判定）。

【边界】：
- `ma60`/`ma5`/`ma10`/`ma20` 任一缺失则该日不做信号判定。
- 单标的未平仓前不重复开仓；平仓后从卖出日之后继续扫描。

【输出】：
- `trigger_date`：信号日 \(i\)；`buy_date`：次日；`extra` 记录四日斜率及信号日均线值、`buy_rule`。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select

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
    """固定阈值（与规格一致）。"""

    take_profit_pct: float = 0.15
    stop_loss_pct: float = 0.08


def _slope_ma60(bars_list: list[Any], i: int) -> float | None:
    """下标 i 当日 MA60 斜率：MA60(i)−MA60(i−1)；需 i≥1。"""
    if i < 1 or i >= len(bars_list):
        return None
    prev, cur = bars_list[i - 1].ma60, bars_list[i].ma60
    if prev is None or cur is None:
        return None
    return float(cur) - float(prev)


def ma60_signal_next_open_ok(bars_list: list[Any], signal_idx: int) -> bool:
    """
    信号日下标 `signal_idx` = i：前 3 日斜率均负、当日斜率为正、当日 MA5>MA10>MA20；
    且存在下一根 K 线可供开盘买入（由调用方再验 open）。
    需 i>=4 且 i+1 < len(bars_list)。
    """
    i = signal_idx
    if i < 4 or i + 1 >= len(bars_list):
        return False
    for j in range(i - 3, i + 1):
        bj = bars_list[j]
        if bj.ma60 is None or bj.close is None:
            return False
    bar_i = bars_list[i]
    if bar_i.ma5 is None or bar_i.ma10 is None or bar_i.ma20 is None:
        return False
    if not (bar_i.ma5 > bar_i.ma10 > bar_i.ma20):
        return False
    for idx in (i - 3, i - 2, i - 1):
        s = _slope_ma60(bars_list, idx)
        if s is None or s >= 0:
            return False
    s_today = _slope_ma60(bars_list, i)
    if s_today is None or s_today <= 0:
        return False
    return True


def simulate_exit_close_only(
    bars_list: list[Any],
    buy_idx: int,
    buy_price: float,
    p: _Params,
) -> tuple[int | None, float | None, str | None]:
    """买入后自 buy_idx+1 起按收盘价监测；先止损后止盈。"""
    for j in range(buy_idx + 1, len(bars_list)):
        bj = bars_list[j]
        if bj.close is None:
            continue
        cj = float(bj.close)
        if cj <= buy_price * (1.0 - p.stop_loss_pct):
            return j, cj, "stop_loss_8pct"
        if cj >= buy_price * (1.0 + p.take_profit_pct):
            return j, cj, "take_profit_15pct"
    return None, None, None


def run_ma60_slope_buy_backtest(
    db,
    *,
    start_date: date,
    end_date: date,
    p: _Params,
) -> BacktestResult:
    """全市场扫描：MA60 三负一正 + 均线多头 + 次日开盘买 + 收盘价止盈止损。"""
    extended_start = start_date - timedelta(days=120)
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
            StockDailyBar.ma60,
        )
        .where(
            StockDailyBar.trade_date.between(extended_start, extended_end),
            StockDailyBar.close.isnot(None),
            StockDailyBar.ma60.isnot(None),
        )
        .order_by(StockDailyBar.stock_code, StockDailyBar.trade_date)
    )
    rows = db.execute(stmt).all()
    logger.info("60日均线买入法回测数据加载完成: %d 条日线记录", len(rows))

    stock_info: dict[str, str | None] = dict(db.query(StockBasic.code, StockBasic.name).all())
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
    skipped = 0
    for code, bars_list in stock_bars.items():
        if len(bars_list) < 6:
            skipped += 1
            continue
        stock_name = stock_info.get(code)
        last_block = -1
        for i in range(4, len(bars_list) - 1):
            if i <= last_block:
                continue
            if not ma60_signal_next_open_ok(bars_list, i):
                continue
            buy_bar = bars_list[i + 1]
            buy_date = buy_bar.trade_date
            if buy_date < start_date or buy_date > end_date:
                continue
            if buy_bar.open is None or float(buy_bar.open) <= 0:
                continue
            buy_price = round(float(buy_bar.open), 4)
            sig_bar = bars_list[i]
            trigger_date = sig_bar.trade_date

            s_m3 = _slope_ma60(bars_list, i - 3)
            s_m2 = _slope_ma60(bars_list, i - 2)
            s_m1 = _slope_ma60(bars_list, i - 1)
            s0 = _slope_ma60(bars_list, i)
            if s_m3 is None or s_m2 is None or s_m1 is None or s0 is None:
                continue

            extra_base: dict[str, Any] = {
                "pattern_path": "ma60_3neg_1pos_ma5_bull_next_open",
                "slope_ma60_day_minus_3": round(s_m3, 6),
                "slope_ma60_day_minus_2": round(s_m2, 6),
                "slope_ma60_day_minus_1": round(s_m1, 6),
                "slope_ma60_signal_day": round(s0, 6),
                "signal_day_ma5": float(sig_bar.ma5) if sig_bar.ma5 is not None else None,
                "signal_day_ma10": float(sig_bar.ma10) if sig_bar.ma10 is not None else None,
                "signal_day_ma20": float(sig_bar.ma20) if sig_bar.ma20 is not None else None,
                "turn_date": trigger_date.isoformat(),
                "buy_rule": "open_on_next_trading_day_after_signal",
                "sell_rule": "close_take_profit_15pct_or_stop_loss_8pct_stop_first",
                "take_profit_pct": p.take_profit_pct,
                "stop_loss_pct": p.stop_loss_pct,
            }

            buy_idx = i + 1
            sell_j, sell_px, exit_reason = simulate_exit_close_only(bars_list, buy_idx, buy_price, p)

            if sell_j is None or exit_reason is None or sell_px is None:
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
                last_block = len(bars_list)
                break

            sell_bar = bars_list[sell_j]
            sell_date = sell_bar.trade_date
            sell_price = round(float(sell_px), 4)
            return_rate = round((sell_price - buy_price) / buy_price, 6)
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
                    extra={**extra_base, "exit_reason": exit_reason},
                ),
            )
            last_block = sell_j

    logger.info("60日均线买入法回测扫描完成: trades=%d skipped_short=%d", len(trades), skipped)
    return BacktestResult(trades=trades, skipped_count=skipped, skip_reasons=[])


class Ma60SlopeBuyStrategy(StockStrategy):
    strategy_id = "ma60_slope_buy"
    version = "v1.2.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="60日均线买入法",
            version=self.version,
            short_description=(
                "MA60 斜率前 3 日为负、当日转正，且当日 MA5>MA10>MA20 时，次日开盘价买入；"
                "持仓后按收盘价 +15% 止盈或 -8% 止损（先判止损）。"
            ),
            description=(
                "记 \(s(i)=MA60(i)-MA60(i-1)\)。**信号日** \(i\)：\(s(i-3),s(i-2),s(i-1)<0\)，\(s(i)>0\)，"
                "且当日 **MA5>MA10>MA20**（表字段，均非空）。\n"
                "**买入**：信号日 **下一交易日开盘价**；无有效 `open` 则不成交。\n"
                "**卖出**：自买入次日起按 **收盘价**；先 **≤ 买入×0.92** 止损，再 **≥ 买入×1.15** 止盈。\n"
                "剔除 ST/*ST；不构成投资建议。"
            ),
            assumptions=[
                "MA60/MA5/MA10/MA20 与日线任务预计算一致。",
                "止盈止损为收盘价口径；买入价为次日开盘价。",
                "同一标的未平仓前不重复扫描后续信号。",
            ],
            risks=[
                "次日开盘跳空可能放大滑点与回测偏差。",
                "震荡市均线多头与 MA60 拐头可能频繁交替。",
            ],
            route_path="/strategy/ma60-slope-buy",
        )

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        """单日扫描：返回「买入日 as_of_date 以开盘价成交」的候选（信号日为前一交易日）。"""
        p = _Params()
        db = SessionLocal()
        try:
            dd = as_of_date or get_latest_bar_date(db, "daily")
            if dd is None:
                raise RuntimeError("日线数据为空，无法执行 60 日均线买入法选股")
            result = run_ma60_slope_buy_backtest(db, start_date=dd, end_date=dd, p=p)
            basics = {r.code: r.exchange for r in db.query(StockBasic.code, StockBasic.exchange).all()}
            items: list[StrategyCandidate] = []
            signals: list[StrategySignal] = []
            for t in result.trades:
                if t.buy_date != dd:
                    continue
                summary: dict[str, Any] = dict(t.extra or {})
                summary["buy_date"] = t.buy_date.isoformat()
                summary["buy_price"] = t.buy_price
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
                        exchange_type=basics.get(t.stock_code),
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
                    "pattern": "MA60 三负一正 + MA5>MA10>MA20，次日开盘买",
                    "universe": "非 ST/*ST 全市场",
                },
                params={
                    "take_profit_pct": p.take_profit_pct,
                    "stop_loss_pct": p.stop_loss_pct,
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
            return run_ma60_slope_buy_backtest(db, start_date=start_date, end_date=end_date, p=p)
        finally:
            db.close()
