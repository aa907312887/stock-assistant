"""
月 MACD 翻红（内置策略，`strategy_id`=`yue_macd_fan_hong`）。

【策略名称】：月 MACD 翻红

【目标】：在月线 MACD **绿转红**后的**首个红柱月**于该月**最后一个交易日收盘**买入；
持仓后按 **±20% 止盈止损** 或 **后续任一月 MACD 红转绿**（该月最后交易日收盘）平仓。

【适用范围】：
- 市场：A 股**主板**（`stock_basic.market == "主板"`），**不买**创业板、科创板；剔除 **ST / *ST**。
- 数据粒度：月线触发买入；日线用于买卖价与 ±20% 监测。
- 依赖字段：日线 `close`；月线 `trade_month_end`、`macd_hist`。

【核心规则】：
1) **选股（execute）**：截止日对齐的最近月线 **前一月绿、当月红**（首个红柱月绿转红）；**不**演算 ±20% 或月末卖出。
2) **买入（回测/模拟）**：相邻月线 **M−1 绿、M 红**；于 **M 月最后一个交易日 T_buy** 以**收盘价**买入。
3) **止盈**：自 T_buy 次日起，收盘 ≥ 买入价×120%。
4) **止损**：自 T_buy 次日起，收盘 ≤ 买入价×80%。
5) **月线卖出**：买入月之后任一月 **Mk−1 红、Mk 绿**，于 **Mk 月最后交易日** 收盘卖。

【关键口径与阈值】：
- 20 点 = 相对买入价 **20%**（非绝对价位差）。
- MACD 颜色：`macd_hist > 0` 红柱，`≤ 0` 绿柱。
- 同日多条件优先级：① 止损 → ② 止盈 → ③ 月线红转绿。

【边界与异常】：
- 缺月线/hist 或 T_buy 无有效收盘则跳过；单标的未平仓前不重复开仓；T_buy 无收盘不顺延。

【输出与可追溯性】：
- 回测/模拟 `trigger_date=buy_date=T_buy`；`extra.exit_reason` 区分三类离场。

【示例】：
- 1 月绿、2 月红 → 2 月最后交易日收盘买；3 月仍红、4 月绿 → 4 月最后交易日 MACD 卖。
- 买入后某交易日收盘达 +20% → 当日止盈，不等待月线转绿。
"""

from __future__ import annotations

import bisect
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.database import SessionLocal
from app.models import StockBasic, StockDailyBar, StockMonthlyBar
from app.services.screening_service import get_latest_bar_date
from app.services.strategy.strategies.chun_zheng_ma_duotou import (
    _load_stock_exchanges,
    _load_stock_names,
)
from app.services.strategy.strategies.lian_xu_da_ban import _load_main_board_non_st_codes
from app.services.strategy.strategies.duo_zhou_qi_macd_gong_zhen import (
    _build_period_hist_index,
    _hist_val,
    _is_green,
    _is_red,
    _latest_period_entry,
)
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

STRATEGY_ID = "yue_macd_fan_hong"


@dataclass(frozen=True)
class _Params:
    take_profit_pct: float = 0.20
    stop_loss_pct: float = 0.20


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def monthly_green_to_red_at_as_of(
    monthly_series: list[tuple[date, float]],
    as_of: date,
) -> tuple[date, float, date, float] | None:
    """
    截止日对齐的最近月线为红柱，且前一月为绿柱（绿转红形态）。

    返回 (prev_month_end, prev_hist, curr_month_end, curr_hist) 或 None。
    """
    if len(monthly_series) < 2:
        return None
    ends = [t[0] for t in monthly_series]
    idx = bisect.bisect_right(ends, as_of) - 1
    if idx < 1:
        return None
    prev_end, prev_h = monthly_series[idx - 1]
    curr_end, curr_h = monthly_series[idx]
    if _is_green(prev_h) and _is_red(curr_h):
        return (prev_end, prev_h, curr_end, curr_h)
    return None


def is_first_red_month_pick_at_as_of(
    monthly_series: list[tuple[date, float]],
    as_of: date,
) -> tuple[date, float, date, float] | None:
    """
    策略选股：截止日处于「首个红柱月」且月 MACD 刚绿转红。

    - 红柱月 bar 须已落盘（as_of >= curr_month_end）
    - 截止日自然月不得晚于红柱月（否则已进入次月）
    """
    transition = monthly_green_to_red_at_as_of(monthly_series, as_of)
    if transition is None:
        return None
    _prev_end, _prev_h, curr_end, _curr_h = transition
    if as_of < curr_end:
        return None
    if (as_of.year, as_of.month) > (curr_end.year, curr_end.month):
        return None
    return transition


def monthly_green_to_red_pairs(
    monthly_series: list[tuple[date, float]],
) -> list[tuple[int, int]]:
    """返回相邻月线下标 (prev_i, curr_i)，满足前月绿、当月红。"""
    pairs: list[tuple[int, int]] = []
    for i in range(1, len(monthly_series)):
        prev_h = monthly_series[i - 1][1]
        curr_h = monthly_series[i][1]
        if _is_green(prev_h) and _is_red(curr_h):
            pairs.append((i - 1, i))
    return pairs


def build_month_last_trade_dates(
    daily_bars: list[Any],
    monthly_series: list[tuple[date, float]],
) -> dict[date, date]:
    """`trade_month_end → 该月最后一个有日线的 trade_date`。"""
    if not monthly_series or not daily_bars:
        return {}
    month_last: dict[date, date] = {}
    for bar in daily_bars:
        d = bar.trade_date
        entry = _latest_period_entry(monthly_series, d)
        if entry is None:
            continue
        m_end = entry[0]
        prev = month_last.get(m_end)
        if prev is None or d > prev:
            month_last[m_end] = d
    return month_last


def monthly_red_to_green_at(
    monthly_series: list[tuple[date, float]],
    month_end: date,
) -> bool:
    """给定月 `month_end`，判定前一月红柱、当月绿柱。"""
    for i in range(1, len(monthly_series)):
        if monthly_series[i][0] == month_end:
            return _is_red(monthly_series[i - 1][1]) and _is_green(monthly_series[i][1])
    return False


def is_last_trading_day_of_month(
    trade_date: date,
    month_last_trade: dict[date, date],
    monthly_series: list[tuple[date, float]],
) -> bool:
    entry = _latest_period_entry(monthly_series, trade_date)
    if entry is None:
        return False
    m_end = entry[0]
    last_d = month_last_trade.get(m_end)
    return last_d is not None and last_d == trade_date


def simulate_exit_after_buy(
    bars_list: list[Any],
    buy_idx: int,
    buy_price: float,
    end_date: date,
    monthly_series: list[tuple[date, float]],
    buy_month_end: date,
    month_last_trade: dict[date, date],
    p: _Params,
) -> tuple[int | None, float | None, str | None]:
    """
    自 buy_idx+1 起按收盘价监测；顺序：−20% 止损 → +20% 止盈 → 买入月之后月末 MACD 红转绿。
    """
    for k in range(buy_idx + 1, len(bars_list)):
        bk = bars_list[k]
        if bk.trade_date > end_date:
            break
        if bk.close is None:
            continue
        ck = float(bk.close)

        if ck <= buy_price * (1.0 - p.stop_loss_pct):
            return k, ck, "stop_loss_20pct"

        if ck >= buy_price * (1.0 + p.take_profit_pct):
            return k, ck, "take_profit_20pct"

        if is_last_trading_day_of_month(bk.trade_date, month_last_trade, monthly_series):
            entry = _latest_period_entry(monthly_series, bk.trade_date)
            if entry is not None:
                curr_month_end = entry[0]
                if curr_month_end > buy_month_end:
                    if monthly_red_to_green_at(monthly_series, curr_month_end):
                        return k, ck, "sell_monthly_macd_red_to_green"

    return None, None, None


def _load_daily_bars_grouped(
    db: Any,
    *,
    extended_start: date,
    extended_end: date,
) -> tuple[dict[str, str | None], dict[str, list[Any]]]:
    stmt = (
        select(
            StockDailyBar.stock_code,
            StockDailyBar.trade_date,
            StockDailyBar.close,
        )
        .where(
            StockDailyBar.trade_date.between(extended_start, extended_end),
            StockDailyBar.close.isnot(None),
        )
        .order_by(StockDailyBar.stock_code, StockDailyBar.trade_date)
    )
    rows = db.execute(stmt).all()

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
    logger.info(
        "%s 日线加载: %d 条 → 主板非ST %d 只",
        STRATEGY_ID,
        len(rows),
        len(stock_bars),
    )
    return stock_info, stock_bars


def run_yue_macd_fan_hong_backtest(
    db: Any,
    *,
    start_date: date,
    end_date: date,
    p: _Params,
) -> BacktestResult:
    extended_start = start_date - timedelta(days=120)
    extended_end = end_date + timedelta(days=1500)

    stock_info, stock_bars = _load_daily_bars_grouped(
        db, extended_start=extended_start, extended_end=extended_end
    )

    m_rows = db.execute(
        select(
            StockMonthlyBar.stock_code,
            StockMonthlyBar.trade_month_end,
            StockMonthlyBar.macd_hist,
        ).where(
            StockMonthlyBar.trade_month_end.between(extended_start, extended_end),
        )
    ).all()
    monthly_by_code = _build_period_hist_index(m_rows, end_attr="trade_month_end")

    trades: list[BacktestTrade] = []
    skipped = 0
    for code, bars_list in stock_bars.items():
        monthly_series = monthly_by_code.get(code, [])
        if len(monthly_series) < 2:
            skipped += 1
            continue

        month_last_trade = build_month_last_trade_dates(bars_list, monthly_series)
        date_to_idx = {bar.trade_date: i for i, bar in enumerate(bars_list)}
        pairs = monthly_green_to_red_pairs(monthly_series)
        last_block = -1

        for prev_i, curr_i in pairs:
            m_end = monthly_series[curr_i][0]
            prev_m_end = monthly_series[prev_i][0]
            t_buy = month_last_trade.get(m_end)
            if t_buy is None:
                continue
            if t_buy < start_date or t_buy > end_date:
                continue

            buy_idx = date_to_idx.get(t_buy)
            if buy_idx is None:
                continue
            if buy_idx <= last_block:
                continue

            buy_bar = bars_list[buy_idx]
            if buy_bar.close is None or float(buy_bar.close) <= 0:
                continue

            buy_price = round(float(buy_bar.close), 4)
            buy_date = t_buy
            trigger_date = t_buy
            stock_name = stock_info.get(code)

            extra_base: dict[str, Any] = {
                "buy_rule": "month_first_red_last_day_close",
                "sell_rule": "close_triggered_multi_exit",
                "buy_month_end": m_end.isoformat(),
                "prev_month_end": prev_m_end.isoformat(),
                "macd_hist_buy_month": monthly_series[curr_i][1],
                "macd_hist_prev_month": monthly_series[prev_i][1],
            }

            sell_j, sell_px, exit_reason = simulate_exit_after_buy(
                bars_list,
                buy_idx,
                buy_price,
                end_date,
                monthly_series,
                m_end,
                month_last_trade,
                p,
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
            sell_month_end = _latest_period_entry(monthly_series, sell_date)
            extra_sell: dict[str, Any] = {
                **extra_base,
                "exit_reason": exit_reason,
            }
            if sell_month_end is not None:
                extra_sell["sell_month_end"] = sell_month_end[0].isoformat()

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
                    extra=extra_sell,
                ),
            )
            last_block = sell_j

    logger.info("%s 回测完成: trades=%d skipped_short=%d", STRATEGY_ID, len(trades), skipped)
    return BacktestResult(trades=trades, skipped_count=skipped, skip_reasons=[])


def run_yue_macd_fan_hong_execute(
    db: Any,
    *,
    as_of_date: date,
) -> StrategyExecutionResult:
    """全市场扫描：截止日对齐月 MACD 绿转红（前一月绿、当月红）的主板非 ST 标的。"""
    universe = _load_main_board_non_st_codes(db)
    names = _load_stock_names(db)
    exchanges = _load_stock_exchanges(db)

    m_rows = db.execute(
        select(
            StockMonthlyBar.stock_code,
            StockMonthlyBar.trade_month_end,
            StockMonthlyBar.macd_hist,
        ).where(
            StockMonthlyBar.trade_month_end <= as_of_date,
        )
    ).all()
    monthly_by_code = _build_period_hist_index(m_rows, end_attr="trade_month_end")

    daily_rows = db.execute(
        select(StockDailyBar.stock_code, StockDailyBar.close).where(
            StockDailyBar.trade_date == as_of_date,
        )
    ).all()
    close_by_code = {
        r.stock_code: _to_float(r.close)
        for r in daily_rows
        if r.stock_code in universe
    }

    items: list[StrategyCandidate] = []
    signals: list[StrategySignal] = []
    for code in sorted(universe):
        series = monthly_by_code.get(code, [])
        transition = is_first_red_month_pick_at_as_of(series, as_of_date)
        if transition is None:
            continue
        prev_end, prev_h, curr_end, curr_h = transition
        items.append(
            StrategyCandidate(
                stock_code=code,
                stock_name=names.get(code),
                exchange_type=exchanges.get(code),
                trigger_date=as_of_date,
                summary={
                    "prev_month_end": prev_end.isoformat(),
                    "buy_month_end": curr_end.isoformat(),
                    "macd_hist_prev_month": prev_h,
                    "macd_hist_buy_month": curr_h,
                    "close": close_by_code.get(code),
                },
            )
        )
        signals.append(
            StrategySignal(
                stock_code=code,
                event_date=as_of_date,
                event_type="trigger",
                payload={
                    "prev_month_end": prev_end.isoformat(),
                    "buy_month_end": curr_end.isoformat(),
                    "monthly_macd_green_to_red": True,
                },
            )
        )

    logger.info(
        "%s 选股: as_of=%s 入选=%d",
        STRATEGY_ID,
        as_of_date,
        len(items),
    )
    return StrategyExecutionResult(
        as_of_date=as_of_date,
        assumptions={
            "data_granularity": "月线",
            "stock_universe": "主板(排除ST/*ST)",
            "filter": "latest monthly bar at as_of: prev green, curr red (first red month)",
        },
        params={
            "monthly": "trade_month_end <= as_of; prev macd_hist <= 0; curr macd_hist > 0",
        },
        items=items,
        signals=signals,
    )


class YueMacdFanHongStrategy(StockStrategy):
    """月 MACD 翻红策略入口。"""

    strategy_id = STRATEGY_ID
    version = "v1.0.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="月 MACD 翻红",
            version=self.version,
            short_description=(
                "主板；选股：月MACD绿转红(首红柱月)；回测/模拟：该月最后交易日收盘买；"
                "±20%止盈止损；后续任一月MACD红转绿月末卖。"
            ),
            description=(
                "**股票范围**：仅 **主板**（`stock_basic.market == \"主板\"`），不买创业板、科创板；剔除 ST/*ST。\n"
                "**选股（execute）**：截止日对齐的最近月线 **前一月绿柱、当月红柱**；且截止日 **≥ 红柱月 bar 落盘日**、截止日自然月 **不晚于红柱月**（仍处于首个红柱月）。\n"
                "**买入（回测/模拟）**：于该红柱月**最后一个交易日**以**收盘价**买入。\n"
                "**卖出**（满足其一）：① 收盘盈利 ≥ **20%**；② 收盘亏损 ≥ **20%**；"
                "③ 买入月之后任一月 MACD **红转绿**，于该月**最后交易日**收盘卖出。\n"
                "监测与成交均为**收盘价**；长期持仓策略，信号稀疏。不构成投资建议。"
            ),
            assumptions=[
                "月线 macd_hist 已预计算；红柱 hist>0，绿柱 hist≤0。",
                "回测/模拟仅扫描 stock_basic.market 为「主板」的标的。",
                "买入日 trigger_date 与 buy_date 均为首个红柱月最后交易日。",
                "历史模拟与历史回测共用同一策略信号口径。",
            ],
            risks=[
                "月线 MACD 未回填的标的不会产生买入信号。",
                "持仓可能跨越回测 end_date 仍未平仓，记为 unclosed。",
            ],
            route_path="/strategy/yue-macd-fan-hong",
        )

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        if as_of_date is None:
            db = SessionLocal()
            try:
                as_of_date = get_latest_bar_date(db, "daily")
            finally:
                db.close()
        if as_of_date is None:
            raise ValueError("as_of_date 不能为空且无法从日线推断最新交易日")
        db = SessionLocal()
        try:
            return run_yue_macd_fan_hong_execute(db, as_of_date=as_of_date)
        finally:
            db.close()

    def backtest(self, *, start_date: date, end_date: date) -> BacktestResult:
        db = SessionLocal()
        try:
            return run_yue_macd_fan_hong_backtest(
                db,
                start_date=start_date,
                end_date=end_date,
                p=_Params(),
            )
        finally:
            db.close()
