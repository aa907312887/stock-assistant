"""历史模拟交易 Pydantic Schemas。"""

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, field_validator


# ---------- 会话 ----------

class CreateSessionRequest(BaseModel):
    start_date: date
    initial_cash: float
    name: Optional[str] = None

    @field_validator("initial_cash")
    @classmethod
    def validate_cash(cls, v: float) -> float:
        if v < 1000:
            raise ValueError("初始资金不能低于 1000 元")
        return v


class PositionSummary(BaseModel):
    """持仓聚合展示（按股票聚合多批次，展示加权均价）。"""
    stock_code: str
    stock_name: Optional[str]
    total_quantity: int
    avg_cost_price: float
    current_price: Optional[float]   # phase=open 时为开盘价，phase=close 时为收盘价
    market_value: Optional[float]
    profit_loss: Optional[float]
    profit_loss_pct: Optional[float]
    can_sell_quantity: int           # 排除当日买入批次后的可卖数量


class ClosedStockSummary(BaseModel):
    """已清仓股票：当前会话内对该代码已无 holding 批次，但存在 closed 批次（曾全部卖出）。"""
    stock_code: str
    stock_name: Optional[str]
    closed_batch_count: int
    # 本会话内该代码已实现盈亏：卖出净入金 − 买入净出金（均含手续费），比例 = 盈亏 / 买入总成本
    realized_profit_loss: float
    realized_profit_loss_pct: float


class SessionResponse(BaseModel):
    session_id: str
    name: Optional[str]
    start_date: date
    current_date: date
    current_phase: str               # open / close
    initial_cash: float
    available_cash: float
    status: str
    positions: list[PositionSummary] = []
    closed_stocks: list[ClosedStockSummary] = []
    total_asset: float
    total_profit_loss: float
    total_profit_loss_pct: float
    created_at: datetime
    # 展示用：对应「当前模拟日」的上一交易日收盘后的大盘温度（非模拟当日，避免未收盘当日被误用）
    market_temp_ref_date: Optional[date] = None
    market_temp_score: Optional[float] = None
    market_temp_level: Optional[str] = None


class SessionListItem(BaseModel):
    session_id: str
    name: Optional[str]
    start_date: date
    current_date: date
    current_phase: str
    initial_cash: float
    available_cash: float
    total_asset: float
    status: str
    created_at: datetime


class SessionListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SessionListItem]


# ---------- 推进到收盘 / 下一交易日 ----------

class PhaseResponse(BaseModel):
    current_date: date
    current_phase: str
    available_cash: float
    positions: list[PositionSummary]
    closed_stocks: list[ClosedStockSummary] = []
    market_temp_ref_date: Optional[date] = None
    market_temp_score: Optional[float] = None
    market_temp_level: Optional[str] = None


class NextDayResponse(BaseModel):
    previous_date: date
    current_date: date
    current_phase: str
    available_cash: float
    positions: list[PositionSummary]
    closed_stocks: list[ClosedStockSummary] = []
    market_temp_ref_date: Optional[date] = None
    market_temp_score: Optional[float] = None
    market_temp_level: Optional[str] = None


class EndSessionResponse(BaseModel):
    """结束会话响应。"""
    session_id: str
    status: str


# ---------- 买入 / 卖出 ----------

class BuyRequest(BaseModel):
    stock_code: str
    price: float
    quantity: int

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v <= 0 or v % 100 != 0:
            raise ValueError("买入数量必须为 100 的正整数倍")
        return v


class SellRequest(BaseModel):
    stock_code: str
    price: float
    quantity: int

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v <= 0 or v % 100 != 0:
            raise ValueError("卖出数量必须为 100 的正整数倍")
        return v


class OrderResponse(BaseModel):
    order_id: int
    order_type: str
    stock_code: str
    stock_name: Optional[str]
    trade_date: date
    price: float
    quantity: int
    amount: float
    commission: float
    cash_after: float
    # 订单写入数据库的时间，用于同日内多笔成交的先后展示
    created_at: datetime


class OrderListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[OrderResponse]


# ---------- 图表数据 ----------

class ChartBar(BaseModel):
    date: str
    open: Optional[float]
    high: Optional[float]   # phase=open 时日 K 最新一根为 None
    low: Optional[float]    # phase=open 时日 K 最新一根为 None
    close: Optional[float]  # phase=open 时日 K 最新一根为 None
    volume: Optional[float] # phase=open 时日 K 最新一根为 None（避免提前暴露全日量）
    prev_close: Optional[float]
    pct_change: Optional[float]
    ma5: Optional[float]
    ma10: Optional[float]
    ma20: Optional[float]
    ma60: Optional[float]
    macd_dif: Optional[float]  # phase=open 时最新一根为 None
    macd_dea: Optional[float]  # phase=open 时最新一根为 None
    macd_hist: Optional[float] # phase=open 时最新一根为 None


class ChartDataResponse(BaseModel):
    stock_code: str
    stock_name: Optional[str]
    period: str
    open_price: Optional[float]   # 当日开盘价（快捷填充用）
    close_price: Optional[float]  # 当日收盘价（phase=close 时有值）
    limit_up: Optional[float]     # 涨停价
    limit_down: Optional[float]   # 跌停价
    data: list[ChartBar]


# ---------- 推荐 / 筛选 ----------

class StockQuote(BaseModel):
    stock_code: str
    stock_name: Optional[str]
    open: Optional[float]
    close: Optional[float]    # phase=open 时为 None
    pct_change: Optional[float]  # phase=open 时为 None
    volume: Optional[float]
    limit_up: Optional[float]
    limit_down: Optional[float]


class RecommendResponse(BaseModel):
    trade_date: date
    phase: str
    items: list[StockQuote]


class ScreenResponse(BaseModel):
    trade_date: date
    total: int
    page: int
    page_size: int
    items: list[StockQuote]


# ---------- 交易日列表 ----------

class TradingDatesResponse(BaseModel):
    dates: list[str]
    min_date: str
    max_date: str


# ---------- 股票解析（代码 / 名称模糊）与资料快照 ----------

class StockResolveItem(BaseModel):
    stock_code: str
    stock_name: Optional[str]
    instrument_kind: Literal["stock", "index"] = "stock"


class StockResolveResponse(BaseModel):
    items: list[StockResolveItem]


class StockInfoBasicBlock(BaseModel):
    stock_code: str
    stock_name: Optional[str]
    exchange: Optional[str]
    market: Optional[str]
    industry_name: Optional[str]
    region: Optional[str]
    list_date: Optional[str]


class StockInfoDailyBlock(BaseModel):
    """当前模拟日对应 stock_daily_bar 一行；phase=open 时不返回未揭晓的高、低、收、涨跌幅。"""
    trade_date: str
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    prev_close: Optional[float]
    pct_change: Optional[float]
    volume: Optional[float]
    amount: Optional[float]
    amplitude: Optional[float]
    turnover_rate: Optional[float]
    pe_ttm: Optional[float]
    pb: Optional[float]
    total_market_cap: Optional[float]
    float_market_cap: Optional[float]


class StockInfoFinancialBlock(BaseModel):
    """截至 end_date（含）最近一期财报行，字段来自 stock_financial_report。"""
    report_date: str
    report_type: Optional[str]
    roe: Optional[float]
    roe_dt: Optional[float]
    debt_to_assets: Optional[float]
    roa: Optional[float]
    gross_margin: Optional[float]
    net_margin: Optional[float]
    revenue: Optional[float]
    net_profit: Optional[float]
    eps: Optional[float]
    bps: Optional[float]


class PaperStockInfoResponse(BaseModel):
    stock_code: str
    end_date: str
    phase: str
    basic: StockInfoBasicBlock
    daily: Optional[StockInfoDailyBlock]
    financial: Optional[StockInfoFinancialBlock]
