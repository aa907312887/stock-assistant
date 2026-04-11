"""历史模拟交易业务逻辑服务。

负责：会话管理、买入/卖出（含 FIFO、T+1、涨跌停验证）、
推进到收盘、进入下一交易日、图表数据、推荐/筛选股票。
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.market_temperature_daily import MarketTemperatureDaily
from app.models.paper_trading import (
    PaperTradingOrder,
    PaperTradingPosition,
    PaperTradingSession,
)
from app.models.stock_daily_bar import StockDailyBar
from app.models.stock_monthly_bar import StockMonthlyBar
from app.models.stock_weekly_bar import StockWeeklyBar
from app.models.stock_basic import StockBasic
from app.models.stock_financial_report import StockFinancialReport
from app.services.market_temperature.constants import FORMULA_VERSION
from app.schemas.paper_trading import (
    ChartBar,
    ChartDataResponse,
    ClosedStockSummary,
    NextDayResponse,
    OrderListResponse,
    OrderResponse,
    PaperStockInfoResponse,
    PhaseResponse,
    PositionSummary,
    RecommendResponse,
    ScreenResponse,
    SessionListItem,
    SessionListResponse,
    SessionResponse,
    StockInfoBasicBlock,
    StockInfoDailyBlock,
    StockInfoFinancialBlock,
    StockQuote,
    StockResolveItem,
    StockResolveResponse,
    TradingDatesResponse,
)

logger = logging.getLogger(__name__)

# ---------- 常量 ----------
BUY_COMMISSION_RATE = Decimal("0.0003")   # 买入手续费 0.03%
SELL_COMMISSION_RATE = Decimal("0.0013")  # 卖出手续费 0.13%（含印花税）
MIN_COMMISSION = Decimal("5.0")           # 最低手续费 5 元
LIMIT_RATE = Decimal("0.10")             # 涨跌停幅度 10%


# ---------- 内部工具 ----------

def _gen_session_id() -> str:
    return f"pt-{uuid.uuid4().hex[:8]}"


def _calc_commission(amount: Decimal, rate: Decimal) -> Decimal:
    raw = (amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return max(raw, MIN_COMMISSION)


def _normalize_ts_code(code: str) -> str:
    """统一 ts_code 大小写，避免订单与持仓中代码写法不一致导致汇总遗漏。"""
    s = (code or "").strip()
    if not s:
        return s
    if "." in s:
        left, right = s.rsplit(".", 1)
        return f"{left.strip().upper()}.{right.strip().upper()}"
    return s.upper()


def _buy_cost_from_closed_batches(db: Session, session_id: str, stock_code: str) -> Decimal:
    """已关闭批次上的买入总成本（∑ 成交价×数量 + 买佣），订单漏记买入时可作兜底。"""
    total = Decimal(0)
    rows = (
        db.query(PaperTradingPosition)
        .filter(
            PaperTradingPosition.session_id == session_id,
            PaperTradingPosition.stock_code == stock_code,
            PaperTradingPosition.status == "closed",
        )
        .all()
    )
    for p in rows:
        total += Decimal(str(p.buy_price)) * int(p.quantity) + Decimal(str(p.commission))
    return total


def _get_session_or_404(db: Session, session_id: str) -> PaperTradingSession:
    session = db.query(PaperTradingSession).filter(
        PaperTradingSession.session_id == session_id
    ).first()
    if session is None:
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": "模拟会话不存在"})
    return session


def _session_is_ended(session: PaperTradingSession) -> bool:
    """是否已结束。仅当 status 明确为 ended 时为真；NULL/空 视为未结束（与库中旧数据一致）。"""
    return (session.status or "").strip().lower() == "ended"


def _get_daily_bar(db: Session, stock_code: str, trade_date: date) -> StockDailyBar:
    """查询当日日线数据，不存在则说明停牌或无数据。"""
    bar = db.query(StockDailyBar).filter(
        StockDailyBar.stock_code == stock_code,
        StockDailyBar.trade_date == trade_date,
    ).first()
    if bar is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "STOCK_SUSPENDED", "message": f"股票 {stock_code} 当日停牌或无数据"},
        )
    return bar


def _prev_trading_date_before(db: Session, sim_day: date) -> date | None:
    """当前模拟日的前一交易日（全市场日线中存在且早于 sim_day 的最大 trade_date）。"""
    return db.query(func.max(StockDailyBar.trade_date)).filter(StockDailyBar.trade_date < sim_day).scalar()


def _market_temperature_prev_trading_day(
    db: Session, sim_day: date
) -> tuple[date | None, float | None, str | None]:
    """模拟界面展示用：取「前一交易日」收盘后的大盘温度，而非模拟当日（避免当日未收盘却展示当日温度）。

    返回：(温度对应的交易日, 分数, 级别)；无上一交易日或库中无记录时相应为 None。
    """
    prev_td = _prev_trading_date_before(db, sim_day)
    if prev_td is None:
        return None, None, None
    row = (
        db.query(MarketTemperatureDaily.temperature_score, MarketTemperatureDaily.temperature_level)
        .filter(
            MarketTemperatureDaily.trade_date == prev_td,
            MarketTemperatureDaily.formula_version == FORMULA_VERSION,
        )
        .first()
    )
    if row is None:
        return prev_td, None, None
    return prev_td, float(row.temperature_score), row.temperature_level


def _calc_limits(prev_close: Decimal) -> tuple[Decimal, Decimal]:
    """计算涨停价和跌停价（±10%，保留两位小数）。"""
    limit_up = (prev_close * (1 + LIMIT_RATE)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    limit_down = (prev_close * (1 - LIMIT_RATE)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return limit_up, limit_down


def _validate_price(price: Decimal, prev_close: Decimal) -> None:
    """验证价格在涨跌停范围内。"""
    limit_up, limit_down = _calc_limits(prev_close)
    if price > limit_up or price < limit_down:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PRICE_OUT_OF_LIMIT",
                "message": f"价格超出涨跌停范围（{float(limit_down)} ~ {float(limit_up)}）",
                "limit_up": float(limit_up),
                "limit_down": float(limit_down),
            },
        )


def _build_position_summaries(
    db: Session,
    session: PaperTradingSession,
) -> list[PositionSummary]:
    """按股票聚合持仓批次，返回持仓汇总列表。"""
    positions = (
        db.query(PaperTradingPosition)
        .filter(
            PaperTradingPosition.session_id == session.session_id,
            PaperTradingPosition.status == "holding",
        )
        .all()
    )

    # 按 stock_code 聚合
    agg: dict[str, dict] = {}
    for pos in positions:
        code = pos.stock_code
        if code not in agg:
            agg[code] = {
                "stock_name": pos.stock_name,
                "batches": [],
            }
        agg[code]["batches"].append(pos)

    summaries = []
    for code, info in agg.items():
        batches = info["batches"]
        total_qty = sum(b.remaining_quantity for b in batches)
        # 可卖数量：排除当日买入批次（T+1）
        can_sell_qty = sum(
            b.remaining_quantity for b in batches if b.buy_date != session.current_date
        )
        # 加权均价
        total_cost = sum(b.buy_price * b.remaining_quantity for b in batches)
        avg_cost = float(total_cost / total_qty) if total_qty else 0.0

        # 当前参考价：open 阶段用开盘价，close 阶段用收盘价
        bar = db.query(StockDailyBar).filter(
            StockDailyBar.stock_code == code,
            StockDailyBar.trade_date == session.current_date,
        ).first()

        current_price = None
        market_value = None
        profit_loss = None
        profit_loss_pct = None

        if bar:
            if session.current_phase == "open" and bar.open is not None:
                current_price = float(bar.open)
            elif session.current_phase == "close" and bar.close is not None:
                current_price = float(bar.close)

            if current_price is not None:
                market_value = current_price * total_qty
                profit_loss = market_value - float(total_cost)
                profit_loss_pct = profit_loss / float(total_cost) if total_cost else 0.0

        summaries.append(PositionSummary(
            stock_code=code,
            stock_name=info["stock_name"],
            total_quantity=total_qty,
            avg_cost_price=avg_cost,
            current_price=current_price,
            market_value=market_value,
            profit_loss=profit_loss,
            profit_loss_pct=profit_loss_pct,
            can_sell_quantity=can_sell_qty,
        ))

    return summaries


def _realized_pnl_by_stock_codes(
    db: Session, session_id: str, stock_codes: list[str]
) -> dict[str, tuple[float, float]]:
    """按股票汇总本会话已实现盈亏：卖出 ∑(amount−commission) − 买入 ∑(amount+commission)；比例=盈亏/买入总成本。"""
    if not stock_codes:
        return {}
    # 会话内全部订单再在内存中按代码匹配，避免 IN 条件与大小写/空白等导致漏单
    norm_to_canonical: dict[str, str] = {}
    for c in stock_codes:
        n = _normalize_ts_code(c)
        if n not in norm_to_canonical:
            norm_to_canonical[n] = c

    orders = (
        db.query(PaperTradingOrder)
        .filter(PaperTradingOrder.session_id == session_id)
        .all()
    )
    buy_cost = {c: Decimal(0) for c in stock_codes}
    sell_proceeds = {c: Decimal(0) for c in stock_codes}
    for o in orders:
        canon = norm_to_canonical.get(_normalize_ts_code(o.stock_code))
        if canon is None:
            continue
        amt = Decimal(str(o.amount))
        comm = Decimal(str(o.commission))
        ot = (o.order_type or "").strip().lower()
        if ot == "buy":
            buy_cost[canon] += amt + comm
        elif ot == "sell":
            sell_proceeds[canon] += amt - comm

    out: dict[str, tuple[float, float]] = {}
    for code in stock_codes:
        tb_ord = buy_cost[code]
        sp = sell_proceeds[code]
        # 订单侧未统计到买入成本时，用已关闭批次还原（与 list_orders 展示仍可对齐）
        tb_pos = _buy_cost_from_closed_batches(db, session_id, code)
        tb = tb_ord if tb_ord > 0 else tb_pos
        pl_dec = sp - tb
        pl = float(pl_dec)
        pct = float(pl_dec / tb) if tb > 0 else 0.0
        out[code] = (pl, pct)
    return out


def _build_closed_stock_summaries(db: Session, session: PaperTradingSession) -> list[ClosedStockSummary]:
    """当前无 holding 但存在 closed 批次的股票代码（曾全部卖出，便于前端「已清仓」列表）。"""
    holding_codes = {
        row[0]
        for row in db.query(PaperTradingPosition.stock_code)
        .filter(
            PaperTradingPosition.session_id == session.session_id,
            PaperTradingPosition.status == "holding",
        )
        .distinct()
        .all()
    }
    closed_rows = (
        db.query(PaperTradingPosition)
        .filter(
            PaperTradingPosition.session_id == session.session_id,
            PaperTradingPosition.status == "closed",
        )
        .order_by(PaperTradingPosition.stock_code.asc(), PaperTradingPosition.id.asc())
        .all()
    )
    by_code: dict[str, dict] = {}
    for p in closed_rows:
        if p.stock_code in holding_codes:
            continue
        if p.stock_code not in by_code:
            by_code[p.stock_code] = {"stock_name": p.stock_name, "count": 0}
        by_code[p.stock_code]["count"] += 1
    codes_sorted = sorted(by_code.keys())
    pnl_map = _realized_pnl_by_stock_codes(db, session.session_id, codes_sorted)
    return [
        ClosedStockSummary(
            stock_code=code,
            stock_name=info["stock_name"],
            closed_batch_count=info["count"],
            realized_profit_loss=pnl_map.get(code, (0.0, 0.0))[0],
            realized_profit_loss_pct=pnl_map.get(code, (0.0, 0.0))[1],
        )
        for code, info in sorted(by_code.items(), key=lambda x: x[0])
    ]


def _build_session_response(db: Session, session: PaperTradingSession) -> SessionResponse:
    positions = _build_position_summaries(db, session)
    closed_stocks = _build_closed_stock_summaries(db, session)
    holdings_value = sum(p.market_value or 0.0 for p in positions)
    total_asset = float(session.available_cash) + holdings_value
    initial = float(session.initial_cash)
    total_pl = total_asset - initial
    total_pl_pct = total_pl / initial if initial else 0.0

    ref_d, temp_score, temp_level = _market_temperature_prev_trading_day(db, session.current_date)

    # 旧数据或异常空值时按 active 返回，避免前端误判为已结束
    st = (session.status or "").strip().lower() or "active"
    if st not in ("active", "ended"):
        st = "active"

    return SessionResponse(
        session_id=session.session_id,
        name=session.name,
        start_date=session.start_date,
        current_date=session.current_date,
        current_phase=session.current_phase,
        initial_cash=float(session.initial_cash),
        available_cash=float(session.available_cash),
        status=st,
        positions=positions,
        closed_stocks=closed_stocks,
        total_asset=total_asset,
        total_profit_loss=total_pl,
        total_profit_loss_pct=total_pl_pct,
        created_at=session.created_at,
        market_temp_ref_date=ref_d,
        market_temp_score=temp_score,
        market_temp_level=temp_level,
    )


# ---------- 公开服务函数 ----------

def create_session(
    db: Session,
    start_date: date,
    initial_cash: float,
    name: Optional[str],
) -> SessionResponse:
    """创建模拟交易会话。验证 start_date 是交易日，写入数据库。"""
    # 验证是否为交易日
    bar_count = db.query(func.count(StockDailyBar.id)).filter(
        StockDailyBar.trade_date == start_date
    ).scalar()
    if not bar_count:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_DATE", "message": f"{start_date} 不是交易日或超出数据范围"},
        )

    session_id = _gen_session_id()
    cash = Decimal(str(initial_cash))
    session = PaperTradingSession(
        session_id=session_id,
        name=name,
        start_date=start_date,
        current_date=start_date,
        current_phase="open",
        initial_cash=cash,
        available_cash=cash,
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info("创建模拟交易会话: session_id=%s, start_date=%s", session_id, start_date)
    return _build_session_response(db, session)


def list_sessions(
    db: Session,
    status: Optional[str],
    page: int,
    page_size: int,
) -> SessionListResponse:
    """查询会话列表。"""
    q = db.query(PaperTradingSession)
    if status:
        q = q.filter(PaperTradingSession.status == status)
    total = q.count()
    sessions = q.order_by(PaperTradingSession.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for s in sessions:
        positions = _build_position_summaries(db, s)
        holdings_value = sum(p.market_value or 0.0 for p in positions)
        total_asset = float(s.available_cash) + holdings_value
        items.append(SessionListItem(
            session_id=s.session_id,
            name=s.name,
            start_date=s.start_date,
            current_date=s.current_date,
            current_phase=s.current_phase,
            initial_cash=float(s.initial_cash),
            available_cash=float(s.available_cash),
            total_asset=total_asset,
            status=s.status,
            created_at=s.created_at,
        ))
    return SessionListResponse(total=total, page=page, page_size=page_size, items=items)


def get_session_detail(db: Session, session_id: str) -> SessionResponse:
    """查询会话详情（含持仓聚合）。"""
    session = _get_session_or_404(db, session_id)
    return _build_session_response(db, session)


def advance_to_close(db: Session, session_id: str) -> PhaseResponse:
    """将当日 phase 从 open 推进到 close，持仓市值改用收盘价重算。"""
    session = _get_session_or_404(db, session_id)
    if _session_is_ended(session):
        raise HTTPException(status_code=400, detail={"code": "SESSION_NOT_ACTIVE", "message": "会话已结束"})
    if session.current_phase == "close":
        raise HTTPException(status_code=400, detail={"code": "ALREADY_CLOSED", "message": "当日已处于收盘状态"})

    session.current_phase = "close"
    db.commit()
    db.refresh(session)

    positions = _build_position_summaries(db, session)
    closed_stocks = _build_closed_stock_summaries(db, session)
    ref_d, temp_score, temp_level = _market_temperature_prev_trading_day(db, session.current_date)
    return PhaseResponse(
        current_date=session.current_date,
        current_phase=session.current_phase,
        available_cash=float(session.available_cash),
        positions=positions,
        closed_stocks=closed_stocks,
        market_temp_ref_date=ref_d,
        market_temp_score=temp_score,
        market_temp_level=temp_level,
    )


def next_day(db: Session, session_id: str) -> NextDayResponse:
    """进入下一交易日，仅在 phase=close 时允许。"""
    session = _get_session_or_404(db, session_id)
    if _session_is_ended(session):
        raise HTTPException(status_code=400, detail={"code": "SESSION_NOT_ACTIVE", "message": "会话已结束"})
    if session.current_phase != "close":
        raise HTTPException(
            status_code=400,
            detail={"code": "PHASE_NOT_CLOSE", "message": "请先推进到收盘，再进入下一交易日"},
        )

    # 查询下一个交易日
    next_date = db.query(func.min(StockDailyBar.trade_date)).filter(
        StockDailyBar.trade_date > session.current_date
    ).scalar()
    if next_date is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "NO_MORE_DATES", "message": "已到达数据最新日期，无法继续推进"},
        )

    prev_date = session.current_date
    session.current_date = next_date
    session.current_phase = "open"
    db.commit()
    db.refresh(session)

    positions = _build_position_summaries(db, session)
    closed_stocks = _build_closed_stock_summaries(db, session)
    ref_d, temp_score, temp_level = _market_temperature_prev_trading_day(db, session.current_date)
    return NextDayResponse(
        previous_date=prev_date,
        current_date=session.current_date,
        current_phase=session.current_phase,
        available_cash=float(session.available_cash),
        positions=positions,
        closed_stocks=closed_stocks,
        market_temp_ref_date=ref_d,
        market_temp_score=temp_score,
        market_temp_level=temp_level,
    )


def end_session(db: Session, session_id: str) -> dict:
    """结束会话。"""
    session = _get_session_or_404(db, session_id)
    session.status = "ended"
    db.commit()
    return {"session_id": session_id, "status": "ended"}


def buy(
    db: Session,
    session_id: str,
    stock_code: str,
    price: float,
    quantity: int,
) -> dict:
    """买入股票。验证停牌、涨跌停、资金，FIFO 写入持仓批次和交易记录。"""
    session = _get_session_or_404(db, session_id)
    if _session_is_ended(session):
        raise HTTPException(status_code=400, detail={"code": "SESSION_NOT_ACTIVE", "message": "会话已结束"})

    bar = _get_daily_bar(db, stock_code, session.current_date)

    if bar.prev_close is None:
        raise HTTPException(status_code=400, detail={"code": "NO_PREV_CLOSE", "message": "缺少前收盘价，无法验证涨跌停"})

    price_dec = Decimal(str(price))
    _validate_price(price_dec, bar.prev_close)

    amount = price_dec * quantity
    commission = _calc_commission(amount, BUY_COMMISSION_RATE)
    total_cost = amount + commission

    if session.available_cash < total_cost:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INSUFFICIENT_CASH",
                "message": "资金不足，无法完成买入",
                "required": float(total_cost),
                "available": float(session.available_cash),
            },
        )

    stock_name = bar.stock_code  # 用 stock_code 兜底，前端可从 stock_basic 获取名称
    # 尝试从 stock_basic 获取股票名称
    try:
        basic = db.query(StockBasic).filter(StockBasic.code == stock_code).first()
        if basic:
            stock_name = basic.name
    except Exception:
        pass

    position = PaperTradingPosition(
        session_id=session_id,
        stock_code=stock_code,
        stock_name=stock_name,
        buy_date=session.current_date,
        buy_price=price_dec,
        quantity=quantity,
        remaining_quantity=quantity,
        commission=commission,
        status="holding",
    )
    db.add(position)
    db.flush()  # 获取 position.id

    new_cash = session.available_cash - total_cost
    order = PaperTradingOrder(
        session_id=session_id,
        order_type="buy",
        stock_code=stock_code,
        stock_name=stock_name,
        trade_date=session.current_date,
        price=price_dec,
        quantity=quantity,
        amount=amount,
        commission=commission,
        cash_after=new_cash,
        position_id=None,
    )
    db.add(order)
    session.available_cash = new_cash
    db.commit()
    db.refresh(order)

    logger.info("买入: session=%s stock=%s price=%s qty=%s", session_id, stock_code, price, quantity)
    return {
        "order_id": order.id,
        "order_type": "buy",
        "stock_code": stock_code,
        "stock_name": stock_name,
        "trade_date": str(session.current_date),
        "price": float(price_dec),
        "quantity": quantity,
        "amount": float(amount),
        "commission": float(commission),
        "cash_after": float(new_cash),
    }


def sell(
    db: Session,
    session_id: str,
    stock_code: str,
    price: float,
    quantity: int,
) -> dict:
    """卖出股票。验证停牌、涨跌停、T+1，FIFO 扣减持仓，写入交易记录。"""
    session = _get_session_or_404(db, session_id)
    if _session_is_ended(session):
        raise HTTPException(status_code=400, detail={"code": "SESSION_NOT_ACTIVE", "message": "会话已结束"})

    bar = _get_daily_bar(db, stock_code, session.current_date)

    if bar.prev_close is None:
        raise HTTPException(status_code=400, detail={"code": "NO_PREV_CLOSE", "message": "缺少前收盘价，无法验证涨跌停"})

    price_dec = Decimal(str(price))
    _validate_price(price_dec, bar.prev_close)

    # 查询可卖批次（排除当日买入，按 buy_date ASC, id ASC 排序 = FIFO）
    sellable_batches = (
        db.query(PaperTradingPosition)
        .filter(
            PaperTradingPosition.session_id == session_id,
            PaperTradingPosition.stock_code == stock_code,
            PaperTradingPosition.status == "holding",
            PaperTradingPosition.buy_date != session.current_date,
        )
        .order_by(PaperTradingPosition.buy_date.asc(), PaperTradingPosition.id.asc())
        .all()
    )

    available_qty = sum(b.remaining_quantity for b in sellable_batches)
    if available_qty == 0:
        raise HTTPException(
            status_code=400,
            detail={"code": "T1_RESTRICTION", "message": "T+1 限制：当日买入的股票次日才能卖出"},
        )
    if quantity > available_qty:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INSUFFICIENT_POSITION",
                "message": f"卖出数量不能超过可卖数量，当前最多可卖 {available_qty} 股",
                "available_quantity": available_qty,
            },
        )

    # FIFO 扣减
    first_position_id = sellable_batches[0].id
    remaining_to_sell = quantity
    for batch in sellable_batches:
        if remaining_to_sell <= 0:
            break
        deduct = min(batch.remaining_quantity, remaining_to_sell)
        batch.remaining_quantity -= deduct
        if batch.remaining_quantity == 0:
            batch.status = "closed"
        remaining_to_sell -= deduct

    amount = price_dec * quantity
    commission = _calc_commission(amount, SELL_COMMISSION_RATE)
    new_cash = session.available_cash + amount - commission

    stock_name = stock_code
    try:
        basic = db.query(StockBasic).filter(StockBasic.code == stock_code).first()
        if basic:
            stock_name = basic.name
    except Exception:
        pass

    order = PaperTradingOrder(
        session_id=session_id,
        order_type="sell",
        stock_code=stock_code,
        stock_name=stock_name,
        trade_date=session.current_date,
        price=price_dec,
        quantity=quantity,
        amount=amount,
        commission=commission,
        cash_after=new_cash,
        position_id=first_position_id,
    )
    db.add(order)
    session.available_cash = new_cash
    db.commit()
    db.refresh(order)

    logger.info("卖出: session=%s stock=%s price=%s qty=%s", session_id, stock_code, price, quantity)
    return {
        "order_id": order.id,
        "order_type": "sell",
        "stock_code": stock_code,
        "stock_name": stock_name,
        "trade_date": str(session.current_date),
        "price": float(price_dec),
        "quantity": quantity,
        "amount": float(amount),
        "commission": float(commission),
        "cash_after": float(new_cash),
    }


def list_orders(
    db: Session,
    session_id: str,
    order_type: Optional[str],
    stock_code: Optional[str],
    page: int,
    page_size: int,
    sort: str = "desc",
) -> OrderListResponse:
    """查询交易记录。默认按 created_at 倒序；sort=asc 时正序（适合时间线展示）。"""
    _get_session_or_404(db, session_id)
    q = db.query(PaperTradingOrder).filter(PaperTradingOrder.session_id == session_id)
    if order_type:
        q = q.filter(PaperTradingOrder.order_type == order_type)
    if stock_code:
        q = q.filter(PaperTradingOrder.stock_code == stock_code)
    total = q.count()
    order_col = PaperTradingOrder.created_at.asc() if sort == "asc" else PaperTradingOrder.created_at.desc()
    records = q.order_by(order_col, PaperTradingOrder.id.asc() if sort == "asc" else PaperTradingOrder.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [
        OrderResponse(
            order_id=r.id,
            order_type=r.order_type,
            stock_code=r.stock_code,
            stock_name=r.stock_name,
            trade_date=r.trade_date,
            price=float(r.price),
            quantity=r.quantity,
            amount=float(r.amount),
            commission=float(r.commission),
            cash_after=float(r.cash_after),
            created_at=r.created_at,
        )
        for r in records
    ]
    return OrderListResponse(total=total, page=page, page_size=page_size, items=items)


def get_chart_data(
    db: Session,
    stock_code: str,
    end_date: date,
    phase: str,
    period: str,
    limit: int,
    *,
    full_history: bool = True,
) -> ChartDataResponse:
    """获取股票图表数据。

    - full_history=True（默认）：日/周/月均为「库中该股最早一根 ≤ end_date 的周期 K」起至 end_date，全量升序返回，便于长期趋势线与周/月 MA/MACD 前置数据。
    - full_history=False：仅最近 limit 根（原行为）。
    phase=open 时最新一根按各周期规则掩码未揭晓的 OHLCV、涨跌幅与 MACD。
    """
    stock_name = stock_code
    try:
        basic = db.query(StockBasic).filter(StockBasic.code == stock_code).first()
        if basic:
            stock_name = basic.name
    except Exception:
        pass

    bars: list[ChartBar] = []
    open_price = None
    close_price = None
    limit_up = None
    limit_down = None

    if period == "weekly":
        q_w = db.query(StockWeeklyBar).filter(
            StockWeeklyBar.stock_code == stock_code,
            StockWeeklyBar.trade_week_end <= end_date,
        )
        if full_history:
            rows = q_w.order_by(StockWeeklyBar.trade_week_end.asc()).all()
        else:
            rows = q_w.order_by(StockWeeklyBar.trade_week_end.desc()).limit(limit).all()
            rows = list(reversed(rows))
        n = len(rows)
        for i, r in enumerate(rows):
            is_latest = i == n - 1
            # 仅返回交易日 ≤ end_date 的周线；最新一根且开盘 phase 且周期末端=模拟日时，与日线一致掩码未揭晓字段
            hide = is_latest and phase == "open" and r.trade_week_end == end_date
            bars.append(ChartBar(
                date=str(r.trade_week_end),
                open=float(r.open) if r.open is not None else None,
                high=None if hide else (float(r.high) if r.high is not None else None),
                low=None if hide else (float(r.low) if r.low is not None else None),
                close=None if hide else (float(r.close) if r.close is not None else None),
                volume=None if hide else (float(r.volume) if r.volume is not None else None),
                prev_close=None,
                pct_change=None if hide else (float(r.pct_change) if r.pct_change is not None else None),
                ma5=float(r.ma5) if r.ma5 else None,
                ma10=float(r.ma10) if r.ma10 else None,
                ma20=float(r.ma20) if r.ma20 else None,
                ma60=float(r.ma60) if r.ma60 else None,
                macd_dif=None if hide else (float(r.macd_dif) if r.macd_dif is not None else None),
                macd_dea=None if hide else (float(r.macd_dea) if r.macd_dea is not None else None),
                macd_hist=None if hide else (float(r.macd_hist) if r.macd_hist is not None else None),
            ))

    elif period == "monthly":
        q_m = db.query(StockMonthlyBar).filter(
            StockMonthlyBar.stock_code == stock_code,
            StockMonthlyBar.trade_month_end <= end_date,
        )
        if full_history:
            rows = q_m.order_by(StockMonthlyBar.trade_month_end.asc()).all()
        else:
            rows = q_m.order_by(StockMonthlyBar.trade_month_end.desc()).limit(limit).all()
            rows = list(reversed(rows))
        n = len(rows)
        for i, r in enumerate(rows):
            is_latest = i == n - 1
            hide = is_latest and phase == "open" and r.trade_month_end == end_date
            bars.append(ChartBar(
                date=str(r.trade_month_end),
                open=float(r.open) if r.open is not None else None,
                high=None if hide else (float(r.high) if r.high is not None else None),
                low=None if hide else (float(r.low) if r.low is not None else None),
                close=None if hide else (float(r.close) if r.close is not None else None),
                volume=None if hide else (float(r.volume) if r.volume is not None else None),
                prev_close=None,
                pct_change=None if hide else (float(r.pct_change) if r.pct_change is not None else None),
                ma5=float(r.ma5) if r.ma5 else None,
                ma10=float(r.ma10) if r.ma10 else None,
                ma20=float(r.ma20) if r.ma20 else None,
                ma60=float(r.ma60) if r.ma60 else None,
                macd_dif=None if hide else (float(r.macd_dif) if r.macd_dif is not None else None),
                macd_dea=None if hide else (float(r.macd_dea) if r.macd_dea is not None else None),
                macd_hist=None if hide else (float(r.macd_hist) if r.macd_hist is not None else None),
            ))

    else:  # daily
        q_d = db.query(StockDailyBar).filter(
            StockDailyBar.stock_code == stock_code,
            StockDailyBar.trade_date <= end_date,
        )
        if full_history:
            rows = q_d.order_by(StockDailyBar.trade_date.asc()).all()
        else:
            rows = q_d.order_by(StockDailyBar.trade_date.desc()).limit(limit).all()
            rows = list(reversed(rows))
        for r in rows:
            is_latest = (r.trade_date == end_date)
            # phase=open 时，最新一根 K 线隐藏 high/low/close/macd
            hide = is_latest and phase == "open"
            bars.append(ChartBar(
                date=str(r.trade_date),
                open=float(r.open) if r.open else None,
                high=None if hide else (float(r.high) if r.high else None),
                low=None if hide else (float(r.low) if r.low else None),
                close=None if hide else (float(r.close) if r.close else None),
                volume=None if hide else (float(r.volume) if r.volume else None),
                prev_close=float(r.prev_close) if r.prev_close else None,
                pct_change=None if hide else (float(r.pct_change) if r.pct_change else None),
                ma5=float(r.ma5) if r.ma5 else None,
                ma10=float(r.ma10) if r.ma10 else None,
                ma20=float(r.ma20) if r.ma20 else None,
                ma60=float(r.ma60) if r.ma60 else None,
                macd_dif=None if hide else (float(r.macd_dif) if r.macd_dif else None),
                macd_dea=None if hide else (float(r.macd_dea) if r.macd_dea else None),
                macd_hist=None if hide else (float(r.macd_hist) if r.macd_hist else None),
            ))

        # 获取当日 open/close 和涨跌停价
        today_bar = db.query(StockDailyBar).filter(
            StockDailyBar.stock_code == stock_code,
            StockDailyBar.trade_date == end_date,
        ).first()
        if today_bar:
            open_price = float(today_bar.open) if today_bar.open else None
            close_price = float(today_bar.close) if (phase == "close" and today_bar.close) else None
            if today_bar.prev_close:
                lu, ld = _calc_limits(today_bar.prev_close)
                limit_up = float(lu)
                limit_down = float(ld)

    return ChartDataResponse(
        stock_code=stock_code,
        stock_name=stock_name,
        period=period,
        open_price=open_price,
        close_price=close_price,
        limit_up=limit_up,
        limit_down=limit_down,
        data=bars,
    )


def resolve_stock_query(db: Session, query: str, limit: int) -> StockResolveResponse:
    """按股票代码或名称模糊匹配，供 K 线查询与资料弹窗解析用户输入。"""
    raw = (query or "").strip()
    if not raw:
        return StockResolveResponse(items=[])
    lim = max(1, min(limit, 50))

    exact = db.query(StockBasic).filter(StockBasic.code == raw).first()
    if exact:
        return StockResolveResponse(
            items=[StockResolveItem(stock_code=exact.code, stock_name=exact.name)],
        )

    pat = f"%{raw}%"
    rows = (
        db.query(StockBasic)
        .filter(or_(StockBasic.code.like(pat), StockBasic.name.like(pat)))
        .order_by(StockBasic.code.asc())
        .limit(lim)
        .all()
    )
    return StockResolveResponse(
        items=[StockResolveItem(stock_code=r.code, stock_name=r.name) for r in rows],
    )


def _fdec(v) -> float | None:
    if v is None:
        return None
    return float(v)


def get_stock_info_snapshot(
    db: Session,
    stock_code: str,
    end_date: date,
    phase: str,
) -> PaperStockInfoResponse:
    """当前模拟日下的股票资料：基本信息、日线一行（遵守 phase 掩码）、截至 end_date 最近一期财报。"""
    basic_row = db.query(StockBasic).filter(StockBasic.code == stock_code).first()
    if not basic_row:
        raise HTTPException(
            status_code=404,
            detail={"code": "STOCK_NOT_FOUND", "message": "未找到该股票基础信息"},
        )

    basic = StockInfoBasicBlock(
        stock_code=basic_row.code,
        stock_name=basic_row.name,
        exchange=basic_row.exchange,
        market=basic_row.market,
        industry_name=basic_row.industry_name,
        region=basic_row.region,
        list_date=str(basic_row.list_date) if basic_row.list_date else None,
    )

    bar = (
        db.query(StockDailyBar)
        .filter(StockDailyBar.stock_code == stock_code, StockDailyBar.trade_date == end_date)
        .first()
    )
    hide = phase == "open"
    daily: StockInfoDailyBlock | None = None
    if bar:
        daily = StockInfoDailyBlock(
            trade_date=str(bar.trade_date),
            open=_fdec(bar.open),
            high=None if hide else _fdec(bar.high),
            low=None if hide else _fdec(bar.low),
            close=None if hide else _fdec(bar.close),
            prev_close=_fdec(bar.prev_close),
            pct_change=None if hide else _fdec(bar.pct_change),
            volume=None if hide else _fdec(bar.volume),
            amount=None if hide else _fdec(bar.amount),
            amplitude=None if hide else _fdec(bar.amplitude),
            turnover_rate=_fdec(bar.turnover_rate),
            pe_ttm=_fdec(bar.pe_ttm),
            pb=_fdec(bar.pb),
            total_market_cap=_fdec(bar.total_market_cap),
            float_market_cap=_fdec(bar.float_market_cap),
        )

    fin = (
        db.query(StockFinancialReport)
        .filter(
            StockFinancialReport.stock_code == stock_code,
            StockFinancialReport.report_date <= end_date,
        )
        .order_by(StockFinancialReport.report_date.desc())
        .first()
    )
    financial: StockInfoFinancialBlock | None = None
    if fin:
        financial = StockInfoFinancialBlock(
            report_date=str(fin.report_date),
            report_type=fin.report_type,
            roe=_fdec(fin.roe),
            roe_dt=_fdec(fin.roe_dt),
            debt_to_assets=_fdec(fin.debt_to_assets),
            roa=_fdec(fin.roa),
            gross_margin=_fdec(fin.gross_margin),
            net_margin=_fdec(fin.net_margin),
            revenue=_fdec(fin.revenue),
            net_profit=_fdec(fin.net_profit),
            eps=_fdec(fin.eps),
            bps=_fdec(fin.bps),
        )

    return PaperStockInfoResponse(
        stock_code=stock_code,
        end_date=str(end_date),
        phase=phase,
        basic=basic,
        daily=daily,
        financial=financial,
    )


def recommend_stocks(
    db: Session,
    trade_date: date,
    phase: str,
    count: int,
) -> RecommendResponse:
    """随机推荐当日有效股票。phase=open 时 close/pct_change 返回 None。"""
    # 获取当日所有股票
    all_bars = (
        db.query(StockDailyBar)
        .filter(StockDailyBar.trade_date == trade_date)
        .all()
    )
    if not all_bars:
        raise HTTPException(status_code=400, detail={"code": "INVALID_DATE", "message": "该日期无股票数据"})

    sampled = random.sample(all_bars, min(count, len(all_bars)))

    items = []
    for bar in sampled:
        # 查询股票名称
        stock_name = bar.stock_code
        try:
            basic = db.query(StockBasic).filter(StockBasic.code == bar.stock_code).first()
            if basic:
                stock_name = basic.name
        except Exception:
            pass

        if bar.prev_close:
            lu, ld = _calc_limits(bar.prev_close)
            limit_up = float(lu)
            limit_down = float(ld)
        else:
            limit_up = limit_down = None

        items.append(StockQuote(
            stock_code=bar.stock_code,
            stock_name=stock_name,
            open=float(bar.open) if bar.open else None,
            close=float(bar.close) if (phase == "close" and bar.close) else None,
            pct_change=float(bar.pct_change) if (phase == "close" and bar.pct_change) else None,
            volume=float(bar.volume) if bar.volume else None,
            limit_up=limit_up,
            limit_down=limit_down,
        ))

    return RecommendResponse(trade_date=trade_date, phase=phase, items=items)


def screen_stocks(
    db: Session,
    trade_date: date,
    pct_change_min: Optional[float],
    pct_change_max: Optional[float],
    volume_min: Optional[float],
    volume_max: Optional[float],
    ma_golden_cross: Optional[str],
    macd_golden_cross: Optional[bool],
    page: int,
    page_size: int,
) -> ScreenResponse:
    """自定义筛选当日股票。均线/MACD 金叉需与前一日对比。"""
    q = db.query(StockDailyBar).filter(StockDailyBar.trade_date == trade_date)

    if pct_change_min is not None:
        q = q.filter(StockDailyBar.pct_change >= pct_change_min)
    if pct_change_max is not None:
        q = q.filter(StockDailyBar.pct_change <= pct_change_max)
    if volume_min is not None:
        q = q.filter(StockDailyBar.volume >= volume_min)
    if volume_max is not None:
        q = q.filter(StockDailyBar.volume <= volume_max)

    # 均线金叉：当日 ma5 > ma10/ma20
    if ma_golden_cross == "ma5_ma10":
        q = q.filter(StockDailyBar.ma5 > StockDailyBar.ma10)
    elif ma_golden_cross == "ma5_ma20":
        q = q.filter(StockDailyBar.ma5 > StockDailyBar.ma20)

    # MACD 金叉：当日 dif > dea
    if macd_golden_cross:
        q = q.filter(StockDailyBar.macd_dif > StockDailyBar.macd_dea)

    total = q.count()
    bars = q.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for bar in bars:
        # 查询股票名称
        stock_name = bar.stock_code
        try:
            basic = db.query(StockBasic).filter(StockBasic.code == bar.stock_code).first()
            if basic:
                stock_name = basic.name
        except Exception:
            pass

        if bar.prev_close:
            lu, ld = _calc_limits(bar.prev_close)
            limit_up = float(lu)
            limit_down = float(ld)
        else:
            limit_up = limit_down = None

        items.append(StockQuote(
            stock_code=bar.stock_code,
            stock_name=stock_name,
            open=float(bar.open) if bar.open else None,
            close=float(bar.close) if bar.close else None,
            pct_change=float(bar.pct_change) if bar.pct_change else None,
            volume=float(bar.volume) if bar.volume else None,
            limit_up=limit_up,
            limit_down=limit_down,
        ))

    return ScreenResponse(trade_date=trade_date, total=total, page=page, page_size=page_size, items=items)


def get_trading_dates(db: Session, start: date, end: date) -> TradingDatesResponse:
    """获取指定范围内的交易日列表。"""
    rows = (
        db.query(StockDailyBar.trade_date)
        .filter(StockDailyBar.trade_date >= start, StockDailyBar.trade_date <= end)
        .distinct()
        .order_by(StockDailyBar.trade_date.asc())
        .all()
    )
    dates = [str(r.trade_date) for r in rows]

    min_row = db.query(func.min(StockDailyBar.trade_date)).scalar()
    max_row = db.query(func.max(StockDailyBar.trade_date)).scalar()

    return TradingDatesResponse(
        dates=dates,
        min_date=str(min_row) if min_row else "",
        max_date=str(max_row) if max_row else "",
    )
