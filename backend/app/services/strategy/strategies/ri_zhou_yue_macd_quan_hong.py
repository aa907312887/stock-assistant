"""
MACD 日周月全红（内置策略，`strategy_id`=`ri_zhou_yue_macd_quan_hong`）。

【策略名称】：MACD 日周月全红

【目标】：在截止模拟日，筛出**日线、周线、月线** MACD 柱（`macd_hist`）均为正的标的，供历史模拟交易「策略选股」快捷对照；**不含**多周期 MACD 共振主升浪的 6 日递增红柱、涨幅过滤等完整买入条件。

【适用范围】：
- 市场：A 股；剔除 **ST / *ST** 及 **北交所**。
- 数据粒度：日线 + 周线 + 月线；依赖预计算的 `macd_hist` 与 `trade_week_end` / `trade_month_end`。

【核心规则】（选股 execute）：
1) **日线**：`trade_date == as_of_date` 且 `macd_hist > 0`。
2) **周线**：取 `trade_week_end ≤ as_of_date` 的最近一根 K 线，且 `macd_hist > 0`。
3) **月线**：取 `trade_month_end ≤ as_of_date` 的最近一根 K 线，且 `macd_hist > 0`。

【边界】：周/月线缺失或对齐后无 K 线则不入选；`macd_hist` 为空视为不满足。

【输出】：`summary` 含 `macd_red_streak_days`（自最近一次绿柱起连续红柱交易日数）与 `close`；`trigger_date` 为 as_of_date。

【示例】：
- 例 1：模拟日三线均为红柱 → 入选。
- 例 2：日线红柱但周线最近一根为绿柱 → 不入选。
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, select

from app.database import SessionLocal
from app.models import StockDailyBar
from app.services.multi_tf_macd_filter import (
    codes_with_multi_tf_macd_red,
    load_daily_macd_hist_by_code,
    load_weekly_monthly_hist_indices,
    macd_red_streak_days_by_code,
)
from app.services.strategy.strategies.chun_zheng_ma_duotou import (
    _load_excluded_codes,
    _load_stock_exchanges,
    _load_stock_names,
)
from app.services.strategy.strategy_base import (
    BacktestResult,
    StockStrategy,
    StrategyCandidate,
    StrategyDescriptor,
    StrategyExecutionResult,
    StrategySignal,
)

logger = logging.getLogger(__name__)

STRATEGY_ID = "ri_zhou_yue_macd_quan_hong"


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


class RiZhouYueMacdQuanHongStrategy(StockStrategy):
    """日/周/月 MACD 柱均为正；仅选股，历史回测占位为空。"""

    strategy_id = STRATEGY_ID
    version = "v1.0.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="MACD日周月全红",
            version=self.version,
            short_description=(
                "截止日日线 MACD 红柱，且对齐周线、月线最近一根均为红柱；"
                "不含 6 日递增等共振主升浪完整买入条件。"
            ),
            description=(
                "**选股（execute）**：模拟日 **日线** `macd_hist > 0`；"
                "**周线**、**月线** 取周期末 ≤ 模拟日的最近一根 K 线且 `macd_hist > 0`。\n"
                "与「多周期 MACD 共振主升浪」的**共振部分**口径一致，但**不要求**绿转红、六日递增、涨幅过滤。\n"
                "**历史回测**：本期未提供独立回测规则，请使用「多周期 MACD 共振主升浪」做区间回测。\n"
                "剔除 ST/*ST 与北交所。不构成投资建议。"
            ),
            assumptions=[
                "日/周/月 macd_hist 已与 K 线同步任务预计算一致；红柱为 hist>0。",
                "周/月线按 trade_week_end、trade_month_end 与模拟日对齐。",
            ],
            risks=[
                "满足三周期红柱的标的数量可能较多，需自行叠加风控。",
                "周/月数据未回填的标的不会入选。",
            ],
            route_path="/strategy/ri-zhou-yue-macd-quan-hong",
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
                        StockDailyBar.macd_hist.isnot(None),
                        StockDailyBar.macd_hist > 0,
                        StockDailyBar.stock_code.notin_(excluded),
                    )
                )
                .order_by(StockDailyBar.stock_code)
            )
            rows = list(db.execute(stmt).scalars().all())
            codes = [r.stock_code for r in rows]
            weekly_idx, monthly_idx = load_weekly_monthly_hist_indices(db, as_of_date, codes)
            ok_codes = codes_with_multi_tf_macd_red(weekly_idx, monthly_idx, codes, as_of_date)
            ok_list = sorted(ok_codes)
            daily_by_code = load_daily_macd_hist_by_code(db, ok_list, as_of_date)
            streak_by_code = macd_red_streak_days_by_code(daily_by_code, ok_list, as_of_date)

            items: list[StrategyCandidate] = []
            signals: list[StrategySignal] = []
            for bar in rows:
                if bar.stock_code not in ok_codes:
                    continue
                streak = streak_by_code.get(bar.stock_code, 0)
                items.append(
                    StrategyCandidate(
                        stock_code=bar.stock_code,
                        stock_name=names.get(bar.stock_code),
                        exchange_type=exchanges.get(bar.stock_code),
                        trigger_date=as_of_date,
                        summary={
                            "macd_red_streak_days": streak,
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
                            "macd_red_streak_days": streak,
                            "multi_tf_macd_red": True,
                        },
                    )
                )

            logger.info(
                "MACD日周月全红选股: as_of=%s 日线红柱=%d 入选=%d",
                as_of_date,
                len(rows),
                len(items),
            )

            return StrategyExecutionResult(
                as_of_date=as_of_date,
                assumptions={
                    "data_granularity": "日/周/月线",
                    "stock_universe": "A股(排除ST/北交所)",
                    "filter": "daily+weekly+monthly macd_hist>0 aligned to as_of_date",
                },
                params={
                    "daily": "macd_hist > 0 on as_of_date",
                    "weekly": "latest trade_week_end <= as_of, macd_hist > 0",
                    "monthly": "latest trade_month_end <= as_of, macd_hist > 0",
                },
                items=items,
                signals=signals,
            )
        finally:
            db.close()

    def backtest(self, *, start_date: date, end_date: date) -> BacktestResult:
        return BacktestResult(
            trades=[],
            skipped_count=0,
            skip_reasons=[
                "本策略仅提供选股（execute）；区间回测请使用 duo_zhou_qi_macd_gong_zhen",
            ],
        )
