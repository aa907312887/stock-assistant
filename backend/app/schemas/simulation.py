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


class SimulationReport(BaseModel):
    total_trades: int
    win_trades: int
    lose_trades: int
    win_rate: float
    avg_return: float
    max_win: float
    max_loss: float
    unclosed_count: int
    skipped_count: int
    conclusion: str
    temp_level_stats: list[TempLevelStat] = Field(default_factory=list)
    exchange_stats: list[DimensionStat] = Field(default_factory=list)
    market_stats: list[DimensionStat] = Field(default_factory=list)


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
