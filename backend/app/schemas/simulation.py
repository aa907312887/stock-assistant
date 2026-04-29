"""历史模拟功能 Pydantic 请求/响应模型。"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.backtest import (
    BacktestFilteredReportResponse,
    BacktestYearlyAnalysisResponse,
    DimensionStat,
    TempLevelStat,
)


class RunSimulationRequest(BaseModel):
    strategy_id: str
    start_date: date
    end_date: date


class RunSimulationResponse(BaseModel):
    task_id: str
    status: str
    message: str


class SimulationTaskItem(BaseModel):
    task_id: str
    strategy_id: str
    strategy_name: str
    strategy_version: str
    start_date: date
    end_date: date
    status: str
    total_trades: int | None = None
    win_trades: int | None = None
    win_rate: float | None = None
    avg_return: float | None = None
    created_at: datetime
    finished_at: datetime | None = None


class SimulationTaskListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SimulationTaskItem]


class SimulationMonthWindowStats(BaseModel):
    """买入后首月（自然日窗口）汇总统计，口径见 assumptions / 页面 Tooltip。"""

    window_calendar_days: int = 30
    gain_threshold_pct: float = 0.08
    stop_threshold_pct: float = 0.08
    ignore_volatility_success_ratio: float = Field(
        default=0.0,
        description="不考虑中途下跌成功率：窗口内至少一日收盘价相对买入价达到目标涨幅的笔数 / 本任务已平仓笔数（闭仓总数）",
    )
    worst_single_mdd_pct: float = Field(
        default=0.0,
        description="各笔「经典最大回撤」中的最差值（一般为负）",
    )
    avg_mdd_pct: float = Field(
        default=0.0,
        description="各笔经典最大回撤的简单平均",
    )
    path_a_count: int = 0
    path_b_count: int = 0
    path_c_count: int = 0
    path_d_count: int = 0
    path_a_ratio: float = 0.0
    path_b_ratio: float = 0.0
    path_c_ratio: float = 0.0
    path_d_ratio: float = 0.0
    trades_with_metrics: int = Field(default=0, description="纳入首月统计的已平仓笔数（与闭仓总数一致）")


class SimulationReport(BaseModel):
    total_trades: int
    win_trades: int
    lose_trades: int
    win_rate: float
    avg_return: float
    max_win: float
    max_loss: float
    avg_holding_days: float = Field(default=0.0, description="平均交易时间（自然日天数，已平仓交易的 sell_date-buy_date 平均值）")
    unclosed_count: int
    skipped_count: int
    conclusion: str
    temp_level_stats: list[TempLevelStat] = Field(default_factory=list)
    exchange_stats: list[DimensionStat] = Field(default_factory=list)
    market_stats: list[DimensionStat] = Field(default_factory=list)
    month_window_stats: SimulationMonthWindowStats | None = None


class SimulationTaskDetailResponse(BaseModel):
    task_id: str
    strategy_id: str
    strategy_name: str
    strategy_version: str
    start_date: date
    end_date: date
    status: str
    report: SimulationReport | None = None
    assumptions: dict | None = None
    created_at: datetime
    finished_at: datetime | None = None
    strategy_description: str | None = None


class SimulationTradeItem(BaseModel):
    id: int
    stock_code: str
    stock_name: str | None = None
    buy_date: date
    buy_price: float
    sell_date: date | None = None
    sell_price: float | None = None
    return_rate: float | None = None
    trade_type: str
    exchange: str | None = None
    market: str | None = None
    market_temp_score: float | None = None
    market_temp_level: str | None = None
    extra: dict | None = None


class SimulationTradeListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SimulationTradeItem]
