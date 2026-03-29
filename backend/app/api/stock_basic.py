"""股票基本信息：分页列表与手动同步。"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func
from sqlalchemy.orm import Session, aliased

from app.database import get_db
from app.models import StockBasic, StockDailyBar
from app.schemas.stock_basic import StockBasicItem, StockBasicListResponse, StockBasicSyncResponse
from app.services.stock_basic_sync_service import run_sync_basic_only
from app.services.tushare_client import TushareClientError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stock/basic", tags=["股票基本信息"])


def _decimal_to_float(v: object | None) -> float | None:
    if v is None:
        return None
    return float(v)

# 历史数据可能存为 zhitu，对外统一展示为 tushare
_LEGACY_SOURCE_MAP = {"zhitu", "zhitu_api"}


def _guess_exchange(code: str, market: str | None, exchange: str | None) -> str | None:
    if exchange:
        return exchange
    if market in {"SSE", "SZSE", "BSE"}:
        return market
    if market in {"SH", "SZ", "BJ"}:
        return {"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}.get(market)
    if code.endswith(".SH"):
        return "SSE"
    if code.endswith(".SZ"):
        return "SZSE"
    if code.endswith(".BJ"):
        return "BSE"
    return None


def _normalize_market(market: str | None, exchange: str | None) -> str | None:
    # 老数据里 market 可能存的是 SH/SZ/BJ 或交易所代码，统一不作为板块展示
    if market in {"SH", "SZ", "BJ", "SSE", "SZSE", "BSE"}:
        return None
    if exchange and market == exchange:
        return None
    return market


def _normalize_data_source(raw: str | None) -> str:
    if not raw:
        return "tushare"
    key = raw.strip().lower()
    if key in _LEGACY_SOURCE_MAP:
        return "tushare"
    return raw


def _apply_stock_basic_filters(q, *, code, name, exchange, market, industry):
    if code:
        q = q.filter(StockBasic.code.like(f"%{code.strip()}%"))
    if name:
        q = q.filter(StockBasic.name.like(f"%{name.strip()}%"))
    if exchange:
        q = q.filter(StockBasic.exchange == exchange.strip())
    if market:
        m = market.strip()
        q = q.filter(StockBasic.market == m)
    if industry:
        q = q.filter(StockBasic.industry_name.like(f"%{industry.strip()}%"))
    return q


@router.get("", response_model=StockBasicListResponse)
def list_stock_basic(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    code: str | None = Query(None, description="股票代码，模糊"),
    name: str | None = Query(None, description="名称，模糊"),
    exchange: str | None = Query(None, description="交易所（SSE/SZSE/BSE）"),
    market: str | None = Query(None, description="板块（主板/创业板/科创板/北交所）"),
    industry: str | None = Query(None, description="行业，模糊"),
    db: Session = Depends(get_db),
) -> StockBasicListResponse:
    q_count = _apply_stock_basic_filters(db.query(StockBasic), code=code, name=name, exchange=exchange, market=market, industry=industry)
    total = q_count.count()

    latest_td_sq = (
        db.query(
            StockDailyBar.stock_code.label("code_key"),
            func.max(StockDailyBar.trade_date).label("latest_td"),
        )
        .group_by(StockDailyBar.stock_code)
        .subquery()
    )
    BarLatest = aliased(StockDailyBar)
    qi = (
        db.query(StockBasic, BarLatest.cum_hist_high, BarLatest.cum_hist_low, BarLatest.updated_at)
        .outerjoin(latest_td_sq, latest_td_sq.c.code_key == StockBasic.code)
        .outerjoin(
            BarLatest,
            and_(
                BarLatest.stock_code == StockBasic.code,
                BarLatest.trade_date == latest_td_sq.c.latest_td,
            ),
        )
    )
    qi = _apply_stock_basic_filters(qi, code=code, name=name, exchange=exchange, market=market, industry=industry)
    rows = (
        qi.order_by(StockBasic.code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    last_synced_at = db.query(func.max(StockBasic.synced_at)).scalar()
    items = [
        StockBasicItem(
            code=r.code,
            name=r.name,
            exchange=_guess_exchange(r.code, r.market, r.exchange),
            market=_normalize_market(r.market, r.exchange),
            industry_name=r.industry_name,
            region=r.region,
            list_date=r.list_date,
            synced_at=r.synced_at,
            data_source=_normalize_data_source(r.data_source),
            hist_high=_decimal_to_float(ch),
            hist_low=_decimal_to_float(cl),
            hist_extrema_computed_at=bar_u,
        )
        for r, ch, cl, bar_u in rows
    ]
    return StockBasicListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        last_synced_at=last_synced_at,
    )


@router.post("/sync", response_model=StockBasicSyncResponse)
def trigger_stock_basic_sync(db: Session = Depends(get_db)) -> StockBasicSyncResponse:
    """请求内同步执行，完成后返回写入条数。"""
    try:
        stats = run_sync_basic_only(db)
    except TushareClientError as e:
        logger.exception("stock_basic 同步失败: %s", e)
        raise HTTPException(status_code=502, detail=f"拉取股票列表失败：{e}") from e
    except Exception as e:
        logger.exception("stock_basic 同步失败: %s", e)
        raise HTTPException(status_code=500, detail=f"同步失败：{e}") from e
    n = stats.get("stock_basic", 0)
    return StockBasicSyncResponse(
        status="ok",
        message=f"已写入 {n} 条股票基本信息",
        stock_basic=n,
    )
