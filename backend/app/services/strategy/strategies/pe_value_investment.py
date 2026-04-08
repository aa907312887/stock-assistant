"""
市盈率长线价值投资策略。

【策略名称】：市盈率长线价值投资
【目标】：捕捉 PE 历史百分位首次进入极度低估区域的信号，长期持有至止盈止损。

【适用范围】：
- 市场：A 股（排除 ST 股票、北交所）
- 数据粒度：日线
- 依赖字段：pe_percentile / pe / open / high / low / close（来自 stock_daily_bar）

【核心规则】：
1) 买入条件：
   - PE 百分位从 5% 以上首次跌落到 5% 以内
   - PE 为正数（pe > 0）
   - 以信号日的下一交易日开盘价买入

2) 卖出条件（优先级从高到低）：
   - 止损：亏损 >= 20% → 以止损价卖出
   - 止盈：盈利 >= 30% → 以止盈价卖出

3) 多标的：
   - 可同时持有多只股票，每只股票独立跟踪
   - 同一股票卖出后可在后续重新买入

【关键口径与阈值】：
- PE 百分位买入阈值：从 5% 以上跌到 5% 以内（首次进入）
- PE 必须为正数
- 止盈比例：+30%
- 止损比例：-20%
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, and_

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
    pe_entry_threshold: float = 5.0      # PE百分位 < 5% 时触发
    profit_take_pct: float = 0.30        # 止盈：盈利30%
    stop_loss_pct: float = 0.20          # 止损：亏损20%


def _to_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


class PeValueInvestmentStrategy(StockStrategy):
    """市盈率长线价值投资策略实现。"""

    strategy_id = "pe_value_investment"
    version = "v3.0.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="市盈率长线价值投资",
            version=self.version,
            short_description="PE百分位首次跌入5%以内时买入，盈利30%止盈，亏损20%止损。",
            description=(
                "本策略捕捉PE历史百分位首次进入极度低估区域的信号："
                "当PE百分位从5%以上首次跌落到5%以内时，以次日开盘价买入。"
                "卖出采用止盈止损机制：盈利30%止盈，亏损20%止损。"
            ),
            assumptions=[
                "PE 百分位使用该股自 2019 年以来的历史 PE 最大最小值计算。",
                "买入条件：PE 百分位从 5% 以上首次跌落到 5% 以内，且 PE > 0。",
                "买入价格：信号日的下一交易日开盘价。",
                "卖出条件（优先级从高到低）：",
                "  1. 止损：亏损 >= 20% 时以止损价卖出。",
                "  2. 止盈：盈利 >= 30% 时以止盈价卖出。",
                "排除 ST/*ST 股票和北交所股票。",
                "可同时持有多只股票，每只独立跟踪。",
                "本策略用于历史验证，不构成投资建议。",
            ],
            risks=[
                "PE 低不代表安全，可能存在业绩持续恶化的价值陷阱。",
                "长线持有期间可能遭遇黑天鹅事件。",
                "数据缺失、停牌会影响回测结果准确性。",
            ],
            route_path="/strategy/pe-value-investment",
        )

    # ------------------------------------------------------------------
    # execute() — 实时选股
    # ------------------------------------------------------------------

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        """选股执行：识别当日 PE 百分位从 5% 以上首次跌落到 5% 以内的股票。"""
        params = _Params()
        if as_of_date is None:
            raise ValueError("as_of_date 不能为空")

        db = SessionLocal()
        try:
            excluded_codes = self._load_excluded_codes(db)

            # 1. 查询当日 PE 百分位在合理范围的股票
            bars_stmt = (
                select(StockDailyBar)
                .where(
                    and_(
                        StockDailyBar.trade_date == as_of_date,
                        StockDailyBar.pe_percentile.isnot(None),
                        StockDailyBar.pe_percentile < params.pe_entry_threshold,
                        StockDailyBar.pe.isnot(None),
                        StockDailyBar.pe > 0,
                        StockDailyBar.open.isnot(None),
                        StockDailyBar.stock_code.notin_(excluded_codes),
                    )
                )
            )
            candidate_bars = db.execute(bars_stmt).scalars().all()

            if not candidate_bars:
                return StrategyExecutionResult(
                    as_of_date=as_of_date,
                    assumptions={"data_granularity": "日线", "stock_universe": "A股(排除ST/北交所)"},
                    params={
                        "pe_entry_threshold": params.pe_entry_threshold,
                        "profit_take_pct": params.profit_take_pct,
                        "stop_loss_pct": params.stop_loss_pct,
                    },
                    items=[],
                    signals=[],
                )

            candidate_codes = [b.stock_code for b in candidate_bars]

            # 2. 批量查询前一日的 PE 百分位（用于判断是否首次跌入）
            prev_pe_map = self._batch_prev_pe_percentile(db, candidate_codes, as_of_date)

            # 3. 筛选
            stock_names = self._load_stock_names(db)
            stock_exchanges = self._load_stock_exchanges(db)

            items: list[StrategyCandidate] = []
            signals: list[StrategySignal] = []

            for bar in candidate_bars:
                prev_pe = prev_pe_map.get(bar.stock_code)
                
                # 检查是否首次跌入：前一日 PE 百分位 >= 5%，当日 < 5%
                if prev_pe is None or prev_pe < params.pe_entry_threshold:
                    continue

                items.append(StrategyCandidate(
                    stock_code=bar.stock_code,
                    stock_name=stock_names.get(bar.stock_code),
                    exchange_type=stock_exchanges.get(bar.stock_code),
                    trigger_date=as_of_date,
                    summary={
                        "pe_percentile": _to_float(bar.pe_percentile),
                        "prev_pe_percentile": prev_pe,
                        "pe": _to_float(bar.pe),
                    },
                ))
                signals.append(StrategySignal(
                    stock_code=bar.stock_code,
                    event_date=as_of_date,
                    event_type="trigger",
                    payload={
                        "pe_percentile": _to_float(bar.pe_percentile),
                        "prev_pe_percentile": prev_pe,
                        "pe": _to_float(bar.pe),
                    },
                ))

            logger.info(
                "市盈率长线价值选股完成: as_of_date=%s, 扫描 %d 只低PE股, 首次跌入 %d 只候选",
                as_of_date, len(candidate_bars), len(items),
            )

            return StrategyExecutionResult(
                as_of_date=as_of_date,
                assumptions={"data_granularity": "日线", "stock_universe": "A股(排除ST/北交所)"},
                params={
                    "pe_entry_threshold": params.pe_entry_threshold,
                    "profit_take_pct": params.profit_take_pct,
                    "stop_loss_pct": params.stop_loss_pct,
                },
                items=items,
                signals=signals,
            )
        finally:
            db.close()

    # ------------------------------------------------------------------
    # backtest() — 历史模拟回测
    # ------------------------------------------------------------------

    def backtest(self, *, start_date: date, end_date: date) -> BacktestResult:
        """回测执行：在指定时间范围内扫描全市场股票模拟交易。"""
        params = _Params()
        db = SessionLocal()

        try:
            excluded_codes = self._load_excluded_codes(db)
            stock_names = self._load_stock_names(db)

            # 1. 加载日线数据（需要有 pe_percentile、pe、价格数据）
            # 需要额外加载信号日前一天的数据用于判断首次跌入
            bars_stmt = (
                select(StockDailyBar)
                .where(
                    and_(
                        StockDailyBar.trade_date >= start_date - timedelta(days=7),
                        StockDailyBar.trade_date <= end_date + timedelta(days=60),
                        StockDailyBar.pe_percentile.isnot(None),
                        StockDailyBar.pe.isnot(None),
                        StockDailyBar.open.isnot(None),
                        StockDailyBar.high.isnot(None),
                        StockDailyBar.low.isnot(None),
                        StockDailyBar.close.isnot(None),
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
                "市盈率长线回测: 加载 %d 只股票的日线数据, 时间范围 %s ~ %s",
                len(bars_by_code), start_date, end_date,
            )

            # 2. 逐股扫描
            trades: list[BacktestTrade] = []

            for stock_code, stock_bars in bars_by_code.items():
                stock_trades = self._scan_stock(
                    stock_code, stock_bars, stock_names.get(stock_code), params, start_date, end_date,
                )
                trades.extend(stock_trades)

            logger.info(
                "市盈率长线回测完成: 扫描 %d 只股票, 产生 %d 笔交易",
                len(bars_by_code), len(trades),
            )

            return BacktestResult(trades=trades, skipped_count=0)

        finally:
            db.close()

    # ------------------------------------------------------------------
    # 私有辅助方法
    # ------------------------------------------------------------------

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

    @staticmethod
    def _batch_prev_pe_percentile(db, stock_codes: list[str], as_of_date: date) -> dict[str, float]:
        """批量查询一组股票在 as_of_date 前一日的 PE 百分位。"""
        if not stock_codes:
            return {}

        # 查询前一日的数据
        rows = db.execute(
            select(StockDailyBar.stock_code, StockDailyBar.pe_percentile)
            .where(
                and_(
                    StockDailyBar.stock_code.in_(stock_codes),
                    StockDailyBar.trade_date < as_of_date,
                    StockDailyBar.pe_percentile.isnot(None),
                )
            )
            .order_by(StockDailyBar.stock_code, StockDailyBar.trade_date.desc())
        ).all()

        # 每只股票只取最近一条
        result: dict[str, float] = {}
        for r in rows:
            if r.stock_code not in result and r.pe_percentile is not None:
                result[r.stock_code] = float(r.pe_percentile)
        return result

    def _scan_stock(
        self,
        stock_code: str,
        bars: list[StockDailyBar],
        stock_name: str | None,
        params: _Params,
        start_date: date,
        end_date: date,
    ) -> list[BacktestTrade]:
        """
        扫描单只股票的日线数据，产生买卖交易。
        
        逻辑：
        1. 买入：PE 百分位从 5% 以上首次跌落到 5% 以内，次日开盘价买入
        2. 卖出：止损 20% / 止盈 30%
        """
        trades: list[BacktestTrade] = []
        in_position = False
        trigger_date_val: date | None = None
        buy_date_val: date | None = None
        buy_price_val: float | None = None
        buy_extra: dict | None = None

        for i, bar in enumerate(bars):
            pe_pct = _to_float(bar.pe_percentile)
            pe_val = _to_float(bar.pe)
            open_price = _to_float(bar.open)
            high_price = _to_float(bar.high)
            low_price = _to_float(bar.low)

            if pe_pct is None or open_price is None:
                continue

            if in_position:
                # 持仓中：检查卖出条件
                stop_loss_price = buy_price_val * (1 - params.stop_loss_pct)
                profit_take_price = buy_price_val * (1 + params.profit_take_pct)
                
                exit_reason = None
                sell_price = None
                
                # 1. 止损：当日最低价 <= 止损价
                if low_price is not None and low_price <= stop_loss_price:
                    exit_reason = f"止损（亏损{int(params.stop_loss_pct * 100)}%）"
                    sell_price = stop_loss_price
                # 2. 止盈：当日最高价 >= 止盈价
                elif high_price is not None and high_price >= profit_take_price:
                    exit_reason = f"止盈（盈利{int(params.profit_take_pct * 100)}%）"
                    sell_price = profit_take_price
                
                if exit_reason:
                    return_rate = (sell_price - buy_price_val) / buy_price_val if buy_price_val else 0
                    trades.append(BacktestTrade(
                        stock_code=stock_code,
                        stock_name=stock_name,
                        buy_date=buy_date_val,
                        buy_price=buy_price_val,
                        sell_date=bar.trade_date,
                        sell_price=sell_price,
                        return_rate=return_rate,
                        trade_type="closed",
                        trigger_date=trigger_date_val,
                        extra={
                            **(buy_extra or {}),
                            "sell_pe_percentile": pe_pct,
                            "exit_reason": exit_reason,
                            "stop_loss_price": float(stop_loss_price),
                            "profit_take_price": float(profit_take_price),
                        },
                    ))
                    in_position = False
                    trigger_date_val = None
                    buy_date_val = None
                    buy_price_val = None
                    buy_extra = None
            else:
                # 未持仓：检查买入条件
                # 检查是否首次跌入：前一日 PE 百分位 >= 5%，当日 < 5%
                if pe_pct < params.pe_entry_threshold and pe_val is not None and pe_val > 0 and i > 0:
                    prev_bar = bars[i - 1]
                    prev_pe = _to_float(prev_bar.pe_percentile)
                    
                    # 首次跌入判断
                    if prev_pe is not None and prev_pe >= params.pe_entry_threshold:
                        # 信号确认，次日开盘价买入
                        if i + 1 < len(bars):
                            next_bar = bars[i + 1]
                            next_open = _to_float(next_bar.open)
                            if next_open is not None and next_bar.trade_date >= start_date:
                                in_position = True
                                trigger_date_val = bar.trade_date
                                buy_date_val = next_bar.trade_date
                                buy_price_val = next_open
                                buy_extra = {
                                    "trigger_date": trigger_date_val.isoformat() if trigger_date_val else None,
                                    "trigger_pe_percentile": pe_pct,
                                    "prev_pe_percentile": prev_pe,
                                    "buy_pe_percentile": _to_float(next_bar.pe_percentile),
                                    "buy_pe": _to_float(next_bar.pe),
                                }

        # 回测结束仍持仓
        if in_position:
            trades.append(BacktestTrade(
                stock_code=stock_code,
                stock_name=stock_name,
                buy_date=buy_date_val,
                buy_price=buy_price_val,
                sell_date=None,
                sell_price=None,
                return_rate=None,
                trade_type="unclosed",
                trigger_date=trigger_date_val,
                extra=buy_extra,
            ))

        return trades
