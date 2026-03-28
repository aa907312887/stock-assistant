"""回测功能 Pydantic 请求/响应模型。"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class RunBacktestRequest(BaseModel):
    strategy_id: str
    start_date: date
    end_date: date


class RunBacktestResponse(BaseModel):
    task_id: str
    status: str
    message: str


class BacktestTaskItem(BaseModel):
    task_id: str
    strategy_id: str
    strategy_name: str
    strategy_version: str
    start_date: date
    end_date: date
    status: str
    total_trades: int | None = None
    win_rate: float | None = None
    total_return: float | None = None
    created_at: datetime
    finished_at: datetime | None = None


class BacktestTaskListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[BacktestTaskItem]


class TempLevelStat(BaseModel):
    level: str
    total: int
    wins: int
    win_rate: float
    avg_return: float


class DimensionStat(BaseModel):
    name: str
    total: int
    wins: int
    win_rate: float
    avg_return: float


class BacktestReport(BaseModel):
    total_trades: int
    win_trades: int
    lose_trades: int
    win_rate: float
    total_return: float
    avg_return: float
    max_win: float
    max_loss: float
    unclosed_count: int
    skipped_count: int
    conclusion: str
    temp_level_stats: list[TempLevelStat] = Field(default_factory=list)
    exchange_stats: list[DimensionStat] = Field(default_factory=list)
    market_stats: list[DimensionStat] = Field(default_factory=list)


class BacktestTaskDetailResponse(BaseModel):
    task_id: str
    strategy_id: str
    strategy_name: str
    strategy_version: str
    start_date: date
    end_date: date
    status: str
    report: BacktestReport | None = None
    assumptions: dict | None = None
    created_at: datetime
    finished_at: datetime | None = None


class BacktestTradeItem(BaseModel):
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


class BacktestTradeListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[BacktestTradeItem]


class BacktestFilteredMetrics(BaseModel):
    """按筛选条件复算后的绩效指标。"""

    total_trades: int
    win_trades: int
    lose_trades: int
    win_rate: float
    total_return: float
    avg_return: float
    max_win: float
    max_loss: float
    unclosed_count: int
    matched_count: int


class BacktestFilteredReportResponse(BaseModel):
    """回测结果按条件筛选后的复算响应。"""

    task_id: str
    filters: dict
    metrics: BacktestFilteredMetrics


class BacktestBestOptionItem(BaseModel):
    """最佳选项结果（一个目标对应一组条件 + 指标）。"""

    filters: dict
    metrics: BacktestFilteredMetrics


class BacktestBestOptionsResponse(BaseModel):
    """自动搜索后的最佳胜率/最佳收益条件。"""

    task_id: str
    best_win_rate: BacktestBestOptionItem
    best_total_return: BacktestBestOptionItem


class BacktestYearlyStatItem(BaseModel):
    """按买入日自然年聚合的统计（可与温度/交易所/板块/年份筛选组合）。"""

    year: int
    matched_count: int
    total_trades: int
    win_trades: int
    lose_trades: int
    win_rate: float
    total_return: float
    avg_return: float


class BacktestYearlyAnalysisResponse(BaseModel):
    task_id: str
    filters: dict
    items: list[BacktestYearlyStatItem]


class DataRangeResponse(BaseModel):
    min_date: date | None = None
    max_date: date | None = None
