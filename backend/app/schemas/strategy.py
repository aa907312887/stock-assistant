"""策略选股接口 Schema（与 OpenAPI 契约保持一致）。"""

from __future__ import annotations

from datetime import date as dt_date
from typing import Any, Literal

from pydantic import BaseModel, Field


class StrategySummary(BaseModel):
    strategy_id: str
    name: str
    version: str
    short_description: str
    route_path: str


class ListStrategiesResponse(BaseModel):
    items: list[StrategySummary] = Field(default_factory=list)


class GetStrategyResponse(BaseModel):
    strategy_id: str
    name: str
    version: str
    description: str
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class ExecuteStrategyRequest(BaseModel):
    as_of_date: dt_date | None = Field(default=None, description="截止时间点；不传则使用数据库最新交易日")


Timeframe = Literal["daily"]


class ExecutionSnapshot(BaseModel):
    execution_id: str
    strategy_id: str
    strategy_version: str
    market: Literal["A股"] = "A股"
    as_of_date: dt_date
    timeframe: Timeframe = "daily"
    assumptions: dict[str, Any] = Field(default_factory=dict)


class StrategySelectionItem(BaseModel):
    stock_code: str
    stock_name: str | None = None
    exchange: str | None = Field(default=None, description="交易所：SSE/SZSE/BSE（来自 stock_basic.exchange）")
    market: str | None = Field(default=None, description="板块：主板/创业板/科创板/北交所等（来自 stock_basic.market）")
    exchange_type: str | None = Field(default=None, description="兼容旧页：可由交易所/板块拼接，勿单独用作筛选主字段")
    trigger_date: dt_date
    summary: dict[str, Any] = Field(default_factory=dict)


SignalType = Literal["trigger", "entry", "exit", "filter", "note"]


class SignalEvent(BaseModel):
    stock_code: str
    event_date: dt_date
    event_type: SignalType
    payload: dict[str, Any] = Field(default_factory=dict)


class ExecuteStrategyResponse(BaseModel):
    execution: ExecutionSnapshot
    items: list[StrategySelectionItem] = Field(default_factory=list)
    signals: list[SignalEvent] = Field(default_factory=list)

