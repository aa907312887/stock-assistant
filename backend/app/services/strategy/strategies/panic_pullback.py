"""
恐慌回落法（用于历史回测验证的内置策略）。

【策略名称】：恐慌回落法
【目标】：在下跌趋势中寻找“恐慌加速日”，并用固定持有 1 个交易日的口径验证次日是否存在修复收益。
【适用范围】：
- 市场：A 股
- 数据粒度：日线（无分时数据）
- 依赖字段：open / close / volume / trade_date（来自 stock_daily_bar），以及 stock_basic.name

【核心规则】：
1) 触发（第 0 天=T）：
   - 均线空头排列：MA5_T < MA10_T < MA20_T
   - 前 5 个交易日至少跌 4 天：在 T-1..T-5 中满足 close_i < close_{i-1} 的天数 ≥ 4
   - 大幅低开（相对昨收）：open_T <= close_{T-1} * 0.97（低开≥3%）
   - 触发日整体下跌：close_T <= close_{T-1} * 0.93（整体跌≥7%）
   - 成交量显著放大（澄清口径 B）：
     - volume_T > max(volume_{T-1..T-5})
     - volume_T >= 1.5 * avg(volume_{T-1..T-5})
2) 买入判定：
   - 买入点：第 0 天（T）收盘价（用于模拟“当日最后买入”）
3) 卖出判定：
   - 卖出点：第 1 天（T+1）收盘价（无论盈亏强制卖出）

【关键口径与阈值】：
- 低开：open_T / close_{T-1} - 1 <= -3%
- 整体跌幅：close_T / close_{T-1} - 1 <= -7%
- 放量（B）：volume_T 同时满足“高于前 5 日最大量”与“≥1.5 倍前 5 日均量”

【边界与异常】：
- 数据缺失：open/close/volume 任一为空、或 close_{T-1}<=0、或窗口内 volume 缺失，则该日不可用于触发判定。
- 不可成交：若无法取到 T+1 日收盘价（停牌/缺失），该笔回测交易记为 skipped（不可成交）并计入 skip_reasons。

【输出与可追溯性】：
- 回测输出：BacktestTrade 列表；extra 中记录触发日与关键计算值，便于复盘。

【示例】：
- 例 1（满足触发）：
  - 满足 MA5<MA10<MA20
  - 最近 5 天中有 4 天收盘下跌
  - T 日低开 -3% 且收盘较昨收 -7% 以上
  - T 日成交量高于过去 5 日最大量，且 ≥1.5 倍过去 5 日均量
  - 则以 T 收盘买入，T+1 收盘卖出，计算收益率
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select

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
    ma_short: int = 5
    ma_mid: int = 10
    ma_long: int = 20
    gap_down_threshold: float = 0.03  # 3%
    day_drop_threshold: float = 0.07  # 7%
    lookback_days: int = 5
    volume_k: float = 1.5


class PanicPullbackStrategy(StockStrategy):
    strategy_id = "panic_pullback"
    version = "v1.0.0"

    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="恐慌回落法",
            version=self.version,
            short_description="在下跌趋势中识别恐慌加速日，并用固定 T+1 收盘卖出口径回测验证。",
            description=(
                "本策略在 A 股日线数据上识别“均线空头排列 + 近期连续下跌 + 当日大幅低开且大跌 + 放量出清”的恐慌日，"
                "并以“触发日收盘买入、次日收盘卖出（无论盈亏）”的固定持有口径做历史回测验证。"
            ),
            assumptions=[
                "当前仅有日线数据，买入与卖出均以收盘价近似，忽略分时成交与滑点。",
                "成交量口径采用日线 volume 字段，放量判定为：volume_T > max(volume_{T-1..T-5}) 且 volume_T >= 1.5 * avg(volume_{T-1..T-5})。",
                "本策略用于历史验证，不构成任何投资建议。",
            ],
            risks=[
                "极端行情或重大利空下，恐慌日可能继续下跌；固定持有口径可能放大回撤。",
                "数据缺失、停牌或口径差异会影响回测结果，应以策略口径为准对比。",
            ],
            route_path="/strategy/panic-pullback",
        )

    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        """
        选股执行：返回“某一日满足触发条件”的候选列表（用于展示/审计）。

        说明：本方法不涉及真实交易，仅用于把触发条件以结构化形式输出。
        """
        params = _Params()
        if as_of_date is None:
            raise ValueError("as_of_date 不能为空")

        db = SessionLocal()
        try:
            items, signals = self._select_trigger_day(db, as_of_date=as_of_date, p=params)
            return StrategyExecutionResult(
                as_of_date=as_of_date,
                assumptions={
                    "data_granularity": "日线",
                    "price_type": "收盘价口径（回测用）",
                    "no_intraday_data": True,
                },
                params={
                    "ma_short": params.ma_short,
                    "ma_mid": params.ma_mid,
                    "ma_long": params.ma_long,
                    "gap_down_threshold": params.gap_down_threshold,
                    "day_drop_threshold": params.day_drop_threshold,
                    "lookback_days": params.lookback_days,
                    "volume_k": params.volume_k,
                },
                items=items,
                signals=signals,
            )
        finally:
            db.close()

    def backtest(self, *, start_date: date, end_date: date) -> BacktestResult:
        """历史回测：逐日扫描触发→以 T 收盘买入、T+1 收盘卖出生成交易。"""
        p = _Params()
        db = SessionLocal()
        try:
            return self._run_backtest(db, start_date=start_date, end_date=end_date, p=p)
        finally:
            db.close()

    @staticmethod
    def _run_backtest(db, *, start_date: date, end_date: date, p: _Params) -> BacktestResult:
        # 需要额外窗口用于均线与“前 5 天跌 4 天/成交量窗口”
        extended_start = start_date - timedelta(days=60)
        extended_end = end_date + timedelta(days=10)

        stmt = (
            select(
                StockDailyBar.stock_code,
                StockDailyBar.trade_date,
                StockDailyBar.open,
                StockDailyBar.close,
                StockDailyBar.volume,
                StockDailyBar.ma5,
                StockDailyBar.ma10,
                StockDailyBar.ma20,
            )
            .where(StockDailyBar.trade_date.between(extended_start, extended_end))
            .order_by(StockDailyBar.stock_code, StockDailyBar.trade_date)
        )
        rows = db.execute(stmt).all()
        logger.info("恐慌回落法回测数据加载完成: %d 条日线记录", len(rows))

        stock_info: dict[str, str | None] = dict(db.query(StockBasic.code, StockBasic.name).all())
        st_codes = {
            code for code, name in stock_info.items()
            if name and (name.startswith("ST") or name.startswith("*ST"))
        }

        stock_bars: dict[str, list[Any]] = defaultdict(list)
        for row in rows:
            if row.stock_code not in st_codes:
                stock_bars[row.stock_code].append(row)

        all_market_dates = sorted({row.trade_date for row in rows})
        market_next: dict[date, date] = {}
        for i in range(len(all_market_dates) - 1):
            market_next[all_market_dates[i]] = all_market_dates[i + 1]

        trades: list[BacktestTrade] = []
        skipped = 0
        skip_reasons: list[str] = []

        for code, bars_list in stock_bars.items():
            stock_name = stock_info.get(code)
            date_idx = {b.trade_date: i for i, b in enumerate(bars_list)}

            for i, bar_t in enumerate(bars_list):
                trigger_date = bar_t.trade_date
                if trigger_date < start_date or trigger_date > end_date:
                    continue

                # 需要 bar_{t-1}，以及窗口 T-1..T-5 与它们各自的前一日 close
                if i < p.lookback_days + 1:
                    continue

                bar_prev = bars_list[i - 1]
                if not (bar_prev.close and float(bar_prev.close) > 0):
                    continue
                prev_close_f = float(bar_prev.close)

                # 均线空头排列
                if not (bar_t.ma5 and bar_t.ma10 and bar_t.ma20):
                    continue
                if not (float(bar_t.ma5) < float(bar_t.ma10) < float(bar_t.ma20)):
                    continue

                # 前 5 天至少跌 4 天（用 close_i < close_{i-1} 口径）
                down_days = 0
                valid_down_window = True
                for j in range(i - p.lookback_days, i):
                    b = bars_list[j]
                    b_prev = bars_list[j - 1]
                    if not (b.close and b_prev.close):
                        valid_down_window = False
                        break
                    if float(b.close) < float(b_prev.close):
                        down_days += 1
                if not valid_down_window or down_days < 4:
                    continue

                # 大幅低开（相对昨收）
                if not (bar_t.open and float(bar_t.open) > 0):
                    continue
                if float(bar_t.open) > prev_close_f * (1 - p.gap_down_threshold):
                    continue

                # 触发日整体下跌（相对昨收）
                if not (bar_t.close and float(bar_t.close) > 0):
                    continue
                close_t_f = float(bar_t.close)
                if close_t_f > prev_close_f * (1 - p.day_drop_threshold):
                    continue

                # 成交量显著放大（B 口径）
                if not (bar_t.volume and float(bar_t.volume) > 0):
                    continue
                vol_t = float(bar_t.volume)
                vols = []
                vols_valid = True
                for j in range(i - p.lookback_days, i):
                    v = bars_list[j].volume
                    if not (v and float(v) > 0):
                        vols_valid = False
                        break
                    vols.append(float(v))
                if not vols_valid:
                    continue
                vol_max = max(vols)
                vol_avg = sum(vols) / len(vols)
                if not (vol_t > vol_max and vol_t >= p.volume_k * vol_avg):
                    continue

                # 卖出日（T+1）=下一交易日收盘
                t1_date = market_next.get(trigger_date)
                if t1_date is None or t1_date > end_date:
                    # 超出回测区间，记为未平仓
                    trades.append(BacktestTrade(
                        stock_code=code,
                        stock_name=stock_name,
                        buy_date=trigger_date,
                        buy_price=round(close_t_f, 4),
                        trade_type="unclosed",
                        extra={
                            "trigger_date": trigger_date.isoformat(),
                            "down_days_in_5": down_days,
                            "gap_down_pct": round(float(bar_t.open) / prev_close_f - 1, 6),
                            "day_drop_pct": round(close_t_f / prev_close_f - 1, 6),
                            "vol_t": vol_t,
                            "vol_max_5": vol_max,
                            "vol_avg_5": round(vol_avg, 4),
                            "volume_k": p.volume_k,
                        },
                    ))
                    continue

                t1_idx = date_idx.get(t1_date)
                if t1_idx is None:
                    skipped += 1
                    if len(skip_reasons) < 200:
                        skip_reasons.append(f"{code} {trigger_date}: T+1 停牌/无数据")
                    continue

                bar_t1 = bars_list[t1_idx]
                if not (bar_t1.close and float(bar_t1.close) > 0):
                    skipped += 1
                    if len(skip_reasons) < 200:
                        skip_reasons.append(f"{code} {trigger_date}: T+1 收盘价缺失")
                    continue

                sell_price = round(float(bar_t1.close), 4)
                buy_price = round(close_t_f, 4)
                return_rate = round((sell_price - buy_price) / buy_price, 4)

                trades.append(BacktestTrade(
                    stock_code=code,
                    stock_name=stock_name,
                    buy_date=trigger_date,
                    buy_price=buy_price,
                    sell_date=t1_date,
                    sell_price=sell_price,
                    return_rate=return_rate,
                    trade_type="closed",
                    extra={
                        "trigger_date": trigger_date.isoformat(),
                        "down_days_in_5": down_days,
                        "gap_down_pct": round(float(bar_t.open) / prev_close_f - 1, 6),
                        "day_drop_pct": round(close_t_f / prev_close_f - 1, 6),
                        "vol_t": vol_t,
                        "vol_max_5": vol_max,
                        "vol_avg_5": round(vol_avg, 4),
                        "volume_k": p.volume_k,
                    },
                ))

        logger.info("恐慌回落法回测扫描完成: trades=%d, skipped=%d", len(trades), skipped)
        return BacktestResult(trades=trades, skipped_count=skipped, skip_reasons=skip_reasons)

    @staticmethod
    def _select_trigger_day(db, *, as_of_date: date, p: _Params) -> tuple[list[StrategyCandidate], list[StrategySignal]]:
        """
        返回某一交易日满足触发条件的候选列表（不生成回测交易）。

        说明：为保持实现简单，本方法复用回测同口径，按单日扫描实现（不做复杂 SQL 窗口函数优化）。
        """
        # 复用回测：只扫描 as_of_date 当天即可
        result = PanicPullbackStrategy._run_backtest(db, start_date=as_of_date, end_date=as_of_date, p=p)
        items: list[StrategyCandidate] = []
        signals: list[StrategySignal] = []
        for t in result.trades:
            if t.buy_date != as_of_date:
                continue
            items.append(StrategyCandidate(
                stock_code=t.stock_code,
                stock_name=t.stock_name,
                exchange_type=None,
                trigger_date=t.buy_date,
                summary=t.extra,
            ))
            signals.append(StrategySignal(
                stock_code=t.stock_code,
                event_date=t.buy_date,
                event_type="trigger",
                payload=t.extra,
            ))
        # 注意：as_of_date 单日扫描下，超出区间的 unclosed 不会出现（start=end）
        return items, signals

