"""历史模拟交易 API 路由。

路由前缀：/api/paper-trading
端点详见 specs/020-历史模拟交易/contracts/api.md。
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.paper_trading import (
    BuyRequest,
    ChartDataResponse,
    CreateSessionRequest,
    EndSessionResponse,
    NextDayResponse,
    OrderListResponse,
    PaperStockInfoResponse,
    PhaseResponse,
    RecommendResponse,
    ScreenResponse,
    SellRequest,
    SessionListResponse,
    SessionResponse,
    StockResolveResponse,
    TradingDatesResponse,
)
from app.services import paper_trading_service as svc

router = APIRouter(prefix="/paper-trading", tags=["paper-trading"])


# ---------- 会话管理 ----------

@router.post("/sessions", response_model=SessionResponse, status_code=201)
def api_create_session(body: CreateSessionRequest, db: Session = Depends(get_db)):
    """创建模拟交易会话。"""
    return svc.create_session(db, body.start_date, body.initial_cash, body.name)


@router.get("/sessions", response_model=SessionListResponse)
def api_list_sessions(
    status: Optional[str] = Query(default=None, description="active / ended"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """查询会话列表。"""
    return svc.list_sessions(db, status, page, page_size)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def api_get_session(session_id: str, db: Session = Depends(get_db)):
    """查询会话详情（含持仓聚合）。"""
    return svc.get_session_detail(db, session_id)


@router.post("/sessions/{session_id}/advance-to-close", response_model=PhaseResponse)
def api_advance_to_close(session_id: str, db: Session = Depends(get_db)):
    """将当日 phase 从 open 推进到 close，持仓市值改用收盘价重算。"""
    return svc.advance_to_close(db, session_id)


@router.post("/sessions/{session_id}/next-day", response_model=NextDayResponse)
def api_next_day(session_id: str, db: Session = Depends(get_db)):
    """进入下一交易日（仅 phase=close 时允许）。"""
    return svc.next_day(db, session_id)


@router.post("/sessions/{session_id}/end", response_model=EndSessionResponse)
def api_end_session(session_id: str, db: Session = Depends(get_db)):
    """结束会话。"""
    return svc.end_session(db, session_id)


# ---------- 交易操作 ----------

@router.post("/sessions/{session_id}/buy")
def api_buy(session_id: str, body: BuyRequest, db: Session = Depends(get_db)):
    """买入股票。"""
    return svc.buy(db, session_id, body.stock_code, body.price, body.quantity)


@router.post("/sessions/{session_id}/sell")
def api_sell(session_id: str, body: SellRequest, db: Session = Depends(get_db)):
    """卖出股票。"""
    return svc.sell(db, session_id, body.stock_code, body.price, body.quantity)


@router.get("/sessions/{session_id}/orders", response_model=OrderListResponse)
def api_list_orders(
    session_id: str,
    order_type: Optional[str] = Query(default=None, description="buy / sell"),
    stock_code: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    sort: str = Query(default="desc", description="按订单创建时间：asc 正序 / desc 倒序"),
    db: Session = Depends(get_db),
):
    """查询交易记录。"""
    sort_norm = "asc" if (sort or "").lower() == "asc" else "desc"
    return svc.list_orders(db, session_id, order_type, stock_code, page, page_size, sort_norm)


# ---------- 图表与选股 ----------

@router.get("/chart-data", response_model=ChartDataResponse)
def api_chart_data(
    stock_code: str = Query(...),
    end_date: date = Query(..., description="当前模拟日期"),
    phase: str = Query(..., description="open / close"),
    period: str = Query(default="daily", description="daily / weekly / monthly"),
    full_history: bool = Query(
        default=True,
        description="true：自库中该股最早一根 K（至 end_date）全量返回，便于长期趋势与周/月均线；false：仅最近 limit 根",
    ),
    limit: int = Query(default=300, ge=1, le=500, description="仅 full_history=false 时生效"),
    db: Session = Depends(get_db),
):
    """获取股票图表数据。phase=open 时最新 K 线 high/low/close 返回 null。"""
    return svc.get_chart_data(db, stock_code, end_date, phase, period, limit, full_history=full_history)


@router.get("/resolve-stock", response_model=StockResolveResponse)
def api_resolve_stock(
    q: str = Query(..., description="股票代码或名称片段"),
    limit: int = Query(default=30, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """解析用户输入：精确代码优先，否则代码/名称模糊匹配。"""
    return svc.resolve_stock_query(db, q, limit)


@router.get("/stock-info", response_model=PaperStockInfoResponse)
def api_stock_info(
    stock_code: str = Query(...),
    end_date: date = Query(..., description="当前模拟日期"),
    phase: str = Query(..., description="open / close"),
    db: Session = Depends(get_db),
):
    """股票基本信息 + 当前模拟日日线（日表）+ 截至模拟日最近一期经营/财务指标。"""
    return svc.get_stock_info_snapshot(db, stock_code, end_date, phase)


@router.get("/recommend", response_model=RecommendResponse)
def api_recommend(
    trade_date: date = Query(...),
    phase: str = Query(..., description="open / close"),
    count: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """随机推荐当日有效股票。"""
    return svc.recommend_stocks(db, trade_date, phase, count)


@router.get("/screen", response_model=ScreenResponse)
def api_screen(
    trade_date: date = Query(...),
    pct_change_min: Optional[float] = Query(default=None),
    pct_change_max: Optional[float] = Query(default=None),
    volume_min: Optional[float] = Query(default=None),
    volume_max: Optional[float] = Query(default=None),
    ma_golden_cross: Optional[str] = Query(default=None, description="ma5_ma10 / ma5_ma20"),
    macd_golden_cross: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """自定义筛选当日股票。"""
    return svc.screen_stocks(
        db, trade_date,
        pct_change_min, pct_change_max,
        volume_min, volume_max,
        ma_golden_cross, macd_golden_cross,
        page, page_size,
    )


@router.get("/trading-dates", response_model=TradingDatesResponse)
def api_trading_dates(
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
):
    """获取指定范围内的交易日列表。"""
    return svc.get_trading_dates(db, start, end)
