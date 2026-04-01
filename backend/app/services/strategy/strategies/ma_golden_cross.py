"""
均线金叉策略（用于历史回测验证的内置策略）。

【策略名称】：均线金叉
【目标】：捕捉短期均线上穿长期均线的金叉信号，在趋势启动初期买入，通过固定止盈止损控制风险收益比。
【适用范围】：
- 市场：A 股全市场
- 数据粒度：日线（无分时数据）
- 依赖字段：open / close / ma5 / ma10 / trade_date（来自 stock_daily_bar）

【核心规则】：
1) 买入条件（金叉确认）：
   - MA5 第一次超过 MA10（金叉信号）
   - MA5 呈上升趋势（当日 MA5 > 前一日 MA5）
   - 当日收盘价买入

2) 卖出规则：
   - 止盈：盈利 >= 5% → 以买入价 × 1.05 卖出
   - 止损：亏损 >= 3% → 以买入价 × 0.97 卖出
   - 优先级：同日触发时，止损优先

【关键口径与阈值】：
- 金叉定义：MA5 > MA10 且前一日 MA5 <= MA10
- MA5 上升趋势：当日 MA5 > 前一日 MA5
- 止盈比例：+5%
- 止损比例：-3%

【输出与可追溯性】：
- 选股输出：StrategyCandidate 列表
- 回测输出：BacktestTrade 列表；extra_json 中记录金叉日期、MA5/MA10 值等
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
    profit_pct: float = 0.05  # 止盈比例 5%
    stop_loss_pct: float = 0.05  # 止损比例 5%
    low_position_ratio: float = 2 / 3  # 低位约束：股价不超过历史最高价的 2/3
    low_open_pct: float = 0.02  # 低开比例：至少低开 2%
    min_hist_days: int = 20  # 最少历史数据天数


@dataclass
class _GoldenCrossSignal:
    """金叉信号。"""
    stock_code: str
    trigger_date: date  # 金叉日
    ma5: Decimal  # 当日 MA5
    ma10: Decimal  # 当日 MA10
    close_price: Decimal  # 金叉日收盘价
    buy_date: date  # 买入日（T+1 低开买入）


class MAGoldenCrossStrategy(StockStrategy):
    """均线金叉策略实现。"""
    
    strategy_id = "ma_golden_cross"
    version = "v1.0.0"
    
    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="均线金叉",
            version=self.version,
            short_description="捕捉 MA5 上穿 MA10 的金叉信号，通过固定止盈止损控制风险。",
            description=(
                "本策略在 A 股日线数据上识别「MA5 第一次超过 MA10 且 MA5 呈上升趋势」的金叉信号，"
                "在金叉确认后买入，通过固定止盈止损规则控制风险收益比。"
            ),
            assumptions=[
                "低位约束：当前股价不超过历史最高价的三分之二。",
                "金叉定义：当日 MA5 > MA10，且前一日 MA5 <= MA10。",
                "MA5 上升趋势：当日 MA5 > 前一日 MA5。",
                "MA10 上升趋势：当日 MA10 > 前一日 MA10。",
                "成交量放大：当日成交量 >= 前一日成交量 × 1.5。",
                "买入条件：金叉次日低开至少 2%，且金叉日均线多头排列。",
                "多头排列：MA5 > MA10 > MA20 且三者都比前一天高。",
                "止盈：盈利 >= 5% 时以买入价 × 1.05 卖出。",
                "止损：亏损 >= 5% 时以买入价 × 0.95 卖出。",
                "本策略用于历史验证，不构成投资建议。",
            ],
            risks=[
                "均线信号有滞后性，可能错过最佳买卖点。",
                "震荡行情中可能频繁触发止损。",
                "数据缺失、停牌会影响回测结果准确性。",
            ],
            route_path="/strategy/ma-golden-cross",
        )
    
    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult:
        """选股执行：识别当日满足金叉条件的股票。"""
        params = _Params()
        if as_of_date is None:
            raise ValueError("as_of_date 不能为空")
        
        db = SessionLocal()
        try:
            items, signals = self._select_golden_cross_stocks(db, as_of_date=as_of_date, p=params)
            return StrategyExecutionResult(
                as_of_date=as_of_date,
                assumptions={"data_granularity": "日线", "stock_universe": "A股全市场"},
                params={
                    "profit_pct": params.profit_pct,
                    "stop_loss_pct": params.stop_loss_pct,
                },
                items=items,
                signals=signals,
            )
        finally:
            db.close()
    
    def backtest(self, *, start_date: date, end_date: date) -> BacktestResult:
        """回测执行：在指定时间范围内模拟策略交易。"""
        params = _Params()
        db = SessionLocal()
        
        try:
            # 查询所有日线数据
            bars_stmt = (
                select(StockDailyBar)
                .where(
                    and_(
                        StockDailyBar.trade_date >= start_date - timedelta(days=60),
                        StockDailyBar.trade_date <= end_date,
                        StockDailyBar.close.isnot(None),
                        StockDailyBar.ma5.isnot(None),
                        StockDailyBar.ma10.isnot(None),
                        StockDailyBar.cum_hist_high.isnot(None),
                    )
                )
                .order_by(StockDailyBar.stock_code, StockDailyBar.trade_date)
            )
            all_bars = db.execute(bars_stmt).scalars().all()
            
            # 查询股票基本信息
            basics_stmt = select(StockBasic)
            basics = db.execute(basics_stmt).scalars().all()
            stock_names = {b.code: b.name for b in basics}
            
            # 按股票分组
            bars_by_code: dict[str, list[StockDailyBar]] = defaultdict(list)
            for bar in all_bars:
                bars_by_code[bar.stock_code].append(bar)
            
            # 逐股识别金叉信号
            all_signals: list[_GoldenCrossSignal] = []
            skipped_count = 0
            
            for stock_code, stock_bars in bars_by_code.items():
                if len(stock_bars) < params.min_hist_days:
                    skipped_count += 1
                    continue
                
                signals = self._find_golden_cross(stock_code, stock_bars, params, start_date)
                all_signals.extend(signals)
            
            logger.info(
                "均线金叉回测信号扫描完成: 扫描 %d 只股票, 识别 %d 个信号, 跳过 %d 只",
                len(bars_by_code), len(all_signals), skipped_count,
            )
            
            # 对每个信号模拟交易
            trades: list[BacktestTrade] = []
            for signal in all_signals:
                trade = self._simulate_trade(
                    signal, bars_by_code[signal.stock_code], stock_names.get(signal.stock_code), params, end_date
                )
                if trade:
                    trades.append(trade)
            
            return BacktestResult(trades=trades, skipped_count=skipped_count)
            
        finally:
            db.close()
    
    def _select_golden_cross_stocks(
        self, db, *, as_of_date: date, p: _Params
    ) -> tuple[list[StrategyCandidate], list[StrategySignal]]:
        """选股核心逻辑：识别当日满足金叉条件的股票。"""
        # 查询当日所有日线数据
        bars_stmt = select(StockDailyBar).where(
            and_(
                StockDailyBar.trade_date == as_of_date,
                StockDailyBar.close.isnot(None),
                StockDailyBar.ma5.isnot(None),
                StockDailyBar.ma10.isnot(None),
                StockDailyBar.cum_hist_high.isnot(None),
            )
        )
        today_bars = db.execute(bars_stmt).scalars().all()
        
        basics_stmt = select(StockBasic)
        basics = db.execute(basics_stmt).scalars().all()
        stock_names = {b.code: b.name for b in basics}
        stock_exchanges = {b.code: b.exchange for b in basics}
        
        items: list[StrategyCandidate] = []
        signals: list[StrategySignal] = []
        
        for bar in today_bars:
            # 查询该股票的历史数据（前一天的 MA5/MA10）
            hist_stmt = select(StockDailyBar).where(
                and_(
                    StockDailyBar.stock_code == bar.stock_code,
                    StockDailyBar.trade_date < as_of_date,
                    StockDailyBar.ma5.isnot(None),
                    StockDailyBar.ma10.isnot(None),
                )
            ).order_by(StockDailyBar.trade_date.desc()).limit(1)
            prev_bar = db.execute(hist_stmt).scalar_one_or_none()
            
            if prev_bar is None:
                continue
            
            # 低位约束：当前股价不超过历史最高价的三分之二
            if bar.cum_hist_high is None or bar.close > bar.cum_hist_high * Decimal(str(p.low_position_ratio)):
                continue
            
            # 检查多头排列
            if not self._is_bullish_alignment(bar, prev_bar):
                continue
            
            # 检查金叉条件
            if self._is_golden_cross(bar, prev_bar):
                # 计算成交量比
                volume_ratio = None
                if bar.volume and prev_bar.volume and prev_bar.volume > 0:
                    volume_ratio = float(bar.volume / prev_bar.volume)
                
                items.append(StrategyCandidate(
                    stock_code=bar.stock_code,
                    stock_name=stock_names.get(bar.stock_code),
                    exchange_type=stock_exchanges.get(bar.stock_code),
                    trigger_date=as_of_date,
                    summary={
                        "ma5": float(bar.ma5) if bar.ma5 else None,
                        "ma10": float(bar.ma10) if bar.ma10 else None,
                        "ma20": float(bar.ma20) if bar.ma20 else None,
                        "close": float(bar.close) if bar.close else None,
                        "volume_ratio": volume_ratio,
                    },
                ))
                signals.append(StrategySignal(
                    stock_code=bar.stock_code,
                    event_date=as_of_date,
                    event_type="trigger",
                    payload={
                        "ma5": float(bar.ma5),
                        "ma10": float(bar.ma10),
                    },
                ))
        
        logger.info(
            "均线金叉选股完成: 扫描 %d 只股票, 识别 %d 个候选",
            len(today_bars), len(items),
        )
        
        return items, signals
    
    def _is_golden_cross(self, bar: StockDailyBar, prev_bar: StockDailyBar) -> bool:
        """
        判断是否满足金叉条件：
        1. 当日 MA5 > MA10
        2. 前一日 MA5 <= MA10
        3. 当日 MA5 > 前一日 MA5（MA5 上升趋势）
        4. 当日 MA10 > 前一日 MA10（MA10 上升趋势）
        5. 当日成交量 >= 前一日成交量 × 1.5（成交量放大）
        """
        if bar.ma5 is None or bar.ma10 is None:
            return False
        if prev_bar.ma5 is None or prev_bar.ma10 is None:
            return False
        
        # 条件1：当日 MA5 > MA10
        if bar.ma5 <= bar.ma10:
            return False
        
        # 条件2：前一日 MA5 <= MA10（第一次上穿）
        if prev_bar.ma5 > prev_bar.ma10:
            return False
        
        # 条件3：当日 MA5 > 前一日 MA5（MA5 上升趋势）
        if bar.ma5 <= prev_bar.ma5:
            return False
        
        # 条件4：当日 MA10 > 前一日 MA10（MA10 上升趋势）
        if bar.ma10 <= prev_bar.ma10:
            return False
        
        # 条件5：成交量放大（当日成交量 >= 前一日 × 1.5）
        if bar.volume is None or prev_bar.volume is None:
            return False
        if prev_bar.volume <= 0:
            return False
        if bar.volume < prev_bar.volume * Decimal("1.5"):
            return False
        
        return True
    
    def _find_golden_cross(
        self,
        stock_code: str,
        bars: list[StockDailyBar],
        p: _Params,
        min_trigger_date: date | None = None,
    ) -> list[_GoldenCrossSignal]:
        """识别金叉信号。"""
        signals: list[_GoldenCrossSignal] = []
        
        for i, bar in enumerate(bars):
            if i == 0:
                continue
            
            prev_bar = bars[i - 1]
            
            if not self._is_golden_cross(bar, prev_bar):
                continue
            
            # 低位约束：当前股价不超过历史最高价的三分之二
            if bar.cum_hist_high is None or bar.close > bar.cum_hist_high * Decimal(str(p.low_position_ratio)):
                continue
            
            # 多头排列判断（用金叉日当天和前一天的数据）
            if not self._is_bullish_alignment(bar, prev_bar):
                continue
            
            if min_trigger_date is not None and bar.trade_date < min_trigger_date:
                continue
            
            # 金叉信号：次日低开买入
            buy_date = self._next_trade_date(bar.trade_date, bars)
            
            signals.append(_GoldenCrossSignal(
                stock_code=stock_code,
                trigger_date=bar.trade_date,
                ma5=bar.ma5,
                ma10=bar.ma10,
                close_price=bar.close,
                buy_date=buy_date,
            ))
        
        return signals
    
    def _next_trade_date(self, current_date: date, bars: list[StockDailyBar]) -> date:
        """获取下一个交易日。"""
        for bar in bars:
            if bar.trade_date > current_date:
                return bar.trade_date
        return current_date + timedelta(days=1)
    
    def _simulate_trade(
        self,
        signal: _GoldenCrossSignal,
        bars: list[StockDailyBar],
        stock_name: str | None,
        p: _Params,
        end_date: date,
    ) -> BacktestTrade | None:
        """模拟单笔交易：T+1 低开买入，固定止盈止损卖出。"""
        # 找到买入日的 K 线
        buy_bar = None
        for bar in bars:
            if bar.trade_date == signal.buy_date:
                buy_bar = bar
                break
        
        if buy_bar is None or buy_bar.open is None:
            return None
        
        # 检查低开条件：开盘价 <= 金叉日收盘价 × (1 - low_open_pct)
        low_open_threshold = signal.close_price * (1 - Decimal(str(p.low_open_pct)))
        if buy_bar.open > low_open_threshold:
            # 未满足低开条件，不买入
            return None
        
        buy_price = buy_bar.open
        
        # 计算止盈止损价格
        profit_price = buy_price * (1 + Decimal(str(p.profit_pct)))  # 5%
        stop_loss_price = buy_price * (1 - Decimal(str(p.stop_loss_pct)))  # 5%
        
        sell_date, sell_price, exit_reason = None, None, None
        
        for bar in bars:
            if bar.trade_date <= signal.buy_date or bar.trade_date > end_date:
                continue
            
            # 检查止损（优先）
            if bar.low and bar.low <= stop_loss_price:
                sell_date = bar.trade_date
                sell_price = stop_loss_price
                exit_reason = f"止损（亏损{int(p.stop_loss_pct * 100)}%）"
                break
            
            # 检查止盈
            if bar.high and bar.high >= profit_price:
                sell_date = bar.trade_date
                sell_price = profit_price
                exit_reason = f"止盈（盈利{int(p.profit_pct * 100)}%）"
                break
        
        if sell_date is None:
            return BacktestTrade(
                stock_code=signal.stock_code,
                stock_name=stock_name,
                buy_date=signal.buy_date,
                buy_price=float(buy_price),
                sell_date=None,
                sell_price=None,
                return_rate=None,
                trade_type="unclosed",
                trigger_date=signal.trigger_date,
                extra={
                    "golden_cross_date": str(signal.trigger_date),
                    "ma5": float(signal.ma5),
                    "ma10": float(signal.ma10),
                    "close_price": float(signal.close_price),
                    "low_open_threshold": float(low_open_threshold),
                    "profit_price": float(profit_price),
                    "stop_loss_price": float(stop_loss_price),
                },
            )
        
        return_rate = (sell_price - buy_price) / buy_price
        
        return BacktestTrade(
            stock_code=signal.stock_code,
            stock_name=stock_name,
            buy_date=signal.buy_date,
            buy_price=float(buy_price),
            sell_date=sell_date,
            sell_price=float(sell_price),
            return_rate=float(return_rate),
            trade_type="closed",
            trigger_date=signal.trigger_date,
            extra={
                "golden_cross_date": str(signal.trigger_date),
                "ma5": float(signal.ma5),
                "ma10": float(signal.ma10),
                "close_price": float(signal.close_price),
                "low_open_threshold": float(low_open_threshold),
                "profit_price": float(profit_price),
                "stop_loss_price": float(stop_loss_price),
                "exit_reason": exit_reason,
            },
        )
    
    def _is_bullish_alignment(self, bar: StockDailyBar, prev_bar: StockDailyBar | None) -> bool:
        """
        检查均线多头排列：
        1. MA5 > MA10 > MA20
        2. MA5、MA10、MA20 都比前一天高（增长）
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