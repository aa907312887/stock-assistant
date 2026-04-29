"""
破 60 日均线买入法（内置策略，`strategy_id`=`ma60_five_day_break`）。

【策略名称】：破 60 日均线买入法

【目标】：当**连续 5 个交易日**收盘价均在**当日** MA60 **下方**，**信号日**收盘**站上** MA60 时，在**下一交易日开盘价**入场；以 **+8% 止盈** 与 **−8% 止损**（买入后按**收盘价**监测，**先止损后止盈**）管理持仓。

【适用范围】：
- 市场：A 股全市场（与现有历史回测默认范围一致），剔除 **ST / *ST** 名称证券。
- 数据粒度：日线；**交易日序列**以 `stock_daily_bar` 中**已落库**的连续行为准，**不**单独处理停牌（无行则不在序列中）。
- 依赖字段：`trade_date`、`open`、`close`、`ma60`（均来自 `stock_daily_bar` 预计算字段）。

【核心规则】：
1) **前 5 日在均线下方**：设信号日下标为 `i`（对应当日 D），则对 `k=1..5`：`close[i-k] < ma60[i-k]`，且各日 `close`/`ma60` 非空。
2) **突破**：`close[i] > ma60[i]`。
3) **买入**：下标 `i+1` 的**开盘价**；`open` 无效或 `≤0` 则**不成交**。
4) **卖出**：自**买入日下一根 K** 起用**收盘价**；先 **≤ 买入×(1−8%)** 止损，再 **≥ 买入×(1+8%)** 止盈，卖出价为触发日**收盘价**。

【关键口径】：止盈/止损均为相对**买入价**的 **8%**；监测价为**收盘价**。

【边界】：
- 单标的**未平仓**前不重复开仓；平仓后自卖出下标之后继续扫描。
- 不足 7 根 K 或任一下标处 `ma60`/`close` 无法比较则**跳过**。

【输出】：回测有 `trigger_date`、成交与 `exit_reason`；**策略选股**仅输出突破日 D 上之收盘/MA60，不演算买卖。
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
    take_profit_pct: float = 0.08
    stop_loss_pct: float = 0.08


def ma60_five_below_and_breakout_at(bars_list: list[Any], i: int) -> bool:
    """
    下标 i 为突破日 D 的形态：D−5..D−1 每根收盘 < 当日 ma60，且 D 日收盘 > 当日 ma60。
    仅要求 i>=5，**不要求**存在 i+1（便于「当日收盘后」选股时最近一根即为 D）。
    """
    if i < 5:
        return False
    for k in range(1, 6):
        b = bars_list[i - k]
        if b.close is None or b.ma60 is None:
            return False
        if not (float(b.close) < float(b.ma60)):
            return False
    b_i = bars_list[i]
    if b_i.close is None or b_i.ma60 is None:
        return False
    return float(b_i.close) > float(b_i.ma60)


def ma60_five_below_then_break_ok(bars_list: list[Any], i: int) -> bool:
    """
    与 `ma60_five_below_and_breakout_at` 相同，但需存在下一根 K（回测/次日开盘买）。
    """
    if not ma60_five_below_and_breakout_at(bars_list, i):
        return False
    return i + 1 < len(bars_list)


def entry_open_at_signal_index(bars_list: list[Any], i: int) -> float | None:
    """
    若下标 i 为有效信号，返回下一日开盘价（4 位小数）；信号不成立或 `open` 无效时返回 `None`。
    """
    if not ma60_five_below_then_break_ok(bars_list, i):
        return None
    buy_bar = bars_list[i + 1]
    if buy_bar.open is None or float(buy_bar.open) <= 0:
        return None
    return round(float(buy_bar.open), 4)


def simulate_exit_close_8_8(
    bars_list: list[Any],
    buy_idx: int,
    buy_price: float,
    p: _Params,
) -> tuple[int | None, float | None, str | None]:
    """买入后自 buy_idx+1 起按收盘价；先 8% 止损再 8% 止盈。"""
    for j in range(buy_idx + 1, len(bars_list)):
        bj = bars_list[j]
        if bj.close is None:
            continue
        cj = float(bj.close)
        if cj <= buy_price * (1.0 - p.stop_loss_pct):
            return j, cj, "stop_loss_8pct"
        if cj >= buy_price * (1.0 + p.take_profit_pct):
            return j, cj, "take_profit_8pct"
    return None, None, None


def _index_of_trade_date(bars_list: list[Any], d: date) -> int | None:
    for idx, b in enumerate(bars_list):
        if b.trade_date == d:
            return idx
    return None


def _load_stock_bars_grouped_by_code(
    db: Any,
    *,
    extended_start: date,
    extended_end: date,
) -> tuple[dict[str, str | None], dict[str, list[Any]]]:
    """仅主板且剔 ST 后，按 code 分组的 `stock_daily_bar` 行（同序）。

    注意：回测的**入场信号**依赖 `ma60`，但**离场**只依赖 `close`。
    因此这里不能因为 `ma60` 为空就丢弃该日 K 线，否则会出现“明明收盘已触发 ±8% 却不卖”的假象。
    """
    stmt = (
        select(
            StockDailyBar.stock_code,
            StockDailyBar.trade_date,
            StockDailyBar.open,
            StockDailyBar.close,
            StockDailyBar.ma60,
        )
        .where(
            StockDailyBar.trade_date.between(extended_start, extended_end),
            StockDailyBar.close.isnot(None),
        )
        .order_by(StockDailyBar.stock_code, StockDailyBar.trade_date)
    )
    rows = db.execute(stmt).all()
    logger.info("破60日均线买入法 回测/选股数据加载: %d 条日线记录（不因 ma60 为空丢行）", len(rows))
    # 本策略约束：只买主板（StockBasic.market == "主板"）
    basic_rows = db.query(StockBasic.code, StockBasic.name, StockBasic.market).all()
    stock_info: dict[str, str | None] = {r.code: r.name for r in basic_rows}
    main_board_codes = {r.code for r in basic_rows if r.market == "主板"}
    st_codes = {
        code
        for code, name in stock_info.items()
        if name and (name.startswith("ST") or name.startswith("*ST"))
    }
    stock_bars: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        if row.stock_code not in main_board_codes:
            continue
        if row.stock_code in st_codes:
            continue
        stock_bars[row.stock_code].append(row)
    return stock_info, stock_bars


def run_ma60_five_day_signal_selection(
    db: Any,
    *,
    as_of_date: date,
) -> tuple[list[StrategyCandidate], list[StrategySignal]]:
    """
    选股用：在 as_of_date 当日 K 上判定「前 5 根收盘均在 ma60 下、当日收盘站上 ma60」。
    不模拟买卖。数据只到 as_of_date，不要求 D+1 日已入库。
    """
    ext_start = as_of_date - timedelta(days=120)
    stock_info, stock_bars = _load_stock_bars_grouped_by_code(
        db, extended_start=ext_start, extended_end=as_of_date
    )
    basic_rows = db.query(StockBasic.code, StockBasic.exchange).all()
    exchange_by_code = {r.code: r.exchange for r in basic_rows}
    items: list[StrategyCandidate] = []
    signals: list[StrategySignal] = []
    n_scanned = 0
    for code, bars_list in stock_bars.items():
        n_scanned += 1
        if len(bars_list) < 6:
            continue
        i = _index_of_trade_date(bars_list, as_of_date)
        if i is None or i < 5:
            continue
        if not ma60_five_below_and_breakout_at(bars_list, i):
            continue
        sig_bar = bars_list[i]
        name = stock_info.get(code)
        ex = exchange_by_code.get(code)
        summary: dict[str, Any] = {
            "selection_mode": "breakout_on_as_of",
            "signal_date": as_of_date.isoformat(),
            "signal_close": float(sig_bar.close) if sig_bar.close is not None else None,
            "signal_ma60": float(sig_bar.ma60) if sig_bar.ma60 is not None else None,
            "pattern": "D-5..D-1 收盘<当日MA60，D 日收盘>当日MA60",
        }
        items.append(
            StrategyCandidate(
                stock_code=code,
                stock_name=name,
                exchange_type=ex,
                trigger_date=as_of_date,
                summary=summary,
            )
        )
        signals.append(
            StrategySignal(
                stock_code=code,
                event_date=as_of_date,
                event_type="trigger",
                payload=dict(summary),
            )
        )
    items.sort(key=lambda c: c.stock_code)
    signals.sort(key=lambda s: s.stock_code)
    logger.info(
        "破60日均线买入法 选股完成: as_of=%s 扫描标=%d 入选=%d",
        as_of_date,
        n_scanned,
        len(items),
    )
    return items, signals


def run_ma60_five_day_break_backtest(
    db,
    *,
    start_date: date,
    end_date: date,
    p: _Params,
) -> BacktestResult:
    """全市场：五日在 MA60 下 + 突破日 + 次日开盘买 + 收盘价 ±8%。"""
    extended_start = start_date - timedelta(days=120)
    extended_end = end_date + timedelta(days=400)
    stock_info, stock_bars = _load_stock_bars_grouped_by_code(
        db, extended_start=extended_start, extended_end=extended_end
    )

    trades: list[BacktestTrade] = []
    skipped = 0
    for code, bars_list in stock_bars.items():
        if len(bars_list) < 7:
            skipped += 1
            continue
        stock_name = stock_info.get(code)
        last_block = -1
        for i in range(5, len(bars_list) - 1):
            if i <= last_block:
                continue
            buy_price = entry_open_at_signal_index(bars_list, i)
            if buy_price is None:
                continue
            buy_bar = bars_list[i + 1]
            buy_date = buy_bar.trade_date
            if buy_date < start_date or buy_date > end_date:
                continue
            sig_bar = bars_list[i]
            trigger_date = sig_bar.trade_date

            extra_base: dict[str, Any] = {
                "pattern_path": "ma60_five_below_break_next_open",
                "signal_date": trigger_date.isoformat(),
                "signal_close": float(sig_bar.close) if sig_bar.close is not None else None,
                "signal_ma60": float(sig_bar.ma60) if sig_bar.ma60 is not None else None,
                "buy_rule": "open_on_next_trading_day_after_signal",
                "sell_rule": "close_take_profit_8pct_or_stop_loss_8pct_stop_first",
                "take_profit_pct": p.take_profit_pct,
                "stop_loss_pct": p.stop_loss_pct,
            }

            buy_idx = i + 1
            sell_j, sell_px, exit_reason = simulate_exit_close_8_8(
                bars_list, buy_idx, buy_price, p
            )

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

    logger.info("破60日均线买入法 回测扫描完成: trades=%d skipped_short=%d", len(trades), skipped)
    return BacktestResult(trades=trades, skipped_count=skipped, skip_reasons=[])


class Ma60FiveDayBreakStrategy(StockStrategy):
    """
    破 60 日均线买入法（`ma60_five_day_break`）策略入口。

    与模块级说明一致；补充**示例**（仅示意价格与下标，非真实代码）：

    - **例 1（满足）**：D−5～D−1 每日收盘 9.0、MA60=10.0；D 日收盘 11.0>10.0；D+1 开盘 10.0 成交；之后某日收盘 ≤9.2 或 ≥10.8 则平仓。
    - **例 2（不满足）**：D−1 日收盘 10.5≥MA60=10.0，则 D 日不视为有效「五日在下」链，不发出本策略信号。
    """

    strategy_id = "ma60_five_day_break"
    version = "v1.0.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="破60日均线买入法",
            version=self.version,
            short_description=(
                "选股：截止日若满足前 5 根收盘均在 MA60 下、当日收盘站上 MA60 则入选（突破日即截止日）。"
                "历史回测中：突破次日开盘价买、收盘价 ±8% 先损后盈；时间轴为库中连续 K。"
            ),
            description=(
                "**策略选股（本页/execute）**：在**截止日**这根 K 上判定：D−5～D−1 每日 **收盘 < 当日 MA60**；D 日 **收盘 > 当日 MA60**；"
                "**不**做买卖与持仓模拟。\n"
                "**历史回测（backtest）**：在 D 满足上式且存在 **D+1** 日 K 时，**下一交易日开盘价** 买入；自买入次日起按 **收盘价** 相对买价先 **止损 −8%** 再 **止盈 +8%**。\n"
                "剔除 ST/*ST；时间轴**仅**含已落库日线。不构成投资建议。"
            ),
            assumptions=[
                "MA60 与日线任务预计算一致；前复权口径与全站回测一致。",
                "前 5 日为表内连续 5 个「有 K」的交易日；缺行即不在序列中，不单独处理停牌。",
                "K 线数量过少或 `ma60` 不可比时本策略不触发信号。",
                "止盈/止损为收盘价、先损后盈；同区间重复回测无随机分支。",
            ],
            risks=[
                "次日开盘跳空会改变实际入场价。",
                "整理形态反复上下穿 MA60 时信号可能较密（单仓策略仅首段）。",
            ],
            route_path="/strategy/ma60-five-day-break",
        )

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        p = _Params()
        db = SessionLocal()
        try:
            dd = as_of_date or get_latest_bar_date(db, "daily")
            if dd is None:
                raise RuntimeError("日线数据为空，无法执行破60日均线买入法选股")
            # 选股：截止日 = 突破日 D（当日已站上 MA60 且前 5 日均在下），不做资金/买卖模拟
            items, signals = run_ma60_five_day_signal_selection(db, as_of_date=dd)
            return StrategyExecutionResult(
                as_of_date=dd,
                assumptions={
                    "data_granularity": "日线",
                    "pattern": "选股仅识别突破日 D；回测中 D+1 开盘买、±8% 收盘监测见历史回测",
                    "universe": "非 ST/*ST 全市场",
                },
                params={
                    "take_profit_pct": p.take_profit_pct,
                    "stop_loss_pct": p.stop_loss_pct,
                    "note": "止盈止损参数仅用于回测，策略选股不模拟成交",
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
            return run_ma60_five_day_break_backtest(db, start_date=start_date, end_date=end_date, p=p)
        finally:
            db.close()
