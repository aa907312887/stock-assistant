"""
市盈率长线价值投资策略。

【策略名称】：市盈率长线价值投资
【目标】：筛选 PE 历史百分位极度低估 + 基本面健康的股票，用于长线价值投资参考。

【适用范围】：
- 市场：A 股（排除 ST 股票、北交所、小盘股）
- 数据粒度：日线
- 依赖字段：pe_percentile / pe / open / high / low / close / total_market_cap（来自 stock_daily_bar）
            roe / debt_to_assets / report_date（来自 stock_financial_report）

【核心规则】：

1) 选股条件（execute 方法）：
   - PE 百分位 < 5%（严格小于）
   - PE 为正数（pe > 0）
   - 最近连续 3 期已披露财报的 ROE 均 > 15%（严格大于）
   - 最近一期已披露资产负债率 < 80%（严格小于）
   - 当日总市值 >= 300 亿元（排除小盘股）
   - 任一财务指标缺失或不满足条件时跳过该股票

2) 回测买入条件（backtest 方法）：
   - PE 百分位从 5% 以上首次跌落到 5% 以内
   - PE 为正数（pe > 0）
   - 信号日最近连续 3 期已披露财报的 ROE 均 > 15%
   - 信号日总市值 >= 300 亿元（排除小盘股）
   - 以信号日的下一交易日开盘价买入

3) 回测卖出条件（优先级从高到低）：
   - 止损：亏损 >= 20% → 以止损价卖出
   - 止盈：盈利 >= 30% → 以止盈价卖出

4) 多标的：
   - 可同时持有多只股票，每只股票独立跟踪
   - 同一股票卖出后可在后续重新买入

【关键口径与阈值】：
- 选股 PE 百分位阈值：< 5%（不要求首次跌入，只要满足就选出）
- 回测 PE 百分位阈值：从 5% 以上首次跌到 5% 以内
- PE 必须为正数
- ROE 阈值：最近连续 3 期均 > 15%
- 资产负债率阈值：< 80%
- 最小市值阈值：>= 300 亿元
- 止盈比例：+30%
- 止损比例：-20%

【边界与异常】：
- pe_percentile 为 None 或 >= 5.0 → 跳过
- pe 为 None 或 <= 0 → 跳过
- 财报记录不足 3 期 → 跳过
- 任一期 roe 为 None 或 <= 15.0 → 跳过
- debt_to_assets 为 None 或 >= 80.0 → 跳过
- total_market_cap 为 None 或 < 300 亿元 → 跳过

【输出与可追溯性】：
- StrategyCandidate.summary 包含：pe_percentile / pe / roe_periods / debt_to_assets / report_date / total_market_cap
- 回测交易记录包含触发日 PE 百分位、ROE 等信息
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, and_

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
    pe_entry_threshold: float = 5.0      # PE百分位 < 5% 时触发
    roe_threshold: float = 15.0          # ROE > 15%
    roe_check_periods: int = 3           # 最近连续 3 期财报 ROE 均须达标
    debt_to_assets_threshold: float = 80.0  # 资产负债率 < 80%
    min_market_cap: float = 30_000_000_000.0  # 最小总市值 300 亿元（排除小盘股）
    profit_take_pct: float = 0.30        # 止盈：盈利30%
    stop_loss_pct: float = 0.20          # 止损：亏损20%


def _to_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _batch_load_latest_n_financial(
    db,
    stock_codes: list[str],
    as_of_date: date,
    n: int = 3,
) -> dict[str, list[dict]]:
    """
    批量查询各标的截至 as_of_date 最近 n 期已披露的财务数据（按 report_date 倒序）。
    返回 {stock_code: [{"roe": float, "debt_to_assets": float, "report_date": date}, ...]}，
    列表长度 <= n，可能为空。
    """
    if not stock_codes:
        return {}

    rows = db.execute(
        select(
            StockFinancialReport.stock_code,
            StockFinancialReport.report_date,
            StockFinancialReport.roe,
            StockFinancialReport.debt_to_assets,
        )
        .where(
            StockFinancialReport.stock_code.in_(stock_codes),
            StockFinancialReport.report_date <= as_of_date,
            StockFinancialReport.roe.isnot(None),
        )
        .order_by(
            StockFinancialReport.stock_code,
            StockFinancialReport.report_date.desc(),
        )
    ).all()

    result: dict[str, list[dict]] = {code: [] for code in stock_codes}
    for row in rows:
        lst = result[row.stock_code]
        if len(lst) < n:
            lst.append({
                "roe": float(row.roe),
                "debt_to_assets": float(row.debt_to_assets) if row.debt_to_assets is not None else None,
                "report_date": row.report_date,
            })
    return result


def _check_roe_consecutive(
    reports: list[dict],
    n: int,
    roe_threshold: float,
) -> tuple[bool, list[float]]:
    """
    检查最近 n 期财报 ROE 是否均 > roe_threshold。
    返回 (是否通过, 各期 ROE 列表)。
    """
    if len(reports) < n:
        return False, []
    roe_values = [r["roe"] for r in reports[:n]]
    passed = all(v > roe_threshold for v in roe_values)
    return passed, roe_values


def _load_all_financials_by_code(db) -> dict[str, list[dict]]:
    """
    预加载全部财报数据，按 stock_code 分组、report_date 倒序排列。
    用于回测中按信号日快速查找最近 N 期财报。
    """
    rows = db.execute(
        select(
            StockFinancialReport.stock_code,
            StockFinancialReport.report_date,
            StockFinancialReport.roe,
            StockFinancialReport.debt_to_assets,
        )
        .where(StockFinancialReport.roe.isnot(None))
        .order_by(
            StockFinancialReport.stock_code,
            StockFinancialReport.report_date.desc(),
        )
    ).all()

    result: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        result[row.stock_code].append({
            "roe": float(row.roe),
            "debt_to_assets": float(row.debt_to_assets) if row.debt_to_assets is not None else None,
            "report_date": row.report_date,
        })
    return result


def _get_recent_reports(
    all_reports: list[dict],
    as_of_date: date,
    n: int,
) -> list[dict]:
    """从已按 report_date 倒序排列的财报列表中，取截至 as_of_date 的最近 n 期。"""
    result = []
    for r in all_reports:
        if r["report_date"] <= as_of_date:
            result.append(r)
            if len(result) >= n:
                break
    return result


class PeValueInvestmentStrategy(StockStrategy):
    """市盈率长线价值投资策略实现。"""

    strategy_id = "pe_value_investment"
    version = "v3.0.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="市盈率长线价值投资",
            version=self.version,
            short_description=(
                "筛选 PE 百分位 < 5% + 连续 3 期 ROE > 15% + 资产负债率 < 80% + 总市值 >= 300 亿的股票，"
                "用于长线价值投资参考。"
            ),
            description=(
                "本策略筛选 PE 历史百分位极度低估且基本面健康的大中盘股票："
                "PE 百分位 < 5%、最近连续 3 个财报期 ROE 均 > 15%、资产负债率 < 80%、"
                "当日总市值 >= 300 亿元。"
                "回测模式下，当 PE 百分位从 5% 以上首次跌落到 5% 以内时买入，"
                "盈利 30% 止盈，亏损 20% 止损。"
            ),
            assumptions=[
                "PE 百分位使用该股自 2019 年以来的历史 PE 最大最小值计算。",
                "选股/回测买入条件：PE 百分位 < 5%、PE > 0、连续 3 期 ROE > 15%、资产负债率 < 80%、总市值 >= 300 亿。",
                "回测买入触发：PE 百分位从 5% 以上首次跌落到 5% 以内，且满足上述基本面条件。",
                "回测买入价格：信号日的下一交易日开盘价。",
                "回测卖出条件（优先级从高到低）：",
                "  1. 止损：亏损 >= 20% 时以止损价卖出。",
                "  2. 止盈：盈利 >= 30% 时以止盈价卖出。",
                "排除 ST/*ST 股票、北交所股票、总市值 < 300 亿的小盘股。",
                "可同时持有多只股票，每只独立跟踪。",
                "本策略用于历史验证，不构成投资建议。",
            ],
            risks=[
                "PE 低不代表安全，可能存在业绩持续恶化的价值陷阱。",
                "ROE 基于最近 3 期财报，可能滞后于当前经营状况。",
                "长线持有期间可能遭遇黑天鹅事件。",
                "数据缺失、停牌会影响回测结果准确性。",
            ],
            route_path="/strategy/pe-value-investment",
        )

    # ------------------------------------------------------------------
    # execute() — 实时选股
    # ------------------------------------------------------------------

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        """选股执行：筛选 PE 百分位 < 5% + 连续3期 ROE > 15% + 资产负债率 < 80% + 总市值 >= 300亿 的股票。"""
        params = _Params()
        if as_of_date is None:
            raise ValueError("as_of_date 不能为空")

        db = SessionLocal()
        try:
            excluded_codes = self._load_excluded_codes(db)

            # 1. 查询当日 PE 百分位在合理范围 + 市值达标的股票
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
                        StockDailyBar.total_market_cap.isnot(None),
                        StockDailyBar.total_market_cap >= params.min_market_cap,
                        StockDailyBar.stock_code.notin_(excluded_codes),
                    )
                )
            )
            candidate_bars = db.execute(bars_stmt).scalars().all()

            if not candidate_bars:
                return StrategyExecutionResult(
                    as_of_date=as_of_date,
                    assumptions={"data_granularity": "日线", "stock_universe": "A股(排除ST/北交所/小盘股)"},
                    params={
                        "pe_entry_threshold": params.pe_entry_threshold,
                        "roe_threshold": params.roe_threshold,
                        "roe_check_periods": params.roe_check_periods,
                        "debt_to_assets_threshold": params.debt_to_assets_threshold,
                        "min_market_cap": params.min_market_cap,
                        "profit_take_pct": params.profit_take_pct,
                        "stop_loss_pct": params.stop_loss_pct,
                    },
                    items=[],
                    signals=[],
                )

            candidate_codes = [b.stock_code for b in candidate_bars]

            # 2. 批量查询最近 3 期财务数据
            financial_map = _batch_load_latest_n_financial(db, candidate_codes, as_of_date, n=params.roe_check_periods)

            # 3. 筛选
            stock_names = self._load_stock_names(db)
            stock_exchanges = self._load_stock_exchanges(db)

            items: list[StrategyCandidate] = []
            signals: list[StrategySignal] = []

            for bar in candidate_bars:
                reports = financial_map.get(bar.stock_code, [])

                # 检查连续 3 期 ROE 是否均 > 15%
                roe_passed, roe_values = _check_roe_consecutive(reports, params.roe_check_periods, params.roe_threshold)
                if not roe_passed:
                    continue

                # 检查最近一期资产负债率 < 80%
                latest = reports[0]
                debt_to_assets = latest["debt_to_assets"]
                if debt_to_assets is None or debt_to_assets >= params.debt_to_assets_threshold:
                    continue

                report_date = latest["report_date"]
                market_cap_yi = _to_float(bar.total_market_cap) / 1e8 if bar.total_market_cap else None

                items.append(StrategyCandidate(
                    stock_code=bar.stock_code,
                    stock_name=stock_names.get(bar.stock_code),
                    exchange_type=stock_exchanges.get(bar.stock_code),
                    trigger_date=as_of_date,
                    summary={
                        "pe_percentile": _to_float(bar.pe_percentile),
                        "pe": _to_float(bar.pe),
                        "roe_periods": roe_values,
                        "debt_to_assets": debt_to_assets,
                        "report_date": report_date.isoformat() if report_date else None,
                        "total_market_cap_yi": market_cap_yi,
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
                        "roe_periods": roe_values,
                        "debt_to_assets": debt_to_assets,
                        "report_date": report_date.isoformat() if report_date else None,
                        "total_market_cap_yi": market_cap_yi,
                    },
                ))

            logger.info(
                "市盈率长线价值选股完成: as_of_date=%s, 扫描 %d 只低PE股, 符合条件 %d 只候选",
                as_of_date, len(candidate_bars), len(items),
            )

            return StrategyExecutionResult(
                as_of_date=as_of_date,
                assumptions={"data_granularity": "日线", "stock_universe": "A股(排除ST/北交所/小盘股)"},
                params={
                    "pe_entry_threshold": params.pe_entry_threshold,
                    "roe_threshold": params.roe_threshold,
                    "roe_check_periods": params.roe_check_periods,
                    "debt_to_assets_threshold": params.debt_to_assets_threshold,
                    "min_market_cap": params.min_market_cap,
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

            # 1. 加载日线数据（需要有 pe_percentile、pe、价格、市值数据）
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

            # 2. 预加载全部财报数据（按 stock_code 分组、report_date 倒序）
            financials_by_code = _load_all_financials_by_code(db)

            logger.info(
                "市盈率长线回测: 加载 %d 只股票的日线数据, %d 只股票的财报数据, 时间范围 %s ~ %s",
                len(bars_by_code), len(financials_by_code), start_date, end_date,
            )

            # 3. 逐股扫描
            trades: list[BacktestTrade] = []

            for stock_code, stock_bars in bars_by_code.items():
                stock_financials = financials_by_code.get(stock_code, [])
                stock_trades = self._scan_stock(
                    stock_code, stock_bars, stock_name=stock_names.get(stock_code),
                    params=params, start_date=start_date, end_date=end_date,
                    financials=stock_financials,
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
        *,
        stock_name: str | None,
        params: _Params,
        start_date: date,
        end_date: date,
        financials: list[dict],
    ) -> list[BacktestTrade]:
        """
        扫描单只股票的日线数据，产生买卖交易。

        逻辑：
        1. 买入：PE 百分位从 5% 以上首次跌落到 5% 以内，
           且信号日连续 3 期 ROE > 15%，且信号日总市值 >= 300 亿，
           次日开盘价买入
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
                if pe_pct < params.pe_entry_threshold and pe_val is not None and pe_val > 0 and i > 0:
                    prev_bar = bars[i - 1]
                    prev_pe = _to_float(prev_bar.pe_percentile)

                    # 首次跌入判断
                    if prev_pe is not None and prev_pe >= params.pe_entry_threshold:
                        # 市值过滤：信号日总市值 >= 300 亿
                        market_cap = _to_float(bar.total_market_cap)
                        if market_cap is None or market_cap < params.min_market_cap:
                            continue

                        # ROE 连续 3 期校验
                        recent = _get_recent_reports(financials, bar.trade_date, params.roe_check_periods)
                        roe_ok, roe_values = _check_roe_consecutive(recent, params.roe_check_periods, params.roe_threshold)
                        if not roe_ok:
                            continue

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
                                    "roe_periods": roe_values,
                                    "total_market_cap_yi": market_cap / 1e8 if market_cap else None,
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
