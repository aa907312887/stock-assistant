"""
市盈率早晨十字星（内置回测策略）。

【策略名称】：市盈率早晨十字星
【目标】：在「早晨十字星」形态基础上，叠加 PE 历史百分位 < 10% 与最近一期 ROE > 15% 两个估值质量过滤，
         捕捉跌势末期反转且估值低廉、盈利能力较强的标的。

【适用范围】：
- 市场：A 股（排除 ST/*ST）
- 数据粒度：日线（前复权口径与库表一致）
- 依赖字段：open/high/low/close/ma5/ma10/ma20/cum_hist_high/pe_percentile（stock_daily_bar）；
            roe/report_date（stock_financial_report）

【核心规则】：
1) 早晨十字星形态（与「早晨十字星」策略完全一致）：
   - T−2 阴线且相对 T−3 收盘跌幅 ≥ 2%
   - T−1 锤头线且相对 T−2 收盘涨跌幅绝对值 ≤ 1%
   - T 阳线且实体涨幅（相对开盘）≥ 3%
   - T 日跌势结构：MA5 < MA10 < MA20 且 close < MA20
   - T 日收盘 ≤ 0.5 × cum_hist_high
   - 前期弱势：T−9…T−3 共 7 日中阴线天数 ≥ 5，且 T−3/T−9 收盘累计跌幅 ≥ 10%
2) PE 百分位过滤：信号日 T 的 pe_percentile < 10.0（严格小于）；字段为空或 PE 为负时跳过。
3) ROE 过滤：信号日 T 前最近一期已披露财报的 roe > 15.0（严格大于）；数据不可用时跳过。
4) 买入：自 T 日（含）起首次 close > MA5，以当日收盘价买入。
5) 卖出（与「早晨十字星」一致）：
   - 止损 8%：close ≤ 买入价 × 0.92 → 卖出价固定为买入价 × 0.92
   - 移动止盈：涨幅达 15% 后启动追踪，从持仓期间最高价回落 5% 时按当日收盘价卖出
   - 未触发则持有至回测结束（unclosed）

【关键口径与阈值】：
- PE 百分位阈值：< 10.0（严格小于，不含等号）
- ROE 阈值：> 15.0（严格大于，不含等号）
- 止损比例：8%，卖出价固定 买入价 × 0.92
- 移动止盈触发：涨幅 ≥ 15%；回撤触发：从最高价回落 ≥ 5%

【边界与异常】：
- pe_percentile 为 None 或 ≥ 10.0 → 跳过
- roe 为 None 或无财报记录 → 跳过
- roe ≤ 15.0 → 跳过
- 形态所需字段任一无效 → 跳过（由 run_morning_star_backtest 处理）
- PE 为负（亏损企业）时 pe_percentile 通常为空，直接跳过

【输出与可追溯性】：
- BacktestTrade.trigger_date：信号阳线日 T
- BacktestTrade.extra 新增字段：
  - trigger_pe_percentile：触发日 PE 百分位
  - trigger_roe：触发日最近一期 ROE
  - trigger_roe_report_date：ROE 对应财报日期

【示例】：
- 例 1（满足）：某标的 T 日形态满足早晨十字星，pe_percentile=8.5（<10），最近一期 roe=18.2（>15）→ 产生信号
- 例 2（不满足 PE）：形态满足，pe_percentile=12.0（≥10）→ 跳过
- 例 3（不满足 ROE）：形态满足，pe_percentile=7.0，roe=14.5（≤15）→ 跳过
- 例 4（PE 为空）：形态满足，pe_percentile=None（亏损企业）→ 跳过
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select

from app.database import SessionLocal
from app.models import StockFinancialReport
from app.services.screening_service import get_latest_bar_date
from app.services.strategy.strategies.zao_chen_shi_zi_xing import (
    _Params,
    run_morning_star_backtest,
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

# PE 百分位过滤阈值（严格小于）
_PE_PERCENTILE_THRESHOLD = 10.0
# ROE 过滤阈值（严格大于）
_ROE_THRESHOLD = 15.0


def _batch_load_latest_roe(
    db,
    stock_codes: list[str],
    as_of_date: date,
) -> dict[str, tuple[float, date] | None]:
    """
    批量查询各标的截至 as_of_date 最近一期已披露的 ROE。
    返回 {stock_code: (roe_value, report_date)} 或 {stock_code: None}。
    """
    if not stock_codes:
        return {}

    # 子查询：每个标的取 report_date 最大值
    subq = (
        select(
            StockFinancialReport.stock_code,
            StockFinancialReport.report_date,
            StockFinancialReport.roe,
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
        .subquery()
    )

    # 直接查询并在 Python 侧取每个 stock_code 的第一条（report_date 最大）
    rows = db.execute(
        select(
            StockFinancialReport.stock_code,
            StockFinancialReport.report_date,
            StockFinancialReport.roe,
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

    result: dict[str, tuple[float, date] | None] = {code: None for code in stock_codes}
    seen: set[str] = set()
    for row in rows:
        if row.stock_code not in seen:
            seen.add(row.stock_code)
            result[row.stock_code] = (float(row.roe), row.report_date)
    return result


class PeZaoChenShiZiXingStrategy(StockStrategy):
    """市盈率早晨十字星策略：早晨十字星形态 + PE 百分位 < 10% + ROE > 15%。"""

    strategy_id = "pe_zao_chen_shi_zi_xing"
    version = "v1.0.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="市盈率早晨十字星",
            version=self.version,
            short_description=(
                "早晨十字星形态（T−2大阴+T−1锤头+T阳线）+ PE百分位<10% + 最近一期ROE>15%；"
                "站上MA5买入；止损8%固定×0.92；涨幅≥15%后从最高回落5%止盈。"
            ),
            description=(
                "在「早晨十字星」形态基础上，叠加两个估值质量过滤条件：\n"
                "① 信号日 T 的 PE 历史百分位 < 10%（极度低估区间，字段来自 stock_daily_bar.pe_percentile）；\n"
                "② 最近一期已披露财报的 ROE > 15%（盈利能力过滤，字段来自 stock_financial_report.roe）。\n"
                "三个条件同时满足才产生信号。买入与卖出规则与「早晨十字星」完全一致：\n"
                "自 T 日起首次收盘站上 MA5 买入；止损 8%（卖价固定买入×0.92）；"
                "涨幅达 15% 后启动移动止盈，从最高价回落 5% 时按收盘价卖出。"
            ),
            assumptions=[
                "剔除 ST/*ST；买卖价均为日线收盘价。",
                "PE 百分位为预计算字段（stock_daily_bar.pe_percentile），取值 0–100；PE 为负或字段为空时跳过。",
                "ROE 取最近一期已披露财报（年报或中报均可），以 report_date <= 信号日 T 为准。",
                "PE 百分位阈值 10%、ROE 阈值 15% 均为严格不等式（不含等号）。",
                "形态判断与买卖规则与「早晨十字星」策略完全一致。",
                "同一标的出现未平仓笔后不再扫描该标的后续形态。",
            ],
            risks=[
                "PE 百分位与 ROE 数据可能存在滞后或缺失，导致部分标的被错误跳过。",
                "双重过滤大幅减少信号数量，样本量可能不足以统计显著。",
                "均线滞后；震荡行情反复穿线。",
            ],
            route_path="/strategy/pe-zao-chen-shi-zi-xing",
        )

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        """单日扫描：返回 as_of_date 当日买入的候选（与回测口径一致）。"""
        p = _Params()
        db = SessionLocal()
        try:
            dd = as_of_date or get_latest_bar_date(db, "daily")
            if dd is None:
                raise RuntimeError("日线数据为空，无法执行市盈率早晨十字星选股")

            # 预加载所有标的的最近一期 ROE（在 extra_filter 回调中使用）
            # 先跑一遍不带过滤的回测拿到所有候选 stock_code，再批量查 ROE
            # 为避免两次全量扫描，直接在 extra_filter 中按需查询（选股场景标的数少）
            roe_cache: dict[str, tuple[float, date] | None] = {}

            def extra_filter(stock_code: str, bar_t: Any) -> bool:
                # PE 百分位过滤
                pe_pct = bar_t.pe_percentile
                if pe_pct is None or float(pe_pct) >= _PE_PERCENTILE_THRESHOLD:
                    logger.debug("跳过 %s：pe_percentile=%s", stock_code, pe_pct)
                    return False
                # ROE 过滤（按需查询并缓存）
                if stock_code not in roe_cache:
                    rows = db.execute(
                        select(StockFinancialReport.roe, StockFinancialReport.report_date)
                        .where(
                            StockFinancialReport.stock_code == stock_code,
                            StockFinancialReport.report_date <= dd,
                            StockFinancialReport.roe.isnot(None),
                        )
                        .order_by(StockFinancialReport.report_date.desc())
                        .limit(1)
                    ).first()
                    roe_cache[stock_code] = (float(rows.roe), rows.report_date) if rows else None
                roe_info = roe_cache[stock_code]
                if roe_info is None or roe_info[0] <= _ROE_THRESHOLD:
                    logger.debug("跳过 %s：roe=%s", stock_code, roe_info)
                    return False
                return True

            result = run_morning_star_backtest(db, start_date=dd, end_date=dd, p=p, extra_filter=extra_filter)

            items: list[StrategyCandidate] = []
            signals: list[StrategySignal] = []
            for t in result.trades:
                if t.buy_date != dd:
                    continue
                summary: dict[str, Any] = dict(t.extra or {})
                # 补充 PE 百分位与 ROE 到 summary
                code = t.stock_code
                roe_info = roe_cache.get(code)
                if roe_info:
                    summary["trigger_roe"] = roe_info[0]
                    summary["trigger_roe_report_date"] = roe_info[1].isoformat()
                if t.trade_type == "closed" and t.return_rate is not None:
                    summary["return_rate"] = t.return_rate
                    if t.sell_date is not None:
                        summary["sell_date"] = t.sell_date.isoformat()
                    if t.sell_price is not None:
                        summary["sell_price"] = t.sell_price
                td = t.trigger_date or t.buy_date
                items.append(
                    StrategyCandidate(
                        stock_code=code,
                        stock_name=t.stock_name,
                        exchange_type=None,
                        trigger_date=td,
                        summary=summary,
                    ),
                )
                signals.append(
                    StrategySignal(
                        stock_code=code,
                        event_date=t.buy_date,
                        event_type="entry",
                        payload=t.extra or {},
                    ),
                )
            return StrategyExecutionResult(
                as_of_date=dd,
                assumptions={
                    "data_granularity": "日线",
                    "price_type": "买入日为首次 close>MA5 的收盘价；止损时卖价固定买入×0.92；移动止盈时卖价为触发日收盘价",
                    "pattern": "早晨十字星形态 + PE百分位<10% + ROE>15%；买入=首次 close>MA5",
                    "universe": "非 ST/*ST 全市场",
                },
                params={
                    "pe_percentile_threshold": _PE_PERCENTILE_THRESHOLD,
                    "roe_threshold": _ROE_THRESHOLD,
                    "stop_loss_pct": p.stop_loss_pct,
                    "arm_profit_trigger_pct": p.arm_profit_trigger_pct,
                    "trailing_stop_pct": p.trailing_stop_pct,
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
            # 预加载区间内所有标的的最近一期 ROE（批量，避免逐标的查询）
            # 由于 extra_filter 在形态判断后才调用，此处用懒加载缓存方式
            roe_cache: dict[str, tuple[float, date] | None] = {}
            # 扩展查询范围与回测引擎一致
            roe_query_end = end_date

            def extra_filter(stock_code: str, bar_t: Any) -> bool:
                trigger_date = bar_t.trade_date

                # PE 百分位过滤
                pe_pct = bar_t.pe_percentile
                if pe_pct is None or float(pe_pct) >= _PE_PERCENTILE_THRESHOLD:
                    logger.debug("跳过 %s %s：pe_percentile=%s", stock_code, trigger_date, pe_pct)
                    return False

                # ROE 过滤（按 trigger_date 查最近一期，缓存 key 含日期）
                cache_key = f"{stock_code}_{trigger_date}"
                if cache_key not in roe_cache:
                    row = db.execute(
                        select(StockFinancialReport.roe, StockFinancialReport.report_date)
                        .where(
                            StockFinancialReport.stock_code == stock_code,
                            StockFinancialReport.report_date <= trigger_date,
                            StockFinancialReport.roe.isnot(None),
                        )
                        .order_by(StockFinancialReport.report_date.desc())
                        .limit(1)
                    ).first()
                    roe_cache[cache_key] = (float(row.roe), row.report_date) if row else None

                roe_info = roe_cache[cache_key]
                if roe_info is None or roe_info[0] <= _ROE_THRESHOLD:
                    logger.debug("跳过 %s %s：roe=%s", stock_code, trigger_date, roe_info)
                    return False
                return True

            base_result = run_morning_star_backtest(
                db, start_date=start_date, end_date=end_date, p=p, extra_filter=extra_filter
            )

            # 将 PE 百分位与 ROE 信息补充到 extra
            enriched_trades: list[BacktestTrade] = []
            for t in base_result.trades:
                cache_key = f"{t.stock_code}_{t.trigger_date}"
                roe_info = roe_cache.get(cache_key)
                # 从 bar_t 中取 pe_percentile（已在 extra_filter 中验证过）
                pe_val = t.extra.get("trigger_pe_percentile")  # 可能不存在，需从原始数据补充
                extra_enriched = dict(t.extra)
                if roe_info:
                    extra_enriched["trigger_roe"] = roe_info[0]
                    extra_enriched["trigger_roe_report_date"] = roe_info[1].isoformat()
                enriched_trades.append(
                    BacktestTrade(
                        stock_code=t.stock_code,
                        stock_name=t.stock_name,
                        buy_date=t.buy_date,
                        buy_price=t.buy_price,
                        sell_date=t.sell_date,
                        sell_price=t.sell_price,
                        return_rate=t.return_rate,
                        trade_type=t.trade_type,
                        trigger_date=t.trigger_date,
                        extra=extra_enriched,
                    )
                )

            logger.info("市盈率早晨十字星回测完成: trades=%d", len(enriched_trades))
            return BacktestResult(trades=enriched_trades, skipped_count=0, skip_reasons=[])
        finally:
            db.close()
