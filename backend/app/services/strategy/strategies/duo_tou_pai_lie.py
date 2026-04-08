"""
多头排列买入法（内置回测策略）。

【策略名称】：多头排列买入法
【目标】：在低位股票中，捕捉均线首次多头排列信号，次日开盘买入；相对买入价 +10% 止盈、-6% 止损（回测与模拟一致）。

【适用范围】：
- 市场：A 股全市场（剔除 ST/*ST）
- 数据粒度：日线
- 依赖字段：open / high / low / close / ma5 / ma10 / ma20 / cum_hist_high / trade_date（来自 stock_daily_bar）

【核心规则】：
1) 低位约束：收盘价不超过截至当日累计历史最高价的 1/2。
2) 多头排列首次出现：
   - 触发日前连续 20 个交易日：每日「MA5 > MA10 > MA20」均不成立即可（仅看三线大小关系，不要求均线相对前一日递增）
   - 触发当日：MA5 > MA10 > MA20，且 MA5、MA10、MA20 均比前一天高，且前一日不满足 MA5 > MA10 > MA20（首次出现）
3) 买入：多头排列出现后的下一交易日，以开盘价买入。
4) 卖出：相对买入价盈利 +10% 止盈、亏损 -6% 止损（按日线 high/low 判定；同根 K 同触及时先止损）。
   历史回测与历史模拟均使用同一套规则。

【输出】：BacktestTrade.trigger_date 为多头排列日；extra 含均线值与 exit_reason。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, and_
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
    low_position_ratio: float = 0.5  # 收盘价 <= 历史最高价 * 1/2
    prior_no_bullish_days: int = 20  # 触发日前连续 N 个交易日不得出现多头排列
    take_profit_pct: float = 0.10  # 相对买入价盈利比例，止盈
    stop_loss_pct: float = 0.06  # 相对买入价亏损比例，止损


def _to_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


class DuoTouPaiLieStrategy(StockStrategy):
    """多头排列买入法策略实现。"""

    strategy_id = "duo_tou_pai_lie"
    version = "v1.2.2"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="多头排列买入法",
            version=self.version,
            short_description="低位股票均线首次多头排列，次日开盘买入；盈利 10% 止盈、亏损 6% 止损。",
            description=(
                "本策略在 A 股日线数据上识别以下形态：\n"
                "1) 低位约束：收盘价不超过历史最高价的 1/2。\n"
                "2) 触发日前连续 20 个交易日：每日均不满足 MA5 > MA10 > MA20（仅看三线大小，不要求均线递增）。\n"
                "3) 触发当日首次多头排列：MA5 > MA10 > MA20，且三线均比前一天高，且前一日不满足该排列。\n"
                "4) 买入：多头排列日的下一交易日，以开盘价买入。\n"
                "5) 卖出：相对买入价 +10% 止盈、-6% 止损（历史回测与历史模拟规则一致）。"
            ),
            assumptions=[
                "低位约束：收盘价不超过历史最高价的 1/2。",
                "触发日前 20 个交易日：仅以「MA5 > MA10 > MA20」是否成立判定多头，不要求均线相对前一日递增。",
                "触发日：MA5 > MA10 > MA20，且 MA5、MA10、MA20 均比前一天高；前一日不满足 MA5 > MA10 > MA20。",
                "买入价：多头排列日的下一交易日开盘价。",
                "卖出：相对买入价 +10% 止盈、-6% 止损；同一根 K 线同时触及时先按止损。",
                "剔除 ST/*ST 股票。",
                "本策略用于历史验证，不构成投资建议。",
            ],
            risks=[
                "均线信号有滞后性，可能错过最佳买卖点。",
                "固定比例止盈止损在震荡行情中可能频繁触发。",
                "数据缺失、停牌会影响回测结果准确性。",
            ],
            route_path="/strategy/duo-tou-pai-lie",
        )

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        """选股执行：识别当日满足多头排列首次出现条件的股票。"""
        params = _Params()
        if as_of_date is None:
            raise ValueError("as_of_date 不能为空")

        db = SessionLocal()
        try:
            excluded_codes = self._load_excluded_codes(db)

            # 查询当日和前一日的数据
            bars_stmt = (
                select(StockDailyBar)
                .where(
                    and_(
                        StockDailyBar.trade_date == as_of_date,
                        StockDailyBar.close.isnot(None),
                        StockDailyBar.ma5.isnot(None),
                        StockDailyBar.ma10.isnot(None),
                        StockDailyBar.ma20.isnot(None),
                        StockDailyBar.cum_hist_high.isnot(None),
                        StockDailyBar.stock_code.notin_(excluded_codes),
                    )
                )
            )
            today_bars = db.execute(bars_stmt).scalars().all()

            if not today_bars:
                return StrategyExecutionResult(
                    as_of_date=as_of_date,
                    assumptions={"data_granularity": "日线", "stock_universe": "A股(排除ST/北交所)"},
                    params={
                        "low_position_ratio": params.low_position_ratio,
                        "prior_no_bullish_days": params.prior_no_bullish_days,
                        "take_profit_pct": params.take_profit_pct,
                        "stop_loss_pct": params.stop_loss_pct,
                    },
                    items=[],
                    signals=[],
                )

            stock_codes = [b.stock_code for b in today_bars]
            # 触发日前连续 N 个交易日（用于「前 N 天无多头排列」与「前一日」）
            hist_stmt = (
                select(StockDailyBar)
                .where(
                    and_(
                        StockDailyBar.stock_code.in_(stock_codes),
                        StockDailyBar.trade_date < as_of_date,
                        StockDailyBar.trade_date >= as_of_date - timedelta(days=90),
                        StockDailyBar.ma5.isnot(None),
                        StockDailyBar.ma10.isnot(None),
                        StockDailyBar.ma20.isnot(None),
                    )
                )
                .order_by(StockDailyBar.stock_code, StockDailyBar.trade_date.desc())
            )
            hist_raw = db.execute(hist_stmt).scalars().all()
            hist_by_code: dict[str, list[StockDailyBar]] = defaultdict(list)
            for hbar in hist_raw:
                if len(hist_by_code[hbar.stock_code]) < params.prior_no_bullish_days:
                    hist_by_code[hbar.stock_code].append(hbar)

            stock_names = self._load_stock_names(db)
            stock_exchanges = self._load_stock_exchanges(db)

            items: list[StrategyCandidate] = []
            signals: list[StrategySignal] = []

            for bar in today_bars:
                # 低位约束
                if bar.cum_hist_high is None or bar.close > bar.cum_hist_high * Decimal(str(params.low_position_ratio)):
                    continue

                prior_bars = hist_by_code.get(bar.stock_code) or []
                if len(prior_bars) < params.prior_no_bullish_days:
                    continue

                prev_bar = prior_bars[0]
                if not self._prior_trading_days_no_bullish_alignment(prior_bars, params.prior_no_bullish_days):
                    continue

                # 检查是否首次出现多头排列
                if not self._is_first_bullish_alignment(bar, prev_bar):
                    continue

                items.append(StrategyCandidate(
                    stock_code=bar.stock_code,
                    stock_name=stock_names.get(bar.stock_code),
                    exchange_type=stock_exchanges.get(bar.stock_code),
                    trigger_date=as_of_date,
                    summary={
                        "ma5": _to_float(bar.ma5),
                        "ma10": _to_float(bar.ma10),
                        "ma20": _to_float(bar.ma20),
                        "close": _to_float(bar.close),
                        "cum_hist_high": _to_float(bar.cum_hist_high),
                    },
                ))
                signals.append(StrategySignal(
                    stock_code=bar.stock_code,
                    event_date=as_of_date,
                    event_type="trigger",
                    payload={
                        "ma5": _to_float(bar.ma5),
                        "ma10": _to_float(bar.ma10),
                        "ma20": _to_float(bar.ma20),
                    },
                ))

            logger.info(
                "多头排列买入法选股完成: as_of_date=%s, 扫描 %d 只股票, 识别 %d 个候选",
                as_of_date, len(today_bars), len(items),
            )

            return StrategyExecutionResult(
                as_of_date=as_of_date,
                assumptions={"data_granularity": "日线", "stock_universe": "A股(排除ST/北交所)"},
                params={
                    "low_position_ratio": params.low_position_ratio,
                    "prior_no_bullish_days": params.prior_no_bullish_days,
                    "take_profit_pct": params.take_profit_pct,
                    "stop_loss_pct": params.stop_loss_pct,
                },
                items=items,
                signals=signals,
            )
        finally:
            db.close()

    def backtest(self, *, start_date: date, end_date: date) -> BacktestResult:
        """在指定时间范围内扫描全市场模拟交易（历史回测与历史模拟共用同一套止盈止损）。"""
        params = _Params()
        db = SessionLocal()

        try:
            excluded_codes = self._load_excluded_codes(db)
            stock_names = self._load_stock_names(db)

            bars_stmt = (
                select(StockDailyBar)
                .where(
                    and_(
                        StockDailyBar.trade_date >= start_date - timedelta(days=60),
                        StockDailyBar.trade_date <= end_date + timedelta(days=60),
                        StockDailyBar.close.isnot(None),
                        StockDailyBar.high.isnot(None),
                        StockDailyBar.low.isnot(None),
                        StockDailyBar.ma5.isnot(None),
                        StockDailyBar.ma10.isnot(None),
                        StockDailyBar.ma20.isnot(None),
                        StockDailyBar.cum_hist_high.isnot(None),
                        StockDailyBar.stock_code.notin_(excluded_codes),
                    )
                )
                .order_by(StockDailyBar.stock_code, StockDailyBar.trade_date)
            )
            all_bars = db.execute(bars_stmt).scalars().all()

            bars_by_code: dict[str, list[StockDailyBar]] = defaultdict(list)
            for bar in all_bars:
                bars_by_code[bar.stock_code].append(bar)

            logger.info(
                "多头排列买入法回测: 加载 %d 只股票, 区间 %s ~ %s",
                len(bars_by_code), start_date, end_date,
            )

            trades: list[BacktestTrade] = []

            for stock_code, stock_bars in bars_by_code.items():
                stock_trades = self._scan_stock(
                    stock_code, stock_bars, stock_names.get(stock_code), params, start_date, end_date,
                )
                trades.extend(stock_trades)

            logger.info(
                "多头排列买入法回测完成: 扫描 %d 只股票, 产生 %d 笔交易",
                len(bars_by_code), len(trades),
            )

            return BacktestResult(trades=trades, skipped_count=0)

        finally:
            db.close()

    def _scan_stock(
        self,
        stock_code: str,
        bars: list[StockDailyBar],
        stock_name: str | None,
        params: _Params,
        start_date: date,
        end_date: date,
    ) -> list[BacktestTrade]:
        """扫描单只股票的日线数据，产生买卖交易（固定比例止盈止损）。

        同一标的同一时间仅持有一笔：出现平仓后从卖出日之后继续寻找下一笔信号，
        避免对每一个可能触发日都做「从头扫到尾」的内层循环（全市场回测时原为 O(n²)/股，会卡死任务）。
        """
        trades: list[BacktestTrade] = []

        i = 1
        while i < len(bars) - 1:
            bar = bars[i]
            trigger_date = bar.trade_date

            if trigger_date < start_date:
                i += 1
                continue
            if trigger_date > end_date:
                break

            if not (bar.close and bar.ma5 and bar.ma10 and bar.ma20 and bar.cum_hist_high):
                i += 1
                continue

            if bar.close > bar.cum_hist_high * Decimal(str(params.low_position_ratio)):
                i += 1
                continue

            prev_bar = bars[i - 1]
            if not (prev_bar.ma5 and prev_bar.ma10 and prev_bar.ma20):
                i += 1
                continue

            if not self._is_first_bullish_alignment(bar, prev_bar):
                i += 1
                continue

            if not self._no_bullish_alignment_in_prior_trading_days(
                bars, i, params.prior_no_bullish_days
            ):
                i += 1
                continue

            next_bar = bars[i + 1]
            if not next_bar.open:
                i += 1
                continue

            if next_bar.trade_date > end_date:
                i += 1
                continue

            buy_date = next_bar.trade_date
            buy_price = _to_float(next_bar.open)
            if buy_price is None or buy_price <= 0:
                i += 1
                continue

            extra_base: dict[str, Any] = {
                "trigger_date": trigger_date.isoformat(),
                "trigger_ma5": _to_float(bar.ma5),
                "trigger_ma10": _to_float(bar.ma10),
                "trigger_ma20": _to_float(bar.ma20),
                "trigger_close": _to_float(bar.close),
            }
            if next_bar.ma10 is not None:
                extra_base["buy_ma10"] = _to_float(next_bar.ma10)

            tp_price = buy_price * (1.0 + params.take_profit_pct)
            sl_price = buy_price * (1.0 - params.stop_loss_pct)
            tp_label = f"止盈+{int(round(params.take_profit_pct * 100))}%"
            sl_label = f"止损-{int(round(params.stop_loss_pct * 100))}%"

            sell_idx: int | None = None
            exit_reason: str | None = None
            sell_price: float | None = None

            for k in range(i + 2, len(bars)):
                bk = bars[k]
                if bk.trade_date > end_date:
                    break

                if bk.high is None or bk.low is None:
                    continue

                high_k = _to_float(bk.high)
                low_k = _to_float(bk.low)
                if high_k is None or low_k is None:
                    continue

                if low_k <= sl_price:
                    sell_idx = k
                    sell_price = sl_price
                    exit_reason = sl_label
                    break
                if high_k >= tp_price:
                    sell_idx = k
                    sell_price = tp_price
                    exit_reason = tp_label
                    break

            if sell_idx is None or sell_price is None:
                trades.append(
                    BacktestTrade(
                        stock_code=stock_code,
                        stock_name=stock_name,
                        buy_date=buy_date,
                        buy_price=buy_price,
                        trade_type="unclosed",
                        trigger_date=trigger_date,
                        extra=extra_base,
                    )
                )
                return trades

            sell_bar = bars[sell_idx]
            sell_date = sell_bar.trade_date

            return_rate = (sell_price - buy_price) / buy_price if buy_price else 0

            trades.append(
                BacktestTrade(
                    stock_code=stock_code,
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
                        "take_profit_price": tp_price,
                        "stop_loss_price": sl_price,
                    },
                )
            )

            i = sell_idx + 1

        return trades

    @staticmethod
    def _is_first_bullish_alignment(bar: StockDailyBar, prev_bar: StockDailyBar) -> bool:
        """
        检查是否首次出现多头排列：
        1. 当日 MA5 > MA10 > MA20
        2. MA5、MA10、MA20 都比前一天高
        3. 前一日不满足 MA5 > MA10 > MA20
        """
        if bar.ma5 is None or bar.ma10 is None or bar.ma20 is None:
            return False
        if prev_bar.ma5 is None or prev_bar.ma10 is None or prev_bar.ma20 is None:
            return False

        # 条件1：当日 MA5 > MA10 > MA20
        if not (bar.ma5 > bar.ma10 > bar.ma20):
            return False

        # 条件2：三者都比前一天高
        if not (bar.ma5 > prev_bar.ma5):
            return False
        if not (bar.ma10 > prev_bar.ma10):
            return False
        if not (bar.ma20 > prev_bar.ma20):
            return False

        # 条件3：前一日不满足 MA5 > MA10 > MA20（首次出现）
        if prev_bar.ma5 > prev_bar.ma10 > prev_bar.ma20:
            return False

        return True

    @staticmethod
    def _is_ma_bullish_order(bar: StockDailyBar) -> bool:
        """仅判断当日是否满足 MA5 > MA10 > MA20（不看均线是否较前一日走高）。

        用于「触发日前 N 个交易日不得出现多头排列」：与触发日「首次多头排列」里附加的
        「三线均比前一天高」无关。
        """
        if bar.ma5 is None or bar.ma10 is None or bar.ma20 is None:
            return False
        return bar.ma5 > bar.ma10 > bar.ma20

    @classmethod
    def _no_bullish_alignment_in_prior_trading_days(
        cls,
        bars: list[StockDailyBar],
        i: int,
        lookback: int,
    ) -> bool:
        """触发日索引 i 之前连续 lookback 个交易日：每日均须 MA5 > MA10 > MA20 不成立。

        仅检验三线大小关系；历史不足则 False。
        """
        if i < lookback:
            return False
        for j in range(i - lookback, i):
            b = bars[j]
            if cls._is_ma_bullish_order(b):
                return False
        return True

    @staticmethod
    def _prior_trading_days_no_bullish_alignment(
        prior_newest_first: list[StockDailyBar],
        lookback: int,
    ) -> bool:
        """选股用：从新到旧取触发日前 lookback 根 K 线，每日均须 MA5 > MA10 > MA20 不成立。"""
        if len(prior_newest_first) < lookback:
            return False
        for b in prior_newest_first[:lookback]:
            if DuoTouPaiLieStrategy._is_ma_bullish_order(b):
                return False
        return True

    @staticmethod
    def _load_excluded_codes(db) -> set[str]:
        """加载需排除的股票代码集合（ST + 北交所）。"""
        basics = db.execute(select(StockBasic)).scalars().all()
        excluded: set[str] = set()
        for b in basics:
            if b.exchange == "BSE":
                excluded.add(b.code)
            elif b.name and ("ST" in b.name.upper()):
                excluded.add(b.code)
        return excluded

    @staticmethod
    def _load_stock_names(db) -> dict[str, str]:
        basics = db.execute(select(StockBasic)).scalars().all()
        return {b.code: b.name for b in basics}

    @staticmethod
    def _load_stock_exchanges(db) -> dict[str, str]:
        basics = db.execute(select(StockBasic)).scalars().all()
        return {b.code: b.exchange for b in basics}
