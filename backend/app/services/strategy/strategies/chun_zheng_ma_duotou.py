"""
纯正均线多头排列（内置策略，`strategy_id`=`chun_zheng_ma_duotou`）。

【策略名称】：纯正均线多头排列

【目标】：在**不做**「首次出现」「低位」「量能」等附加约束的前提下，筛出**当日**满足 **MA5 > MA10 > MA20** 的标的，供历史模拟交易「内置策略选股」与专题执行同源使用；历史回测侧提供与破 60 日均线法一致的**次日开盘买 + 收盘价 ±8%（先损后盈）**占位仿真，便于区间统计与历史模拟任务跑通。

【适用范围】：
- 市场：A 股；剔除 **ST / *ST** 及 **北交所**（与现有内置策略常见口径一致）。
- 数据粒度：日线；依赖 `stock_daily_bar` 的 `ma5` / `ma10` / `ma20`（及回测用到的 `open` / `high` / `low` / `close`）。

【核心规则】：
1) **选股（execute）**：`trade_date == as_of_date` 且 `ma5`、`ma10`、`ma20` 均有值，且 **MA5 > MA10 > MA20**。
2) **回测（backtest）**：任意交易日 i 满足上式、且存在 i+1 根 K、`open` 有效则 **i+1 日开盘价买入**；之后按 **收盘价** 先 **−8% 止损** 再 **+8% 止盈**（与 `ma60_five_day_break` 离场函数一致）；单标的未平仓前不重复开仓。

【关键口径】：「纯正」指**仅**三线大小关系，不含「三线较昨日抬高」「前 N 日不得多头」等条件（与 `duo_tou_pai_lie` 区分）。

【边界】：均线字段缺失则该股当日不入选；时间序列为库中连续日线，不单独补停牌。

【输出】：选股 `summary` 带 ma5/ma10/ma20/close；回测 `trigger_date` 为信号日，`extra` 记录买卖规则说明。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, select

from app.database import SessionLocal
from app.models import StockBasic, StockDailyBar
from app.services.strategy.strategies.ma60_five_day_break import (
    _Params as Ma60ExitParams,
    simulate_exit_close_8_8,
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


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def is_pure_ma_bull_order_bar(bar: Any) -> bool:
    """当日是否满足 MA5 > MA10 > MA20（均有值）。"""
    if bar.ma5 is None or bar.ma10 is None or bar.ma20 is None:
        return False
    return bar.ma5 > bar.ma10 > bar.ma20


@dataclass(frozen=True)
class _ExitParams:
    take_profit_pct: float = 0.08
    stop_loss_pct: float = 0.08


def _load_excluded_codes(db: Any) -> set[str]:
    basics = db.execute(select(StockBasic)).scalars().all()
    excluded: set[str] = set()
    for b in basics:
        if b.exchange == "BSE":
            excluded.add(b.code)
        elif b.name and ("ST" in b.name.upper()):
            excluded.add(b.code)
    return excluded


def _load_stock_names(db: Any) -> dict[str, str]:
    basics = db.execute(select(StockBasic)).scalars().all()
    return {x.code: x.name for x in basics}


def _load_stock_exchanges(db: Any) -> dict[str, str]:
    basics = db.execute(select(StockBasic)).scalars().all()
    return {x.code: x.exchange for x in basics}


class ChunZhengMaDuotouStrategy(StockStrategy):
    """纯正均线多头排列：选股仅 MA5>MA10>MA20；回测为次日开买 + 收盘 ±8%（先损后盈）。"""

    strategy_id = "chun_zheng_ma_duotou"
    version = "v1.0.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="纯正均线多头排列",
            version=self.version,
            short_description="选股：当日 MA5>MA10>MA20，无其它附加过滤。回测：次日开盘买、收盘 ±8% 先损后盈（与破60日均线离场一致）。",
            description=(
                "**策略选股（execute）**：在截止日这根日线上，若 **MA5 > MA10 > MA20** 且三线均有值，则入选；"
                "不要求均线较昨日走高、不要求「首次多头」、不要求股价位置或成交量。\n"
                "**历史回测（backtest）**：信号日下一交易日 **开盘价** 买入；自买入次日起按 **收盘价** 先 **止损 −8%** 再 **止盈 +8%**（与破60日均线策略使用的离场函数一致），"
                "便于与全站回测/历史模拟引擎对接；**选股口径不包含上述买卖仿真**。\n"
                "剔除 ST/*ST 与北交所。不构成投资建议。"
            ),
            assumptions=[
                "MA5/MA10/MA20 与日线同步任务预计算一致；前复权口径与全站一致。",
                "选股仅看截止日一根 K 的三线大小关系。",
                "回测中单标的未平仓前不重复开仓；平仓后自卖出日之后继续扫描。",
            ],
            risks=[
                "满足三线的标的可能较多，实盘需自行叠加风控与仓位。",
                "均线滞后；不含趋势强度或量能过滤时假信号可能偏多。",
            ],
            route_path="/strategy/chun-zheng-ma-duotou",
        )

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        if as_of_date is None:
            raise ValueError("as_of_date 不能为空")
        db = SessionLocal()
        try:
            excluded = _load_excluded_codes(db)
            names = _load_stock_names(db)
            exchanges = _load_stock_exchanges(db)

            stmt = (
                select(StockDailyBar)
                .where(
                    and_(
                        StockDailyBar.trade_date == as_of_date,
                        StockDailyBar.ma5.isnot(None),
                        StockDailyBar.ma10.isnot(None),
                        StockDailyBar.ma20.isnot(None),
                        StockDailyBar.ma5 > StockDailyBar.ma10,
                        StockDailyBar.ma10 > StockDailyBar.ma20,
                        StockDailyBar.stock_code.notin_(excluded),
                    )
                )
                .order_by(StockDailyBar.stock_code)
            )
            rows = db.execute(stmt).scalars().all()

            items: list[StrategyCandidate] = []
            signals: list[StrategySignal] = []
            for bar in rows:
                items.append(
                    StrategyCandidate(
                        stock_code=bar.stock_code,
                        stock_name=names.get(bar.stock_code),
                        exchange_type=exchanges.get(bar.stock_code),
                        trigger_date=as_of_date,
                        summary={
                            "ma5": _to_float(bar.ma5),
                            "ma10": _to_float(bar.ma10),
                            "ma20": _to_float(bar.ma20),
                            "close": _to_float(bar.close),
                        },
                    )
                )
                signals.append(
                    StrategySignal(
                        stock_code=bar.stock_code,
                        event_date=as_of_date,
                        event_type="trigger",
                        payload={
                            "ma5": _to_float(bar.ma5),
                            "ma10": _to_float(bar.ma10),
                            "ma20": _to_float(bar.ma20),
                        },
                    )
                )

            logger.info(
                "纯正均线多头排列选股: as_of=%s 入选=%d",
                as_of_date,
                len(items),
            )

            return StrategyExecutionResult(
                as_of_date=as_of_date,
                assumptions={"data_granularity": "日线", "stock_universe": "A股(排除ST/北交所)"},
                params={
                    "filter": "ma5 > ma10 > ma20 on as_of_date only",
                    "backtest_exit_note": "回测使用次日开盘买 + 收盘±8%先损后盈，与 ma60_five_day_break 离场一致",
                },
                items=items,
                signals=signals,
            )
        finally:
            db.close()

    def backtest(self, *, start_date: date, end_date: date) -> BacktestResult:
        p = _ExitParams()
        exit_p = Ma60ExitParams(take_profit_pct=p.take_profit_pct, stop_loss_pct=p.stop_loss_pct)
        db = SessionLocal()
        try:
            excluded = _load_excluded_codes(db)
            stock_names = _load_stock_names(db)

            ext_start = start_date - timedelta(days=5)
            ext_end = end_date + timedelta(days=400)

            bars_stmt = (
                select(StockDailyBar)
                .where(
                    and_(
                        StockDailyBar.trade_date >= ext_start,
                        StockDailyBar.trade_date <= ext_end,
                        StockDailyBar.close.isnot(None),
                        StockDailyBar.high.isnot(None),
                        StockDailyBar.low.isnot(None),
                        StockDailyBar.stock_code.notin_(excluded),
                    )
                )
                .order_by(StockDailyBar.stock_code, StockDailyBar.trade_date)
            )
            all_bars = db.execute(bars_stmt).scalars().all()

            bars_by_code: dict[str, list[StockDailyBar]] = defaultdict(list)
            for bar in all_bars:
                bars_by_code[bar.stock_code].append(bar)

            trades: list[BacktestTrade] = []
            skipped = 0
            for code, bars_list in bars_by_code.items():
                if len(bars_list) < 2:
                    skipped += 1
                    continue
                stock_name = stock_names.get(code)
                last_block = -1
                i = 0
                while i < len(bars_list) - 1:
                    if i <= last_block:
                        i += 1
                        continue
                    bar = bars_list[i]
                    if not is_pure_ma_bull_order_bar(bar):
                        i += 1
                        continue

                    trigger_date = bar.trade_date
                    next_bar = bars_list[i + 1]
                    if next_bar.open is None or float(next_bar.open) <= 0:
                        i += 1
                        continue

                    buy_date = next_bar.trade_date
                    if buy_date < start_date or buy_date > end_date:
                        i += 1
                        continue

                    buy_price = round(float(next_bar.open), 4)
                    buy_idx = i + 1

                    extra_base: dict[str, Any] = {
                        "signal_date": trigger_date.isoformat(),
                        "signal_ma5": _to_float(bar.ma5),
                        "signal_ma10": _to_float(bar.ma10),
                        "signal_ma20": _to_float(bar.ma20),
                        "buy_rule": "open_on_next_trading_day_after_signal",
                        "sell_rule": "close_take_profit_8pct_or_stop_loss_8pct_stop_first",
                        "take_profit_pct": p.take_profit_pct,
                        "stop_loss_pct": p.stop_loss_pct,
                    }

                    sell_j, sell_px, exit_reason = simulate_exit_close_8_8(
                        bars_list, buy_idx, buy_price, exit_p
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
                            )
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
                        )
                    )
                    last_block = sell_j
                    i = sell_j + 1
                    continue

            logger.info(
                "纯正均线多头排列回测完成: trades=%d skipped_short_series=%d",
                len(trades),
                skipped,
            )
            return BacktestResult(trades=trades, skipped_count=skipped, skip_reasons=[])
        finally:
            db.close()
