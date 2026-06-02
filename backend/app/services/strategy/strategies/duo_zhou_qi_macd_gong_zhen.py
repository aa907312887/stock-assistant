"""
多周期 MACD 共振主升浪（内置策略，`strategy_id`=`duo_zhou_qi_macd_gong_zhen`）。

【策略名称】：多周期 MACD 共振主升浪

【目标】：在日/周/月 MACD 同为红柱、日线经历绿转红后 **6 根严格递增红柱** 且涨幅达标时，
于 **D6 收盘**买入；持仓后按 **止损 / 无条件卖出 / 移动止盈** 规则收盘平仓。

【适用范围】：
- 市场：A 股**主板**（`stock_basic.market == "主板"`），**不买**创业板、科创板；剔除 **ST / *ST**。
- 数据粒度：日线触发；周/月线仅用于买入日共振（`macd_hist` 预计算字段）。
- 依赖字段：日线 `open`、`close`、`macd_hist`；周线 `trade_week_end`、`macd_hist`；
  月线 `trade_month_end`、`macd_hist`。

【核心规则】：
1) **买入**：D0 绿 → D1…D6 红柱且 hist 严格递增；`close(D6) ≥ open(D1)×(1+10%)`；
   买入日周/月最近 bar 的 `macd_hist` 均 >0；**D6 收盘价**买入。
2) **止损**：收盘 ≤ 买入价×93%（仅亏损侧）。
3) **无条件卖出**：日线 MACD 红转绿、或连续 3 日收跌 —— **不论盈亏**（含盈利未满 10%）。
4) **移动止盈**：收盘曾 ≥ 买入价×110% 后，自武装后最高收盘价回撤 3% 收盘卖。

【边界】：缺周/月 MACD 或 OHLC 无效则跳过；单标的未平仓前不重复开仓；D6 无收盘不顺延。

【输出】：回测 `trigger_date=buy_date=D6`；`extra.exit_reason` 区分四类离场。

【示例】：
- 买入后收盘 +5% 但 MACD 红转绿 → 当日收盘卖（`sell_macd_red_to_green`），不等待 +10%。
- 买入后曾 +12%，随后收盘从峰值回撤 3% → `trailing_take_profit_3pct`。
"""

from __future__ import annotations

import bisect
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select

from app.database import SessionLocal
from app.models import StockBasic, StockDailyBar, StockMonthlyBar, StockWeeklyBar
from app.services.screening_service import get_latest_bar_date
from app.services.strategy.strategy_base import (
    BacktestResult,
    BacktestTrade,
    StockStrategy,
    StrategyDescriptor,
    StrategyExecutionResult,
)

logger = logging.getLogger(__name__)

STRATEGY_ID = "duo_zhou_qi_macd_gong_zhen"


@dataclass(frozen=True)
class _Params:
    gain_filter_pct: float = 0.10
    arm_profit_pct: float = 0.10
    trailing_drawdown_pct: float = 0.03
    stop_loss_pct: float = 0.07


def _hist_val(bar: Any) -> float | None:
    h = getattr(bar, "macd_hist", None)
    if h is None:
        return None
    try:
        v = float(h)
    except (TypeError, ValueError):
        return None
    return v


def _is_red(hist: float | None) -> bool:
    return hist is not None and hist > 0


def _is_green(hist: float | None) -> bool:
    return hist is not None and hist <= 0


def six_increasing_red_ends_at(bars_list: list[Any], i: int) -> bool:
    """
    下标 i 为 D6：D0=i-6 须为绿柱，D1…D6 为红柱且 macd_hist 严格递增。
    """
    if i < 6:
        return False
    h0 = _hist_val(bars_list[i - 6])
    if not _is_green(h0):
        return False
    prev_hist = h0
    for k in range(i - 5, i + 1):
        hk = _hist_val(bars_list[k])
        if not _is_red(hk):
            return False
        assert hk is not None
        if hk <= prev_hist:
            return False
        prev_hist = hk
    return True


def gain_filter_ok(bars_list: list[Any], i: int, *, gain_filter_pct: float) -> bool:
    """close(D6) >= open(D1) * (1 + gain_filter_pct)。"""
    d1 = bars_list[i - 5]
    d6 = bars_list[i]
    if d1.open is None or d6.close is None:
        return False
    o1 = float(d1.open)
    c6 = float(d6.close)
    if o1 <= 0:
        return False
    return c6 >= o1 * (1.0 + gain_filter_pct) - 1e-9


def _build_period_hist_index(
    rows: list[Any],
    *,
    end_attr: str,
) -> dict[str, list[tuple[date, float]]]:
    """按 stock_code 分组，(周期末端, macd_hist) 按日期升序。"""
    out: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for row in rows:
        code = row.stock_code
        end_d = getattr(row, end_attr)
        h = _hist_val(row)
        if end_d is None or h is None:
            continue
        out[code].append((end_d, h))
    for code in out:
        out[code].sort(key=lambda x: x[0])
    return out


def _latest_period_entry(
    series: list[tuple[date, float]], as_of: date
) -> tuple[date, float] | None:
    if not series:
        return None
    ends = [t[0] for t in series]
    idx = bisect.bisect_right(ends, as_of) - 1
    if idx < 0:
        return None
    return series[idx]


def latest_hist_leq(series: list[tuple[date, float]], as_of: date) -> float | None:
    entry = _latest_period_entry(series, as_of)
    return entry[1] if entry else None


def multi_tf_macd_red(
    weekly_by_code: dict[str, list[tuple[date, float]]],
    monthly_by_code: dict[str, list[tuple[date, float]]],
    code: str,
    as_of: date,
) -> bool:
    wh = latest_hist_leq(weekly_by_code.get(code, []), as_of)
    mh = latest_hist_leq(monthly_by_code.get(code, []), as_of)
    return _is_red(wh) and _is_red(mh)


def simulate_exit_after_buy(
    bars_list: list[Any],
    buy_idx: int,
    buy_price: float,
    end_date: date,
    p: _Params,
) -> tuple[int | None, float | None, str | None]:
    """
    自 buy_idx+1 起按收盘价监测；顺序：7% 止损 → 红转绿 → 三连跌 → 移动止盈。
    红转绿/三连跌不检查盈亏。
    """
    trailing_armed = False
    peak_close: float | None = None
    down_streak = 0
    buy_bar = bars_list[buy_idx]
    if buy_bar.close is None:
        prev_close = buy_price
    else:
        prev_close = float(buy_bar.close)

    for k in range(buy_idx + 1, len(bars_list)):
        bk = bars_list[k]
        if bk.trade_date > end_date:
            break
        if bk.close is None:
            continue
        ck = float(bk.close)

        if ck <= buy_price * (1.0 - p.stop_loss_pct):
            return k, ck, "stop_loss_7pct"

        h_prev = _hist_val(bars_list[k - 1])
        h_cur = _hist_val(bk)
        if _is_red(h_prev) and _is_green(h_cur):
            return k, ck, "sell_macd_red_to_green"

        if ck < prev_close:
            down_streak += 1
        else:
            down_streak = 0
        if down_streak >= 3:
            return k, ck, "sell_three_down_days"
        prev_close = ck

        if ck >= buy_price * (1.0 + p.arm_profit_pct):
            trailing_armed = True
        if trailing_armed:
            peak_close = ck if peak_close is None else max(peak_close, ck)
            if ck <= peak_close * (1.0 - p.trailing_drawdown_pct):
                return k, ck, "trailing_take_profit_3pct"

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
            StockDailyBar.open,
            StockDailyBar.close,
            StockDailyBar.macd_hist,
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


def run_duo_zhou_qi_macd_gong_zhen_backtest(
    db: Any,
    *,
    start_date: date,
    end_date: date,
    p: _Params,
) -> BacktestResult:
    extended_start = start_date - timedelta(days=40)
    extended_end = end_date + timedelta(days=400)

    stock_info, stock_bars = _load_daily_bars_grouped(
        db, extended_start=extended_start, extended_end=extended_end
    )

    w_rows = db.execute(
        select(
            StockWeeklyBar.stock_code,
            StockWeeklyBar.trade_week_end,
            StockWeeklyBar.macd_hist,
        ).where(
            StockWeeklyBar.trade_week_end.between(extended_start, extended_end),
        )
    ).all()
    m_rows = db.execute(
        select(
            StockMonthlyBar.stock_code,
            StockMonthlyBar.trade_month_end,
            StockMonthlyBar.macd_hist,
        ).where(
            StockMonthlyBar.trade_month_end.between(extended_start, extended_end),
        )
    ).all()
    weekly_by_code = _build_period_hist_index(w_rows, end_attr="trade_week_end")
    monthly_by_code = _build_period_hist_index(m_rows, end_attr="trade_month_end")

    trades: list[BacktestTrade] = []
    skipped = 0
    for code, bars_list in stock_bars.items():
        if len(bars_list) < 7:
            skipped += 1
            continue
        stock_name = stock_info.get(code)
        last_block = -1
        for i in range(6, len(bars_list)):
            if i <= last_block:
                continue
            if not six_increasing_red_ends_at(bars_list, i):
                continue
            if not gain_filter_ok(bars_list, i, gain_filter_pct=p.gain_filter_pct):
                continue
            sig_bar = bars_list[i]
            if sig_bar.close is None or float(sig_bar.close) <= 0:
                continue
            if not _is_red(_hist_val(sig_bar)):
                continue
            t_buy = sig_bar.trade_date
            if t_buy < start_date or t_buy > end_date:
                continue
            if not multi_tf_macd_red(weekly_by_code, monthly_by_code, code, t_buy):
                continue

            buy_price = round(float(sig_bar.close), 4)
            buy_date = t_buy
            trigger_date = t_buy
            d1_bar = bars_list[i - 5]
            d1_open = float(d1_bar.open) if d1_bar.open is not None else None
            gain_pct = (
                round((buy_price - d1_open) / d1_open, 6) if d1_open and d1_open > 0 else None
            )

            w_entry = _latest_period_entry(weekly_by_code.get(code, []), t_buy)
            m_entry = _latest_period_entry(monthly_by_code.get(code, []), t_buy)

            extra_base: dict[str, Any] = {
                "buy_rule": "d6_close",
                "sell_rule": "close_triggered_multi_exit",
                "d1_date": d1_bar.trade_date.isoformat(),
                "d1_open": d1_open,
                "gain_filter_pct": gain_pct,
                "macd_hist_d6": _hist_val(sig_bar),
                "weekly_bar_end": w_entry[0].isoformat() if w_entry else None,
                "monthly_bar_end": m_entry[0].isoformat() if m_entry else None,
            }

            sell_j, sell_px, exit_reason = simulate_exit_after_buy(
                bars_list, i, buy_price, end_date, p
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
            trailing_armed = exit_reason == "trailing_take_profit_3pct"
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
                    extra={
                        **extra_base,
                        "exit_reason": exit_reason,
                        "trailing_armed": trailing_armed,
                    },
                ),
            )
            last_block = sell_j

    logger.info("%s 回测完成: trades=%d skipped_short=%d", STRATEGY_ID, len(trades), skipped)
    return BacktestResult(trades=trades, skipped_count=skipped, skip_reasons=[])


class DuoZhouQiMacdGongZhenStrategy(StockStrategy):
    """多周期 MACD 共振主升浪策略入口。"""

    strategy_id = STRATEGY_ID
    version = "v1.0.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="多周期 MACD 共振主升浪",
            version=self.version,
            short_description=(
                "主板；日周月MACD红柱共振；6日递增红柱；D6收盘买入；"
                "红转绿/三连跌不论盈亏即卖；+10%后3%移动止盈；7%亏损止损。"
            ),
            description=(
                "**股票范围**：仅 **主板**（`stock_basic.market == \"主板\"`），不买创业板、科创板；剔除 ST/*ST。\n"
                "**买入**：日线 D0 绿 → D1…D6 红柱且 MACD 柱严格递增；"
                "买入日周/月最近 bar 亦为红柱；`close(D6) ≥ open(D1)×110%`；**D6 收盘价**买入。\n"
                "**卖出**：① 收盘亏满 7% 止损；② 日线 MACD 红转绿 —— **不论盈亏**（含盈利未满 10%）；"
                "③ 连续 3 日收跌 —— **不论盈亏**；④ 浮盈曾 ≥10% 后，自武装后最高收盘价回撤 3% 移动止盈。\n"
                "监测与成交均为**收盘价**。不构成投资建议。"
            ),
            assumptions=[
                "日/周/月 macd_hist 已预计算；红柱为 hist>0。",
                "回测仅扫描 stock_basic.market 为「主板」的标的，不含创业板、科创板。",
                "买入日 trigger_date 与 buy_date 均为 D6。",
                "红转绿、三连跌为无条件卖出，不因浮盈而豁免。",
                "同区间重复回测结果可复现。",
            ],
            risks=[
                "周/月 MACD 未回填的标的不会触发买入。",
                "六日递增红柱窗口固定以 D6 为末端，不向左滑动 D1。",
            ],
            route_path="/backtest/history",
        )

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        db = SessionLocal()
        try:
            dd = as_of_date or get_latest_bar_date(db, "daily")
            if dd is None:
                raise RuntimeError(f"日线数据为空，无法执行 {STRATEGY_ID}")
            return StrategyExecutionResult(
                as_of_date=dd,
                assumptions={
                    "note": "本期仅支持历史回测；策略选股尚未开放",
                    "data_granularity": "日线",
                },
                params={
                    "gain_filter_pct": _Params().gain_filter_pct,
                    "arm_profit_pct": _Params().arm_profit_pct,
                    "trailing_drawdown_pct": _Params().trailing_drawdown_pct,
                    "stop_loss_pct": _Params().stop_loss_pct,
                },
                items=[],
                signals=[],
            )
        finally:
            db.close()

    def backtest(self, *, start_date: date, end_date: date) -> BacktestResult:
        p = _Params()
        db = SessionLocal()
        try:
            return run_duo_zhou_qi_macd_gong_zhen_backtest(
                db, start_date=start_date, end_date=end_date, p=p
            )
        finally:
            db.close()
