"""指数基金专题 API Schema，与 specs/024-指数专题/contracts/index-api.md 对齐。"""
from datetime import date as dt_date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.stock import ScreeningTimeframe


class IndexScreeningItem(BaseModel):
    """专题列表单行（字段对标 ScreeningItem，价格为指数点位）。"""
    instrument_type: Literal["index"] = "index"
    code: str
    name: str | None = None
    exchange: str | None = None
    trade_date: dt_date | None = None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    hist_high: Decimal | None = None
    hist_low: Decimal | None = None
    close: Decimal | None = None
    price: Decimal | None = None
    prev_close: Decimal | None = None
    change_amount: Decimal | None = None
    pct_change: Decimal | None = None
    ma5: Decimal | None = None
    ma10: Decimal | None = None
    ma20: Decimal | None = None
    ma60: Decimal | None = None
    macd_dif: Decimal | None = None
    macd_dea: Decimal | None = None
    macd_hist: Decimal | None = None
    volume: Decimal | None = None
    amount: Decimal | None = None
    amplitude: Decimal | None = None
    turnover_rate: Decimal | None = None
    pe: Decimal | None = None
    pe_ttm: Decimal | None = None
    pe_percentile: Decimal | None = None
    pb: Decimal | None = None
    dv_ratio: Decimal | None = None
    report_date: dt_date | None = None
    revenue: Decimal | None = None
    net_profit: Decimal | None = None
    eps: Decimal | None = None
    gross_profit_margin: Decimal | None = None
    roe: Decimal | None = None
    bps: Decimal | None = None
    net_margin: Decimal | None = None
    debt_to_assets: Decimal | None = None
    updated_at: datetime | None = None


class IndexScreeningResponse(BaseModel):
    """GET /screening"""
    items: list[IndexScreeningItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    timeframe: ScreeningTimeframe = "daily"
    data_date: dt_date | None = None


class CompositionConstituentItem(BaseModel):
    """成分一行。"""
    con_code: str
    weight: float | None = None
    pe_percentile: float | None = None


class CompositionPeMeta(BaseModel):
    """指数 PE 推理元数据。"""
    formula: str = "weighted_mean_renormalize"
    participating_weight_ratio: float | None = None
    constituents_total: int = 0
    constituents_with_pe: int = 0


class CompositionResponse(BaseModel):
    """GET /{ts_code}/composition"""
    ts_code: str
    weight_table_date: dt_date | None = None
    snapshot_trade_date: dt_date | None = None
    index_pe_percentile: float | None = None
    pe_percentile_meta: CompositionPeMeta | None = None
    items: list[CompositionConstituentItem] = Field(default_factory=list)
    message: str | None = None

    @classmethod
    def from_service_bundle(cls, bundle: dict[str, Any]) -> "CompositionResponse":
        meta_raw = bundle.get("pe_percentile_meta") or {}
        meta = CompositionPeMeta(
            formula=str(meta_raw.get("formula") or "weighted_mean_renormalize"),
            participating_weight_ratio=meta_raw.get("participating_weight_ratio"),
            constituents_total=int(meta_raw.get("constituents_total") or 0),
            constituents_with_pe=int(meta_raw.get("constituents_with_pe") or 0),
        )
        raw_items = bundle.get("items") or []
        items = [
            CompositionConstituentItem(
                con_code=str(x.get("con_code") or ""),
                weight=x.get("weight"),
                pe_percentile=x.get("pe_percentile"),
            )
            for x in raw_items
        ]
        return cls(
            ts_code=str(bundle.get("ts_code") or ""),
            weight_table_date=bundle.get("weight_table_date"),
            snapshot_trade_date=bundle.get("snapshot_trade_date"),
            index_pe_percentile=bundle.get("index_pe_percentile"),
            pe_percentile_meta=meta,
            items=items,
            message=bundle.get("message"),
        )
