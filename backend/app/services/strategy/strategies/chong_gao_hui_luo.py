"""
冲高回落战法（首个内置策略）。

【策略名称】：冲高回落战法
【目标】：在 A 股中识别“盘中强势拉升（从开盘到最高涨幅 >=10%）但收盘从最高回落 >=3%”的个股，作为次日低开潜在交易机会的候选集合。
【适用范围】：
- 市场：A 股
- 数据粒度：日线（无分时数据）
- 依赖字段：open / high / close / volume / trade_date（来自 stock_daily_bar），以及 stock_basic.name

【核心规则】：
1) 触发（第 0 天=T）：
   - 大涨（大阳线）定义：当日从开盘到最高的最大涨幅满足
     (high - open) / open >= 10%
   - 冲高回落：从当日最高点回落至少 3 个点（百分比）：
     (high - close) / high >= 3%
   - 放量：触发日成交量须比前一交易日成交量高至少三分之一：
     volume_T >= volume_{T-1} * (1 + 1/3)（等价于 volume_T * 3 >= volume_{T-1} * 4，且前一日成交量须 > 0）
2) 过滤（最近 10 个交易日约束）：
   - 在第 0 天之前最近 10 个交易日内，不存在任何一天满足 (high-open)/open >= 10%
3) 买入判定（第 1 天=T+1，后续回测复用）：
   - 低开至少 3%： (open_1 - prev_close_0) / prev_close_0 <= -3%
   - 买入点：第 1 天开盘（当前无分时数据，仅能以日线开盘价表达）
4) 卖出判定（第 2 天=T+2，后续回测复用）：
   - 无论如何，第 2 天开盘卖出（当前无分时数据，仅能以日线开盘价表达）

【关键口径与阈值】：
- 大涨： (high-open)/open >= 10%
- 回落： (high-close)/high >= 3%
- 放量： volume_T >= volume_{T-1} * (4/3)（实现上用 volume_T * 3 >= volume_{T-1} * 4）
- 低开： (open_1-prev_close_0)/prev_close_0 <= -3%

【边界与异常】：
- 数据缺失：若 open/high/close 任一为空，或触发日/前一日 volume 为空、或前一日 volume<=0，该日不可用于触发判定。
- 非交易日：策略本身以 trade_date 为准；定时任务层需判断交易日并跳过。
- 数据未同步：若 as_of_date 当日 K 线未落库，执行服务应返回“数据未就绪”而非给出误导结果。

【输出与可追溯性】：
- 执行快照：记录策略版本、as_of_date、阈值口径与假设（无分时数据、开盘口径）。
- 信号事件：至少记录 trigger 事件（触发日），并在 payload 中写入关键计算值与阈值；未来回测可在同口径下复现“当时为何触发”。
- 候选明细：输出并落库触发日候选列表（用于页面展示与审计）。

【示例】：
- 例 1（满足触发）：
  - T 日：open=10.00 high=11.20 close=10.80
    - (11.20-10.00)/10.00=12%（大涨满足）
    - (11.20-10.80)/11.20≈3.57%（回落满足）
  - 且 T 前 10 个交易日都没有出现 (high-open)/open>=10% 的大阳线
  - 且 T 日成交量 >= T-1 日成交量 * (4/3)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, func, literal, not_, or_, select

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
class _Thresholds:
    big_rise_pct: Decimal = Decimal("0.10")  # 10%
    pullback_pct: Decimal = Decimal("0.03")  # 3%
    gap_down_pct: Decimal = Decimal("-0.03")  # -3%
    lookback_trading_days: int = 10
    # 触发日成交量须比前一交易日高至少三分之一：volume_T >= volume_{T-1} * (1 + 1/3)
    volume_vs_prev_numerator: int = 4
    volume_vs_prev_denominator: int = 3
    # 首根大阳额外约束：前 10 个交易日不能出现“收盘涨幅超过 6%”
    # 口径：stock_daily_bar.pct_change（单位：百分比点，例如 6.50 表示 6.50%）
    lookback_max_pct_change: Decimal = Decimal("6.0")


class ChongGaoHuiLuoStrategy(StockStrategy):
    strategy_id = "chong_gao_hui_luo"
    version = "v1.1.3"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="冲高回落战法",
            version=self.version,
            short_description="筛选当日盘中强势拉升后回落的个股，形成今日候选列表。",
            description=(
                "本策略在 A 股日线数据上识别“开盘到最高涨幅≥10%，且当日从最高回落≥3%，"
                "且触发日成交量不低于前一交易日成交量 4/3 倍”的股票，"
                "并要求其在此前 10 个交易日内未出现同等强度的大阳线。输出为“今日符合冲高回落”的候选列表。"
            ),
            assumptions=[
                "当前无分时数据，涉及“开盘买入/卖出”的规则仅做口径记录，本期不计算真实成交。",
                "大涨口径采用 (high-open)/open；回落口径采用 (high-close)/high。",
                "放量口径：volume_T >= volume_{T-1} * (4/3)，前一日成交量须 > 0。",
                "首根约束：触发日前 10 个交易日内不得出现 (high-open)/open >= 10% 的大涨。",
            ],
            risks=[
                "策略基于历史日线形态筛选，不保证未来收益；极端行情下形态可能失真。",
                "数据缺失或复权口径变化会影响筛选结果，应以执行快照中的口径记录为准。",
            ],
            route_path="/strategy/chong-gao-hui-luo",
        )

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        thresholds = _Thresholds()
        db = SessionLocal()
        try:
            dd = as_of_date or get_latest_bar_date(db, "daily")
            if dd is None:
                # 由上层统一映射为“数据未就绪”
                raise RuntimeError("日线数据为空，无法执行冲高回落筛选")

            items, signals = self._select_stage1(db, dd, thresholds)
            return StrategyExecutionResult(
                as_of_date=dd,
                assumptions={
                    "market": "A股",
                    "timeframe": "daily",
                    "big_rise_def": "(high-open)/open >= 10%",
                    "pullback_def": "(high-close)/high >= 3%",
                    "volume_vs_prev_def": "volume_T >= volume_{T-1} * (4/3)",
                    "lookback_max_pct_change_def": "最近10个交易日前收涨幅不得超过6%（按 pct_change）",
                    "lookback_trading_days": thresholds.lookback_trading_days,
                    "no_intraday_data": True,
                },
                params={
                    "big_rise_pct": str(thresholds.big_rise_pct),
                    "pullback_pct": str(thresholds.pullback_pct),
                    "gap_down_pct": str(thresholds.gap_down_pct),
                    "volume_vs_prev": f"{thresholds.volume_vs_prev_numerator}/{thresholds.volume_vs_prev_denominator}",
                    "lookback_max_pct_change": str(thresholds.lookback_max_pct_change),
                },
                items=items,
                signals=signals,
            )
        finally:
            db.close()

    def backtest(self, *, start_date: date, end_date: date) -> BacktestResult:
        """历史回测：批量查询日线数据，逐日扫描触发→模拟 T+1 买入 / T+2 卖出。"""
        th = _Thresholds()
        db = SessionLocal()
        try:
            return self._run_backtest(db, start_date, end_date, th)
        finally:
            db.close()

    @staticmethod
    def _run_backtest(db, start_date: date, end_date: date, th: _Thresholds) -> BacktestResult:
        extended_start = start_date - timedelta(days=40)
        extended_end = end_date + timedelta(days=10)

        stmt = (
            select(
                StockDailyBar.stock_code,
                StockDailyBar.trade_date,
                StockDailyBar.open,
                StockDailyBar.high,
                StockDailyBar.close,
                StockDailyBar.volume,
                StockDailyBar.pct_change,
                StockDailyBar.ma5,
                StockDailyBar.ma10,
                StockDailyBar.ma20,
                StockDailyBar.ma60,
                StockDailyBar.macd_hist,
            )
            .where(StockDailyBar.trade_date.between(extended_start, extended_end))
            .order_by(StockDailyBar.stock_code, StockDailyBar.trade_date)
        )
        rows = db.execute(stmt).all()
        logger.info("回测数据加载完成: %d 条日线记录", len(rows))

        stock_info: dict[str, str | None] = dict(db.query(StockBasic.code, StockBasic.name).all())
        st_codes = {
            code for code, name in stock_info.items()
            if name and (name.startswith("ST") or name.startswith("*ST"))
        }

        stock_bars: dict[str, list] = defaultdict(list)
        for row in rows:
            if row.stock_code not in st_codes:
                stock_bars[row.stock_code].append(row)

        all_market_dates = sorted({row.trade_date for row in rows})
        market_next: dict[date, date] = {}
        market_next2: dict[date, date] = {}
        for i in range(len(all_market_dates) - 1):
            market_next[all_market_dates[i]] = all_market_dates[i + 1]
        for i in range(len(all_market_dates) - 2):
            market_next2[all_market_dates[i]] = all_market_dates[i + 2]

        trades: list[BacktestTrade] = []
        skipped = 0
        skip_reasons: list[str] = []
        big_rise_pct_f = float(th.big_rise_pct)
        pullback_pct_f = float(th.pullback_pct)
        gap_down_pct_f = float(th.gap_down_pct)
        lookback_max_pct_f = float(th.lookback_max_pct_change)

        for code, bars_list in stock_bars.items():
            stock_name = stock_info.get(code)
            date_idx = {b.trade_date: i for i, b in enumerate(bars_list)}

            for i, bar_t in enumerate(bars_list):
                trigger_date = bar_t.trade_date
                if trigger_date < start_date or trigger_date > end_date:
                    continue

                o, h, c = bar_t.open, bar_t.high, bar_t.close
                if not (o and h and c) or float(o) <= 0:
                    continue

                o_f, h_f, c_f = float(o), float(h), float(c)
                big_rise = (h_f - o_f) / o_f
                if big_rise < big_rise_pct_f:
                    continue
                pullback = (h_f - c_f) / h_f
                if pullback < pullback_pct_f:
                    continue
                if c_f < o_f:
                    continue
                if bar_t.pct_change is None or float(bar_t.pct_change) <= 0:
                    continue

                if i == 0:
                    continue
                bar_prev = bars_list[i - 1]
                if not (bar_t.volume and bar_prev.volume and float(bar_prev.volume) > 0):
                    continue
                if float(bar_t.volume) * th.volume_vs_prev_denominator < float(bar_prev.volume) * th.volume_vs_prev_numerator:
                    continue

                if not all([bar_t.ma5, bar_t.ma10, bar_t.ma20, bar_t.ma60]):
                    continue
                if not (float(bar_t.ma5) > float(bar_t.ma10) > float(bar_t.ma20) > float(bar_t.ma60)):
                    continue
                if bar_t.macd_hist is None or float(bar_t.macd_hist) <= 0:
                    continue

                has_conflict = False
                for j in range(max(0, i - th.lookback_trading_days), i):
                    lb = bars_list[j]
                    if lb.open and float(lb.open) > 0 and lb.high:
                        if (float(lb.high) - float(lb.open)) / float(lb.open) >= big_rise_pct_f:
                            has_conflict = True
                            break
                    if lb.pct_change is not None and float(lb.pct_change) > lookback_max_pct_f:
                        has_conflict = True
                        break
                if has_conflict:
                    continue

                t1_date = market_next.get(trigger_date)
                if t1_date is None:
                    skipped += 1
                    continue

                t1_idx = date_idx.get(t1_date)
                if t1_idx is None:
                    skipped += 1
                    if len(skip_reasons) < 100:
                        skip_reasons.append(f"{code} {trigger_date}: T+1 停牌")
                    continue

                bar_t1 = bars_list[t1_idx]
                if not (bar_t1.open and float(bar_t1.open) > 0):
                    skipped += 1
                    continue

                gap_down = (float(bar_t1.open) - c_f) / c_f
                if gap_down > gap_down_pct_f:
                    continue

                buy_date = t1_date
                buy_price = round(float(bar_t1.open), 4)
                extra = {
                    "trigger_date": trigger_date.isoformat(),
                    "surge_pct": round(big_rise, 4),
                    "pullback_pct": round(pullback, 4),
                }

                t2_date = market_next2.get(trigger_date)
                if t2_date is None or t2_date > end_date:
                    trades.append(BacktestTrade(
                        stock_code=code, stock_name=stock_name,
                        buy_date=buy_date, buy_price=buy_price,
                        trade_type="unclosed", extra=extra,
                    ))
                    continue

                t2_idx = date_idx.get(t2_date)
                if t2_idx is None:
                    skipped += 1
                    if len(skip_reasons) < 100:
                        skip_reasons.append(f"{code} {trigger_date}: T+2 停牌")
                    continue

                bar_t2 = bars_list[t2_idx]
                if not (bar_t2.open and float(bar_t2.open) > 0):
                    skipped += 1
                    continue

                sell_price = round(float(bar_t2.open), 4)
                return_rate = round((sell_price - buy_price) / buy_price, 4)

                trades.append(BacktestTrade(
                    stock_code=code, stock_name=stock_name,
                    buy_date=buy_date, buy_price=buy_price,
                    sell_date=t2_date, sell_price=sell_price,
                    return_rate=return_rate, trade_type="closed", extra=extra,
                ))

        logger.info("回测扫描完成: trades=%d, skipped=%d", len(trades), skipped)
        return BacktestResult(trades=trades, skipped_count=skipped, skip_reasons=skip_reasons)

    @staticmethod
    def _select_stage1(db, as_of_date: date, th: _Thresholds) -> tuple[list[StrategyCandidate], list[StrategySignal]]:
        """
        选出“今日符合冲高回落”的候选集合。

        实现要点：
        - 用窗口函数按 stock_code 倒序编号，定位：
          - rn=1：as_of_date 当日 bar（第 0 天）
          - rn=2..11：此前 10 个交易日 bar（过滤用）
        """

        # 避免除 0；open<=0 视为不可用
        valid_open = and_(StockDailyBar.open.isnot(None), StockDailyBar.open > 0)
        valid_high = StockDailyBar.high.isnot(None)
        valid_close = StockDailyBar.close.isnot(None)

        # 注意：均线多头排列与 MACD 红柱是“触发日当天”的约束，不能用于过滤回看窗口，
        # 否则会把“昨天的大阳线”错误排除出 lookback，从而误判“今天是首根大阳线”。
        def _ma_bull_ok_on_curr(curr_cte: Any) -> Any:
            return and_(
                curr_cte.c.ma5.isnot(None),
                curr_cte.c.ma10.isnot(None),
                curr_cte.c.ma20.isnot(None),
                curr_cte.c.ma60.isnot(None),
                curr_cte.c.ma5 > curr_cte.c.ma10,
                curr_cte.c.ma10 > curr_cte.c.ma20,
                curr_cte.c.ma20 > curr_cte.c.ma60,
            )

        def _macd_red_ok_on_curr(curr_cte: Any) -> Any:
            return and_(curr_cte.c.macd_hist.isnot(None), curr_cte.c.macd_hist > 0)

        big_rise_expr = (StockDailyBar.high - StockDailyBar.open) / StockDailyBar.open
        pullback_expr = (StockDailyBar.high - StockDailyBar.close) / StockDailyBar.high

        rn = func.row_number().over(partition_by=StockDailyBar.stock_code, order_by=StockDailyBar.trade_date.desc())

        base = (
            select(
                StockDailyBar.stock_code.label("stock_code"),
                StockDailyBar.trade_date.label("trade_date"),
                StockDailyBar.open.label("open"),
                StockDailyBar.high.label("high"),
                StockDailyBar.close.label("close"),
                StockDailyBar.pct_change.label("pct_change"),
                StockDailyBar.volume.label("volume"),
                StockDailyBar.ma5.label("ma5"),
                StockDailyBar.ma10.label("ma10"),
                StockDailyBar.ma20.label("ma20"),
                StockDailyBar.ma60.label("ma60"),
                StockDailyBar.macd_hist.label("macd_hist"),
                big_rise_expr.label("big_rise"),
                pullback_expr.label("pullback"),
                rn.label("rn"),
            )
            .where(StockDailyBar.trade_date <= as_of_date)
            # base 仅做“数据可用性”过滤，避免影响 lookback 窗口判定
            .where(valid_open, valid_high, valid_close)
        ).cte("bars")

        curr = select(base).where(base.c.rn == 1).cte("curr")
        # 前一交易日 K 线（rn=2），用于放量对比
        prev = select(base).where(base.c.rn == 2).cte("prev")
        lookback = (
            select(
                base.c.stock_code,
                # 最近 10 个交易日是否出现过大阳线（按 big_rise 口径）
                func.max(case((base.c.big_rise >= th.big_rise_pct, 1), else_=0)).label("has_big"),
                # 最近 10 个交易日是否出现过“收盘涨幅 > 6%”
                func.max(
                    case(
                        (
                            and_(
                                base.c.pct_change.isnot(None),
                                base.c.pct_change > th.lookback_max_pct_change,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("has_gt_6"),
            )
            .where(and_(base.c.rn >= 2, base.c.rn <= th.lookback_trading_days + 1))
            .group_by(base.c.stock_code)
            .cte("lb")
        )

        # 放量：volume_T * denom >= volume_{T-1} * numer  （即 volume_T >= volume_{T-1} * numer/denom）
        vol_ok = and_(
            curr.c.volume.isnot(None),
            prev.c.volume.isnot(None),
            prev.c.volume > 0,
            curr.c.volume * th.volume_vs_prev_denominator >= prev.c.volume * th.volume_vs_prev_numerator,
        )

        # 仅保留：当日满足触发 + 回落 + 放量；且 lookback 没有大阳
        q = (
            select(
                curr.c.stock_code,
                StockBasic.name.label("stock_name"),
                func.coalesce(StockBasic.exchange, StockBasic.market).label("exchange_type"),
                literal(as_of_date).label("trigger_date"),
                curr.c.open,
                curr.c.high,
                curr.c.close,
                curr.c.volume,
                prev.c.volume.label("prev_volume"),
                curr.c.big_rise,
                curr.c.pullback,
                curr.c.ma5,
                curr.c.ma10,
                curr.c.ma20,
                curr.c.ma60,
                curr.c.macd_hist,
            )
            .select_from(curr)
            .join(prev, prev.c.stock_code == curr.c.stock_code)
            .join(StockBasic, StockBasic.code == curr.c.stock_code)
            .outerjoin(lookback, lookback.c.stock_code == curr.c.stock_code)
            # 过滤 ST：stock_basic 目前无 is_st 字段，按名称前缀过滤（ST* / *ST*）
            .where(
                not_(
                    or_(
                        StockBasic.name.like("ST%"),
                        StockBasic.name.like("*ST%"),
                    )
                )
            )
            .where(curr.c.big_rise >= th.big_rise_pct)
            .where(curr.c.pullback >= th.pullback_pct)
            .where(vol_ok)
            .where(_ma_bull_ok_on_curr(curr))
            .where(_macd_red_ok_on_curr(curr))
            # 大阳线必须是“阳线”：避免出现“盘中冲高但收盘大跌的阴线”被误纳入
            .where(curr.c.close >= curr.c.open)
            # 同时要求收盘涨幅为正（与“阴线/大跌”直觉一致）
            .where(curr.c.pct_change.isnot(None), curr.c.pct_change > 0)
            .where(func.coalesce(lookback.c.has_big, 0) == 0)
            .where(func.coalesce(lookback.c.has_gt_6, 0) == 0)
            .order_by(curr.c.stock_code)
        )

        rows = db.execute(q).all()

        items: list[StrategyCandidate] = []
        signals: list[StrategySignal] = []
        for r in rows:
            big_rise_pct = float(r.big_rise) if r.big_rise is not None else None
            pullback_pct = float(r.pullback) if r.pullback is not None else None
            vol = float(r.volume) if getattr(r, "volume", None) is not None else None
            prev_vol = float(r.prev_volume) if getattr(r, "prev_volume", None) is not None else None
            macd_hist = float(r.macd_hist) if getattr(r, "macd_hist", None) is not None else None
            summary: dict[str, Any] = {
                "open": str(r.open) if r.open is not None else None,
                "high": str(r.high) if r.high is not None else None,
                "close": str(r.close) if r.close is not None else None,
                "pct_change": float(r.pct_change) if getattr(r, "pct_change", None) is not None else None,
                "volume": vol,
                "prev_volume": prev_vol,
                "volume_vs_prev_ratio": (vol / prev_vol) if vol is not None and prev_vol else None,
                "big_rise_ratio": big_rise_pct,
                "pullback_ratio": pullback_pct,
                "ma5": str(r.ma5) if getattr(r, "ma5", None) is not None else None,
                "ma10": str(r.ma10) if getattr(r, "ma10", None) is not None else None,
                "ma20": str(r.ma20) if getattr(r, "ma20", None) is not None else None,
                "ma60": str(r.ma60) if getattr(r, "ma60", None) is not None else None,
                "macd_hist": macd_hist,
                "big_rise_threshold": float(th.big_rise_pct),
                "pullback_threshold": float(th.pullback_pct),
                "volume_vs_prev_rule": f">= {th.volume_vs_prev_numerator}/{th.volume_vs_prev_denominator} 倍前一日",
                "lookback_max_pct_change_rule": f"最近{th.lookback_trading_days}个交易日前收涨幅不得超过{th.lookback_max_pct_change}%",
            }
            items.append(
                StrategyCandidate(
                    stock_code=r.stock_code,
                    stock_name=r.stock_name,
                    exchange_type=r.exchange_type,
                    trigger_date=as_of_date,
                    summary=summary,
                )
            )
            signals.append(
                StrategySignal(
                    stock_code=r.stock_code,
                    event_date=as_of_date,
                    event_type="trigger",
                    payload={
                        "strategy": "chong_gao_hui_luo",
                        "as_of_date": as_of_date.isoformat(),
                        "computed": {
                            "big_rise_ratio": big_rise_pct,
                            "pullback_ratio": pullback_pct,
                            "volume": vol,
                            "prev_volume": prev_vol,
                            "macd_hist": macd_hist,
                            "pct_change": float(r.pct_change) if getattr(r, "pct_change", None) is not None else None,
                        },
                        "thresholds": {
                            "big_rise_ratio": float(th.big_rise_pct),
                            "pullback_ratio": float(th.pullback_pct),
                            "volume_vs_prev": f">= {th.volume_vs_prev_numerator}/{th.volume_vs_prev_denominator}",
                            "ma_bull": "MA5>MA10>MA20>MA60",
                            "macd_red": "macd_hist > 0",
                            "lookback_max_pct_change": f"pct_change <= {th.lookback_max_pct_change}%",
                            "yang_xian": "close >= open 且 pct_change > 0",
                        },
                        "notes": [
                            "当前无分时数据，买入/卖出规则仅记录口径，未计算成交。",
                            "后续回测可在同口径下复现触发原因。",
                        ],
                    },
                )
            )

        # 记录一次全局 note，便于回放了解本次执行的整体口径（按 execution_snapshot 也会记录）
        signals.append(
            StrategySignal(
                stock_code="__GLOBAL__",
                event_date=as_of_date,
                event_type="note",
                payload={
                    "assumptions": {
                        "big_rise_def": "(high-open)/open >= 10%",
                        "pullback_def": "(high-close)/high >= 3%",
                        "volume_vs_prev_def": "volume_T >= volume_{T-1} * (4/3)",
                        "lookback_trading_days": th.lookback_trading_days,
                    }
                },
            )
        )

        return items, signals

