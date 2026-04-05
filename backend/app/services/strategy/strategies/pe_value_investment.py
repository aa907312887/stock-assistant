"""
市盈率长线价值投资策略。

【策略名称】：市盈率长线价值投资
【目标】：在 PE 历史百分位极低且基本面健康、均线多头排列确认时买入，长期持有至止盈止损或估值修复。

【适用范围】：
- 市场：A 股（排除 ST 股票、北交所）
- 数据粒度：日线
- 依赖字段：pe_percentile / pe / ma5 / ma10 / ma20（来自 stock_daily_bar），roe（来自 stock_financial_report）

【核心规则】：
1) 筛选条件（进入观察池）：
   - PE 历史百分位 < 6%（pe_percentile 字段，0-100 范围）
   - PE 为正数（pe > 0）
   - 最近一期财报 ROE > 15%

2) 买入时机（触发买入）：
   - 观察池中的股票出现均线首次多头排列
   - 多头排列定义：MA5 > MA10 > MA20，且三者都比前一天高
   - 以当日收盘价买入

3) 卖出条件（优先级从高到低）：
   - 止损：亏损 >= 15% → 以止损价卖出
   - 止盈：盈利 >= 30% → 以止盈价卖出
   - 估值修复：PE 百分位 >= 30 → 以收盘价卖出

4) 多标的：
   - 可同时持有多只股票，每只股票独立跟踪
   - 同一股票卖出后可在后续重新买入

【关键口径与阈值】：
- PE 百分位筛选阈值：< 6%
- PE 必须为正数
- ROE 最低要求：> 15%
- 止盈比例：+30%
- 止损比例：-15%
- 财报匹配：使用 report_date <= 当日交易日的最新一期财报
"""

from __future__ import annotations

import logging
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select, and_, func

from app.database import SessionLocal
from app.models import StockBasic, StockDailyBar, StockFinancialReport
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
    pe_filter_threshold: float = 6.0     # PE百分位 < 6% 进入观察池
    pe_sell_threshold: float = 30.0      # PE百分位 >= 30 卖出
    roe_min: float = 15.0               # ROE > 15%
    profit_take_pct: float = 0.30       # 止盈：盈利30%
    stop_loss_pct: float = 0.15         # 止损：亏损15%


def _to_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


class PeValueInvestmentStrategy(StockStrategy):
    """市盈率长线价值投资策略实现。"""

    strategy_id = "pe_value_investment"
    version = "v2.0.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="市盈率长线价值投资",
            version=self.version,
            short_description="PE百分位极低+基本面健康+均线多头排列确认买入，止盈止损控制风险。",
            description=(
                "本策略分两阶段选股："
                "1) 筛选阶段：PE百分位 < 6% 且 PE > 0 且 ROE > 15% 进入观察池；"
                "2) 买入阶段：观察池中的股票出现均线首次多头排列（MA5 > MA10 > MA20 且三者都比前一天高）时以收盘价买入。"
                "卖出采用止盈止损机制：盈利30%止盈，亏损15%止损，或PE百分位 >= 30时估值修复卖出。"
            ),
            assumptions=[
                "PE 百分位使用该股自 2019 年以来的历史 PE 最大最小值计算。",
                "筛选条件：PE 百分位 < 6% 且 PE > 0 且 ROE > 15%。",
                "买入时机：均线首次多头排列（MA5 > MA10 > MA20 且三者都比前一天高）。",
                "卖出条件（优先级从高到低）：",
                "  1. 止损：亏损 >= 15% 时以止损价卖出。",
                "  2. 止盈：盈利 >= 30% 时以止盈价卖出。",
                "  3. 估值修复：PE 百分位 >= 30 时以收盘价卖出。",
                "交易价格：筛选日以收盘价确认，买入日以收盘价买入。",
                "财报匹配：使用 report_date <= 交易日的最新一期财务报告。",
                "排除 ST/*ST 股票和北交所股票。",
                "可同时持有多只股票，每只独立跟踪。",
                "本策略用于历史验证，不构成投资建议。",
            ],
            risks=[
                "PE 低不代表安全，可能存在业绩持续恶化的价值陷阱。",
                "财报数据有滞后性，发布时间与报告期存在时间差。",
                "均线确认可能错过最佳买点，或买入后股价反转。",
                "长线持有期间可能遭遇黑天鹅事件。",
            ],
            route_path="/strategy/pe-value-investment",
        )

    # ------------------------------------------------------------------
    # execute() — 实时选股
    # ------------------------------------------------------------------

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        """选股执行：识别当日满足筛选条件且均线多头排列的股票。"""
        params = _Params()
        if as_of_date is None:
            raise ValueError("as_of_date 不能为空")

        db = SessionLocal()
        try:
            excluded_codes = self._load_excluded_codes(db)

            # 1. 查询当日 PE百分位 < 6% 且 PE > 0 的股票
            bars_stmt = (
                select(StockDailyBar)
                .where(
                    and_(
                        StockDailyBar.trade_date == as_of_date,
                        StockDailyBar.pe_percentile.isnot(None),
                        StockDailyBar.pe_percentile < params.pe_filter_threshold,
                        StockDailyBar.pe.isnot(None),
                        StockDailyBar.pe > 0,
                        StockDailyBar.close.isnot(None),
                        StockDailyBar.ma5.isnot(None),
                        StockDailyBar.ma10.isnot(None),
                        StockDailyBar.ma20.isnot(None),
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
                        "pe_filter_threshold": params.pe_filter_threshold,
                        "pe_sell_threshold": params.pe_sell_threshold,
                        "roe_min": params.roe_min,
                        "profit_take_pct": params.profit_take_pct,
                        "stop_loss_pct": params.stop_loss_pct,
                    },
                    items=[],
                    signals=[],
                )

            candidate_codes = [b.stock_code for b in candidate_bars]

            # 2. 批量查询最新财报
            fina_map = self._batch_latest_financial(db, candidate_codes, as_of_date)

            # 3. 批量查询前一日的均线数据
            prev_bars_map = self._batch_prev_bars(db, candidate_codes, as_of_date)

            # 4. 筛选
            stock_names = self._load_stock_names(db)
            stock_exchanges = self._load_stock_exchanges(db)

            items: list[StrategyCandidate] = []
            signals: list[StrategySignal] = []

            for bar in candidate_bars:
                # 检查 ROE
                fina = fina_map.get(bar.stock_code)
                if fina is None:
                    continue
                roe_val = fina[0]
                if roe_val is None or roe_val <= params.roe_min:
                    continue

                # 检查均线多头排列
                prev_bar = prev_bars_map.get(bar.stock_code)
                if not self._is_bullish_alignment(bar, prev_bar):
                    continue

                items.append(StrategyCandidate(
                    stock_code=bar.stock_code,
                    stock_name=stock_names.get(bar.stock_code),
                    exchange_type=stock_exchanges.get(bar.stock_code),
                    trigger_date=as_of_date,
                    summary={
                        "pe_percentile": _to_float(bar.pe_percentile),
                        "pe": _to_float(bar.pe),
                        "roe": float(roe_val),
                        "ma5": _to_float(bar.ma5),
                        "ma10": _to_float(bar.ma10),
                        "ma20": _to_float(bar.ma20),
                        "close": _to_float(bar.close),
                    },
                ))
                signals.append(StrategySignal(
                    stock_code=bar.stock_code,
                    event_date=as_of_date,
                    event_type="trigger",
                    payload={
                        "pe_percentile": _to_float(bar.pe_percentile),
                        "pe": _to_float(bar.pe),
                        "roe": float(roe_val),
                    },
                ))

            logger.info(
                "市盈率长线价值选股完成: as_of_date=%s, 扫描 %d 只低PE股, ROE筛选后 %d 只, 多头排列确认后 %d 只候选",
                as_of_date, len(candidate_bars), len([b for b in candidate_bars if fina_map.get(b.stock_code) and fina_map.get(b.stock_code)[0] and fina_map.get(b.stock_code)[0] > params.roe_min]), len(items),
            )

            return StrategyExecutionResult(
                as_of_date=as_of_date,
                assumptions={"data_granularity": "日线", "stock_universe": "A股(排除ST/北交所)"},
                params={
                    "pe_filter_threshold": params.pe_filter_threshold,
                    "pe_sell_threshold": params.pe_sell_threshold,
                    "roe_min": params.roe_min,
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

            # 1. 加载日线数据（需要有 pe_percentile、pe、均线数据）
            bars_stmt = (
                select(StockDailyBar)
                .where(
                    and_(
                        StockDailyBar.trade_date >= start_date,
                        StockDailyBar.trade_date <= end_date,
                        StockDailyBar.pe_percentile.isnot(None),
                        StockDailyBar.pe.isnot(None),
                        StockDailyBar.close.isnot(None),
                        StockDailyBar.ma5.isnot(None),
                        StockDailyBar.ma10.isnot(None),
                        StockDailyBar.ma20.isnot(None),
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

            # 2. 加载财报数据并构建查找结构
            fina_lookup = self._build_financial_lookup(db)

            # 3. 逐股扫描
            trades: list[BacktestTrade] = []
            skipped_count = 0

            for stock_code, stock_bars in bars_by_code.items():
                stock_trades = self._scan_stock(
                    stock_code, stock_bars, stock_names.get(stock_code),
                    fina_lookup.get(stock_code, []), params, end_date,
                )
                trades.extend(stock_trades)

            logger.info(
                "市盈率长线回测完成: 扫描 %d 只股票, 产生 %d 笔交易",
                len(bars_by_code), len(trades),
            )

            return BacktestResult(trades=trades, skipped_count=skipped_count)

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
    def _batch_latest_financial(
        db, stock_codes: list[str], as_of_date: date,
    ) -> dict[str, tuple[float, date]]:
        """批量查询一组股票在 as_of_date 前的最新财报 (roe, report_date)。"""
        if not stock_codes:
            return {}

        # 子查询：每只股票最新的 report_date
        sub = (
            select(
                StockFinancialReport.stock_code,
                func.max(StockFinancialReport.report_date).label("max_rd"),
            )
            .where(
                and_(
                    StockFinancialReport.stock_code.in_(stock_codes),
                    StockFinancialReport.report_date <= as_of_date,
                )
            )
            .group_by(StockFinancialReport.stock_code)
            .subquery()
        )

        rows = db.execute(
            select(
                StockFinancialReport.stock_code,
                StockFinancialReport.roe,
                StockFinancialReport.report_date,
            )
            .join(
                sub,
                and_(
                    StockFinancialReport.stock_code == sub.c.stock_code,
                    StockFinancialReport.report_date == sub.c.max_rd,
                ),
            )
        ).all()

        result: dict[str, tuple[float, date]] = {}
        for r in rows:
            roe_val = float(r.roe) if r.roe is not None else None
            if roe_val is not None:
                result[r.stock_code] = (roe_val, r.report_date)
        return result

    @staticmethod
    def _batch_prev_bars(db, stock_codes: list[str], as_of_date: date) -> dict[str, StockDailyBar]:
        """批量查询一组股票在 as_of_date 前一日的日线数据（用于均线比较）。"""
        if not stock_codes:
            return {}

        # 查询前一日的数据
        rows = db.execute(
            select(StockDailyBar)
            .where(
                and_(
                    StockDailyBar.stock_code.in_(stock_codes),
                    StockDailyBar.trade_date < as_of_date,
                    StockDailyBar.ma5.isnot(None),
                    StockDailyBar.ma10.isnot(None),
                    StockDailyBar.ma20.isnot(None),
                )
            )
            .order_by(StockDailyBar.stock_code, StockDailyBar.trade_date.desc())
        ).scalars().all()

        # 每只股票只取最近一条
        result: dict[str, StockDailyBar] = {}
        for bar in rows:
            if bar.stock_code not in result:
                result[bar.stock_code] = bar
        return result

    @staticmethod
    def _is_bullish_alignment(bar: StockDailyBar, prev_bar: StockDailyBar | None) -> bool:
        """
        检查均线是否首次多头排列：
        1. MA5 > MA10 > MA20
        2. 三者都比前一天高
        """
        if bar.ma5 is None or bar.ma10 is None or bar.ma20 is None:
            return False
        if prev_bar is None:
            return False
        if prev_bar.ma5 is None or prev_bar.ma10 is None or prev_bar.ma20 is None:
            return False

        # 条件1：MA5 > MA10 > MA20
        if not (bar.ma5 > bar.ma10 > bar.ma20):
            return False

        # 条件2：三者都比前一天高
        if not (bar.ma5 > prev_bar.ma5):
            return False
        if not (bar.ma10 > prev_bar.ma10):
            return False
        if not (bar.ma20 > prev_bar.ma20):
            return False

        return True

    @staticmethod
    def _build_financial_lookup(db) -> dict[str, list[tuple[date, float | None]]]:
        """
        加载全量财报，构建 {stock_code: [(report_date, roe), ...]} 字典。
        列表按 report_date 升序排列，用于 bisect 查找。
        """
        rows = db.execute(
            select(
                StockFinancialReport.stock_code,
                StockFinancialReport.report_date,
                StockFinancialReport.roe,
            )
            .order_by(StockFinancialReport.stock_code, StockFinancialReport.report_date)
        ).all()

        lookup: dict[str, list[tuple[date, float | None]]] = defaultdict(list)
        for r in rows:
            roe_val = float(r.roe) if r.roe is not None else None
            lookup[r.stock_code].append((r.report_date, roe_val))
        return dict(lookup)

    @staticmethod
    def _find_latest_financial(
        fina_list: list[tuple[date, float | None]],
        trade_date: date,
    ) -> tuple[float | None, date | None]:
        """在排序的财报列表中查找 report_date <= trade_date 的最新记录。"""
        if not fina_list:
            return None, None

        # fina_list 是 (report_date, roe) 列表，按 report_date 升序
        # 使用 bisect_right 查找插入点
        dates = [f[0] for f in fina_list]
        idx = bisect_right(dates, trade_date)
        if idx == 0:
            return None, None

        entry = fina_list[idx - 1]
        return entry[1], entry[0]

    def _scan_stock(
        self,
        stock_code: str,
        bars: list[StockDailyBar],
        stock_name: str | None,
        fina_list: list[tuple[date, float | None]],
        params: _Params,
        end_date: date,
    ) -> list[BacktestTrade]:
        """
        扫描单只股票的日线数据，产生买卖交易。
        
        逻辑：
        1. 筛选阶段：PE百分位 < 6% 且 PE > 0 且 ROE > 15% → 进入观察池
        2. 买入阶段：观察池中的股票出现均线首次多头排列时买入
        3. 卖出阶段：止损15% / 止盈30% / PE百分位 >= 30
        """
        trades: list[BacktestTrade] = []
        in_position = False
        in_watchlist = False  # 是否在观察池中
        buy_date_val: date | None = None
        buy_price_val: float | None = None
        buy_extra: dict | None = None

        for i, bar in enumerate(bars):
            pe_pct = _to_float(bar.pe_percentile)
            pe_val = _to_float(bar.pe)
            close_price = _to_float(bar.close)
            high_price = _to_float(bar.high)
            low_price = _to_float(bar.low)

            if pe_pct is None or close_price is None:
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
                # 3. PE估值修复：PE百分位 >= 30
                elif pe_pct >= params.pe_sell_threshold:
                    exit_reason = "估值修复（PE百分位>=30）"
                    sell_price = close_price
                
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
                        trigger_date=buy_date_val,
                        extra={
                            **(buy_extra or {}),
                            "sell_pe_percentile": pe_pct,
                            "exit_reason": exit_reason,
                            "stop_loss_price": float(stop_loss_price),
                            "profit_take_price": float(profit_take_price),
                        },
                    ))
                    in_position = False
                    in_watchlist = False  # 卖出后也退出观察池
                    buy_date_val = None
                    buy_price_val = None
                    buy_extra = None
            else:
                # 未持仓：检查筛选条件和买入时机
                roe_val, report_date = self._find_latest_financial(fina_list, bar.trade_date)
                
                # 筛选条件：PE百分位 < 6% 且 PE > 0 且 ROE > 15%
                if (pe_pct < params.pe_filter_threshold and 
                    pe_val is not None and pe_val > 0 and
                    roe_val is not None and roe_val > params.roe_min):
                    in_watchlist = True
                
                # 如果在观察池中，检查均线多头排列
                if in_watchlist and i > 0:
                    prev_bar = bars[i - 1]
                    if self._is_bullish_alignment(bar, prev_bar):
                        # 买入
                        in_position = True
                        buy_date_val = bar.trade_date
                        buy_price_val = close_price
                        buy_extra = {
                            "buy_pe_percentile": pe_pct,
                            "buy_pe": pe_val,
                            "roe": roe_val,
                            "report_date": str(report_date) if report_date else None,
                            "ma5": _to_float(bar.ma5),
                            "ma10": _to_float(bar.ma10),
                            "ma20": _to_float(bar.ma20),
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
                trigger_date=buy_date_val,
                extra=buy_extra,
            ))

        return trades
