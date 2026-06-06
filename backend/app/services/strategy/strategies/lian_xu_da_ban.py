"""
连续打板（内置策略，`strategy_id`=`lian_xu_da_ban`）。

【策略名称】：连续打板

【目标】：在日线 MACD **绿转红**后 **3 个交易日内**出现**连续 2 次涨停**时，
于**第二次涨停日收盘**买入（打二板）；持仓后按 **最高价回落 5%** 或 **MACD 红转绿**（满足其一即收盘平仓）。

【适用范围】：
- 市场：A 股**主板**（`stock_basic.market == "主板"`），**不买**创业板、科创板；剔除 **ST / *ST**。
- 数据粒度：日线。
- 依赖字段：日线 `close`、`prev_close`、`macd_hist`。

【核心规则】：
1) **买入**：存在绿转红日 **G**（G−1 绿、G 红）；**T_buy−1** 与 **T_buy** 均为涨停；
   **T_buy − G ≤ 2**（3 日窗口）；**不要求**周/月 MACD 红柱；**T_buy 收盘价**买入。
2) **离场（或关系）**：① 持仓期最高收盘价回落 **≥5%** 当日收盘卖（兼作止盈/止损）；
   ② 日线 MACD **红转绿**（前日红柱、当日绿柱）当日收盘卖。

【关键口径与阈值】：
- **首板涨停**：涨幅 **≥ 10%**（`pct_change` 百分比点或 `close/prev_close`）。
- **续板涨停**（二板及以后）：涨幅 **> 9.5%**。
- 绿转红：前一日 `macd_hist ≤ 0`，当日 `macd_hist > 0`。
- 3 日窗口：自 G 起 G、G+1、G+2 三个交易日，T_buy 须落在此窗口内。

【边界与异常】：
- 缺 `macd_hist`、OHLC 或 prev_close 无效则跳过；单标的未平仓前不重复开仓；T_buy 无收盘不顺延。

【输出与可追溯性】：
- 回测 `trigger_date=buy_date=T_buy`；`extra` 含绿转红日、二连板日期、离场原因。
- 选股 `execute`：`summary` 含 `first_limit_up`、`pct_change`、`close`；**不**判断二板。

【示例】：
- G 日绿转红；G+1 首板、G+2 二板 → G+2 收盘买入。
- G 日绿转红且首板；G+1 二板 → G+1 收盘买入。
- 买入后最高收盘 120，当日收 114（回落 5%）→ 收盘卖；或 MACD 红转绿当日卖。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import StockBasic, StockDailyBar
from app.services.strategy.strategies.chun_zheng_ma_duotou import (
    _load_stock_exchanges,
    _load_stock_names,
)
from app.services.strategy.strategies.duo_zhou_qi_macd_gong_zhen import (
    _hist_val,
    _is_green,
    _is_red,
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

STRATEGY_ID = "lian_xu_da_ban"

# 首板：涨幅须达 10%（主板涨停价口径）；续板：涨幅 > 9.5%
_FIRST_BOARD_MIN_PCT_POINTS = 10.0
_FIRST_BOARD_MIN_RATIO = 0.10
_FIRST_BOARD_CLOSE_EPS = 0.001

_FOLLOW_BOARD_MIN_PCT_POINTS = 9.5
_FOLLOW_BOARD_MIN_RATIO = 0.095


@dataclass(frozen=True)
class _Params:
    trailing_drawdown_pct: float = 0.05  # 自持仓期最高收盘价回落 5%
    green_to_red_window_days: int = 2  # T_buy - G <= 2 → 3 日窗口


def _prev_close_val(bar: Any) -> float | None:
    pc = getattr(bar, "prev_close", None)
    if pc is None:
        return None
    try:
        v = float(pc)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _pct_change_points(bar: Any) -> float | None:
    """涨跌幅百分比点（如 9.51 表示 9.51%）。"""
    pct = getattr(bar, "pct_change", None)
    if pct is None:
        return None
    try:
        return float(pct)
    except (TypeError, ValueError):
        return None


def _daily_gain_pct_and_ratio(bar: Any) -> tuple[float | None, float | None]:
    """返回 (涨跌幅百分比点, 小数涨幅)；优先库表 pct_change，否则用 close/prev_close。"""
    pct_pts = _pct_change_points(bar)
    ratio: float | None = None
    if bar.close is not None:
        pc = _prev_close_val(bar)
        if pc is not None:
            try:
                c = float(bar.close)
                if c > 0:
                    ratio = (c - pc) / pc
            except (TypeError, ValueError):
                pass
    if pct_pts is None and ratio is not None:
        pct_pts = ratio * 100.0
    elif ratio is None and pct_pts is not None:
        ratio = pct_pts / 100.0
    return pct_pts, ratio


def is_limit_up_first_board(bar: Any) -> bool:
    """
    首板涨停：涨幅 **≥ 10%**。
    优先 `pct_change`（百分比点）；否则 `close ≥ prev_close × (1+10%) − ε`。
    """
    pct_pts, ratio = _daily_gain_pct_and_ratio(bar)
    if pct_pts is not None:
        return pct_pts >= _FIRST_BOARD_MIN_PCT_POINTS
    if ratio is not None:
        return ratio >= _FIRST_BOARD_MIN_RATIO - 1e-9
    if bar.close is None:
        return False
    pc = _prev_close_val(bar)
    if pc is None:
        return False
    try:
        c = float(bar.close)
    except (TypeError, ValueError):
        return False
    if c <= 0:
        return False
    return c >= pc * (1.0 + _FIRST_BOARD_MIN_RATIO) - _FIRST_BOARD_CLOSE_EPS


def is_limit_up_follow_board(bar: Any) -> bool:
    """
    续板涨停（二板及以后）：涨幅 **> 9.5%**。
    """
    pct_pts, ratio = _daily_gain_pct_and_ratio(bar)
    if pct_pts is not None:
        return pct_pts > _FOLLOW_BOARD_MIN_PCT_POINTS
    if ratio is not None:
        return ratio > _FOLLOW_BOARD_MIN_RATIO
    return False


def is_limit_up_day(bar: Any) -> bool:
    """当日是否计为涨停（首板达标或续板达标）。"""
    return is_limit_up_first_board(bar) or is_limit_up_follow_board(bar)


def is_macd_green_to_red_day(prev_bar: Any, cur_bar: Any) -> bool:
    """前一交易日绿柱、当日红柱（`macd_hist` 口径）。"""
    return _is_green(_hist_val(prev_bar)) and _is_red(_hist_val(cur_bar))


def is_macd_red_to_green_day(prev_bar: Any, cur_bar: Any) -> bool:
    """前一交易日红柱、当日绿柱（`macd_hist` 口径）——卖出信号。"""
    return _is_red(_hist_val(prev_bar)) and _is_green(_hist_val(cur_bar))


def is_green_to_red(bars_list: list[Any], idx: int) -> bool:
    """下标 idx 为绿转红日：idx−1 绿柱，idx 红柱。"""
    if idx < 1:
        return False
    return is_macd_green_to_red_day(bars_list[idx - 1], bars_list[idx])


def is_first_board_pick(prev_bar: Any | None, today_bar: Any) -> bool:
    """
    策略选股：截止日同时满足 MACD 绿转红 + 当日为**首板**涨停。

    首板口径：当日涨停，且**前一交易日非涨停**（排除二板、三连板等）。
    典型漏网场景（须排除）：昨首板且 MACD 仍为绿柱，今二板日 MACD 绿转红——
    若不校验昨涨停，会误把二板当选股结果。
    """
    if prev_bar is None:
        return False
    if not is_macd_green_to_red_day(prev_bar, today_bar):
        return False
    if not is_limit_up_first_board(today_bar):
        return False
    # 前一交易日已涨停（首板或续板）→ 当日为连板，非首板
    if is_limit_up_day(prev_bar):
        return False
    return True


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _load_main_board_non_st_codes(db: Any) -> set[str]:
    basics = db.execute(select(StockBasic.code, StockBasic.name, StockBasic.market)).all()
    codes: set[str] = set()
    for row in basics:
        if row.market != "主板":
            continue
        name = row.name or ""
        if name.startswith("ST") or name.startswith("*ST"):
            continue
        codes.add(row.code)
    return codes


def run_lian_xu_da_ban_execute(db: Any, *, as_of_date: date) -> StrategyExecutionResult:
    """全市场扫描：截止日 MACD 绿转红且当日首板涨停。"""
    prev_date = db.scalar(
        select(func.max(StockDailyBar.trade_date)).where(StockDailyBar.trade_date < as_of_date)
    )
    if prev_date is None:
        return StrategyExecutionResult(
            as_of_date=as_of_date,
            assumptions={"note": "无前一交易日日线，无法判定绿转红"},
            params={},
            items=[],
            signals=[],
        )

    universe = _load_main_board_non_st_codes(db)
    names = _load_stock_names(db)
    exchanges = _load_stock_exchanges(db)

    today_rows = list(
        db.execute(
            select(StockDailyBar).where(
                StockDailyBar.trade_date == as_of_date,
                StockDailyBar.stock_code.in_(universe),
            )
        ).scalars().all()
    )
    prev_rows = list(
        db.execute(
            select(StockDailyBar).where(
                StockDailyBar.trade_date == prev_date,
                StockDailyBar.stock_code.in_(universe),
            )
        ).scalars().all()
    )
    prev_by_code = {r.stock_code: r for r in prev_rows}

    items: list[StrategyCandidate] = []
    signals: list[StrategySignal] = []
    for bar in today_rows:
        prev_bar = prev_by_code.get(bar.stock_code)
        if not is_first_board_pick(prev_bar, bar):
            continue
        pct = _to_float(bar.pct_change)
        close_px = _to_float(bar.close)
        items.append(
            StrategyCandidate(
                stock_code=bar.stock_code,
                stock_name=names.get(bar.stock_code),
                exchange_type=exchanges.get(bar.stock_code),
                trigger_date=as_of_date,
                summary={
                    "macd_green_to_red": True,
                    "first_limit_up": True,
                    "pct_change": pct,
                    "close": close_px,
                    "prev_trade_date": prev_date.isoformat(),
                },
            )
        )
        signals.append(
            StrategySignal(
                stock_code=bar.stock_code,
                event_date=as_of_date,
                event_type="trigger",
                payload={
                    "signal_kind": "first_board_green_to_red",
                    "first_limit_up": True,
                    "pct_change": pct,
                },
            )
        )

    items.sort(key=lambda x: x.stock_code)
    logger.info(
        "%s 选股: as_of=%s 扫描=%d 入选=%d",
        STRATEGY_ID,
        as_of_date,
        len(today_rows),
        len(items),
    )
    return StrategyExecutionResult(
        as_of_date=as_of_date,
        assumptions={
            "data_granularity": "日线",
            "stock_universe": "主板(排除ST)",
            "filter": "as_of MACD green-to-red + first limit-up; no second board check",
        },
        params={
            "macd": "prev hist<=0, today hist>0",
            "first_board_limit_up": "pct_change >= 10 or close >= prev_close * 110%",
            "follow_board_limit_up": "pct_change > 9.5 or gain ratio > 0.095",
            "first_board_pick": "green-to-red + first_board_limit_up + prev not limit_up_day",
            "second_board": "not evaluated in execute",
        },
        items=items,
        signals=signals,
    )


def find_green_to_red_for_second_board(
    bars_list: list[Any],
    buy_idx: int,
    *,
    window_days: int,
) -> int | None:
    """
    buy_idx 为第二次涨停日（T_buy）。
    在 [buy_idx − window_days, buy_idx] 内寻找绿转红日 G，使 T_buy − G ≤ window_days。
    若多个 G 满足，取**最近**的绿转红日（最大下标）。
    """
    if buy_idx < 1:
        return None
    start = max(1, buy_idx - window_days)
    found: int | None = None
    for g in range(start, buy_idx + 1):
        if is_green_to_red(bars_list, g):
            found = g
    return found


def is_second_consecutive_limit_up(bars_list: list[Any], buy_idx: int) -> bool:
    """
    连续二板：buy_idx−1 为**首板**（≥10%），buy_idx 为**续板**（>9.5%）。
    """
    if buy_idx < 1:
        return False
    first_bar = bars_list[buy_idx - 1]
    second_bar = bars_list[buy_idx]
    return is_limit_up_first_board(first_bar) and is_limit_up_follow_board(second_bar)


def buy_signal_at(
    bars_list: list[Any],
    buy_idx: int,
    *,
    window_days: int,
) -> tuple[bool, int | None]:
    """
    判定 buy_idx 是否满足买入条件（不含多周期 MACD，由调用方校验）。
    返回 (是否满足, 绿转红日下标)。
    """
    if not is_second_consecutive_limit_up(bars_list, buy_idx):
        return False, None
    g_idx = find_green_to_red_for_second_board(
        bars_list, buy_idx, window_days=window_days
    )
    if g_idx is None:
        return False, None
    if buy_idx - g_idx > window_days:
        return False, None
    buy_bar = bars_list[buy_idx]
    if buy_bar.close is None or float(buy_bar.close) <= 0:
        return False, None
    return True, g_idx


def simulate_exit_after_buy(
    bars_list: list[Any],
    buy_idx: int,
    buy_price: float,
    end_date: date,
    p: _Params,
) -> tuple[int | None, float | None, str | None]:
    """
    自 buy_idx+1 起按收盘价监测；满足其一即卖（或关系）：
    ① MACD 红转绿；② 收盘相对持仓期最高收盘价回落 ≥ trailing_drawdown_pct。
    峰值含买入日收盘；同日两条件均成立时记 MACD 离场。
    """
    buy_bar = bars_list[buy_idx]
    peak_close = buy_price
    if buy_bar.close is not None:
        peak_close = float(buy_bar.close)

    for k in range(buy_idx + 1, len(bars_list)):
        bk = bars_list[k]
        if bk.trade_date > end_date:
            break
        if bk.close is None:
            continue
        ck = float(bk.close)

        if is_macd_red_to_green_day(bars_list[k - 1], bk):
            return k, ck, "sell_macd_red_to_green"

        peak_close = max(peak_close, ck)
        if peak_close > 0:
            drawdown = (peak_close - ck) / peak_close
            if drawdown >= p.trailing_drawdown_pct - 1e-9:
                return k, ck, "trailing_stop_from_peak_5pct"

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
            StockDailyBar.prev_close,
            StockDailyBar.pct_change,
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


def run_lian_xu_da_ban_backtest(
    db: Any,
    *,
    start_date: date,
    end_date: date,
    p: _Params,
) -> BacktestResult:
    extended_start = start_date - timedelta(days=30)
    extended_end = end_date + timedelta(days=400)

    stock_info, stock_bars = _load_daily_bars_grouped(
        db, extended_start=extended_start, extended_end=extended_end
    )

    trades: list[BacktestTrade] = []
    skipped = 0
    for code, bars_list in stock_bars.items():
        if len(bars_list) < 3:
            skipped += 1
            continue
        stock_name = stock_info.get(code)
        last_block = -1
        for i in range(2, len(bars_list)):
            if i <= last_block:
                continue
            ok, g_idx = buy_signal_at(
                bars_list,
                i,
                window_days=p.green_to_red_window_days,
            )
            if not ok or g_idx is None:
                continue

            sig_bar = bars_list[i]
            t_buy = sig_bar.trade_date
            if t_buy < start_date or t_buy > end_date:
                continue

            buy_price = round(float(sig_bar.close), 4)
            buy_date = t_buy
            trigger_date = t_buy
            g_bar = bars_list[g_idx]
            first_board_bar = bars_list[i - 1]

            extra_base: dict[str, Any] = {
                "buy_rule": "second_limit_up_close",
                "sell_rule": "close_peak_trailing_or_macd_green",
                "green_to_red_date": g_bar.trade_date.isoformat(),
                "first_limit_up_date": first_board_bar.trade_date.isoformat(),
                "second_limit_up_date": t_buy.isoformat(),
                "macd_hist_buy": _hist_val(sig_bar),
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
                    },
                ),
            )
            last_block = sell_j

    logger.info("%s 回测完成: trades=%d skipped_short=%d", STRATEGY_ID, len(trades), skipped)
    return BacktestResult(trades=trades, skipped_count=skipped, skip_reasons=[])


class LianXuDaBanStrategy(StockStrategy):
    """连续打板策略入口。"""

    strategy_id = STRATEGY_ID
    version = "v1.5.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="连续打板",
            version=self.version,
            short_description=(
                "选股：绿转红+首板(≥10%)。回测：二连板二板收盘买；"
                "离场：最高收盘回落5%或MACD红转绿（或关系）。"
            ),
            description=(
                "**股票范围**：仅 **主板**，剔除 ST/*ST。\n"
                "**策略选股（execute）**：截止日 **MACD 绿转红**且当日**首板涨停（涨幅≥10%）**；"
                "前一交易日非涨停；**不**判断次日二板。\n"
                "**历史回测（backtest）**：绿转红后 3 日内**首板≥10%**且**续板>9.5%**的连续二涨停，"
                "于**续板日（二板）收盘价**买入。\n"
                "**卖出**（回测，收盘价，**满足其一即卖**）："
                "① 自买入后**最高收盘价**回落 **≥5%**（兼作止盈/止损，非相对买入价固定比例）；"
                "② 日线 **MACD 红转绿**（前日红柱、当日绿柱）。\n"
                "不构成投资建议。"
            ),
            assumptions=[
                "日线 macd_hist 已预计算；绿转红为前日 hist≤0、当日 hist>0。",
                "首板涨停：涨幅≥10%；续板涨停：涨幅>9.5%（优先 pct_change）。",
                "峰值收盘自买入日（含）起统计；回落 5% 含边界。",
            ],
            risks=[
                "涨停判定依赖 prev_close 字段，缺失则跳过。",
                "首板入选不等于次日能二板，需自行风控。",
            ],
            route_path="/strategy/lian-xu-da-ban",
        )

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        if as_of_date is None:
            raise ValueError("as_of_date 不能为空")
        db = SessionLocal()
        try:
            return run_lian_xu_da_ban_execute(db, as_of_date=as_of_date)
        finally:
            db.close()

    def backtest(self, *, start_date: date, end_date: date) -> BacktestResult:
        p = _Params()
        db = SessionLocal()
        try:
            return run_lian_xu_da_ban_backtest(
                db, start_date=start_date, end_date=end_date, p=p
            )
        finally:
            db.close()
