"""手动模拟交易业务逻辑。

比例跟盘：持仓名义金额随参考价与录入收盘价之比同比变化；不算股数。
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from dateutil.relativedelta import relativedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.manual_trading import ManualTradingOperation, ManualTradingSession
from app.models.user import User
from app.schemas.manual_trading import (
    AdvanceResponse,
    OperationItem,
    OperationsResponse,
    SessionDetailResponse,
    SessionListItem,
    SessionListResponse,
)

OP_TYPE_LABELS = {
    "buy": "买入",
    "reval": "估值推进",
    "end": "结束交易",
}

VALID_STEPS = frozenset({"day", "week", "month", "year"})


def _gen_session_id() -> str:
    return f"mt-{uuid.uuid4().hex[:8]}"


def _d(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _price(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def advance_date(current: date, step: str) -> date:
    """按步长推进日历日。"""
    if step == "day":
        return current + relativedelta(days=1)
    if step == "week":
        return current + relativedelta(days=7)
    if step == "month":
        return current + relativedelta(months=1)
    if step == "year":
        return current + relativedelta(years=1)
    raise ValueError(f"invalid step: {step}")


def apply_reval(
    position_value: Decimal,
    reference_price: Decimal,
    close_price: Decimal,
) -> tuple[Decimal, Decimal]:
    """比例跟盘：返回 (新持仓金额, 本段盈亏)。"""
    if position_value <= 0 or reference_price <= 0:
        return position_value, Decimal("0")
    pos_before = position_value
    ratio = close_price / reference_price
    pos_after = _money(pos_before * ratio)
    segment_pnl = _money(pos_after - pos_before)
    return pos_after, segment_pnl


def _get_session_or_404(db: Session, session_id: str, user_id: int) -> ManualTradingSession:
    row = (
        db.query(ManualTradingSession)
        .filter(
            ManualTradingSession.session_id == session_id,
            ManualTradingSession.user_id == user_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"code": "SESSION_NOT_FOUND", "message": "会话不存在"},
        )
    return row


def _assert_active(session: ManualTradingSession) -> None:
    if session.status != "active":
        raise HTTPException(
            status_code=409,
            detail={"code": "SESSION_ENDED", "message": "会话已结束"},
        )


def _assert_not_awaiting(session: ManualTradingSession) -> None:
    if session.awaiting_reval:
        raise HTTPException(
            status_code=409,
            detail={"code": "AWAITING_REVAL", "message": "请先录入收盘价后再操作"},
        )


def _assert_awaiting(session: ManualTradingSession) -> None:
    if not session.awaiting_reval:
        raise HTTPException(
            status_code=409,
            detail={"code": "NOT_AWAITING_REVAL", "message": "当前不在待录价状态"},
        )


def _calc_total_pnl(session: ManualTradingSession) -> Decimal:
    return _money(_d(session.position_value) - _d(session.total_invested))


def _calc_total_pnl_pct(session: ManualTradingSession) -> Optional[float]:
    invested = _d(session.total_invested)
    if invested <= 0:
        return None
    pnl = _calc_total_pnl(session)
    return float((pnl / invested).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _calc_total_trading_days(session: ManualTradingSession) -> Optional[int]:
    if not session.first_operation_date:
        return None
    end = session.end_date if session.status == "ended" else session.current_date
    return (end - session.first_operation_date).days


def _to_detail(session: ManualTradingSession) -> SessionDetailResponse:
    ref = float(session.reference_price) if session.reference_price is not None else None
    return SessionDetailResponse(
        session_id=session.session_id,
        name=session.name,
        asset_name=session.asset_name,
        start_date=session.start_date,
        current_date=session.current_date,
        reference_price=ref,
        position_value=float(session.position_value),
        total_invested=float(session.total_invested),
        total_pnl=float(_calc_total_pnl(session)),
        total_pnl_pct=_calc_total_pnl_pct(session),
        total_trading_days=_calc_total_trading_days(session),
        status=session.status,
        awaiting_reval=bool(session.awaiting_reval),
        end_date=session.end_date,
        first_operation_date=session.first_operation_date,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _to_list_item(session: ManualTradingSession) -> SessionListItem:
    return SessionListItem(
        session_id=session.session_id,
        name=session.name,
        asset_name=session.asset_name,
        start_date=session.start_date,
        current_date=session.current_date,
        position_value=float(session.position_value),
        total_invested=float(session.total_invested),
        total_pnl=float(_calc_total_pnl(session)),
        status=session.status,
        awaiting_reval=bool(session.awaiting_reval),
        created_at=session.created_at,
    )


def create_session(
    db: Session,
    user: User,
    asset_name: str,
    start_date: date,
    name: Optional[str] = None,
) -> SessionDetailResponse:
    asset_name = (asset_name or "").strip()
    if not asset_name:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_PARAM", "message": "标的名称不能为空"},
        )
    session = ManualTradingSession(
        session_id=_gen_session_id(),
        user_id=user.id,
        name=(name or "").strip() or None,
        asset_name=asset_name,
        start_date=start_date,
        current_date=start_date,
        position_value=Decimal("0"),
        total_invested=Decimal("0"),
        awaiting_reval=False,
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _to_detail(session)


def list_sessions(
    db: Session,
    user: User,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> SessionListResponse:
    q = db.query(ManualTradingSession).filter(ManualTradingSession.user_id == user.id)
    if status in ("active", "ended"):
        q = q.filter(ManualTradingSession.status == status)
    total = q.count()
    rows = (
        q.order_by(ManualTradingSession.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return SessionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_to_list_item(r) for r in rows],
    )


def get_session(db: Session, user: User, session_id: str) -> SessionDetailResponse:
    session = _get_session_or_404(db, session_id, user.id)
    return _to_detail(session)


def delete_session(db: Session, user: User, session_id: str) -> None:
    session = _get_session_or_404(db, session_id, user.id)
    db.query(ManualTradingOperation).filter(
        ManualTradingOperation.session_id == session.session_id
    ).delete()
    db.delete(session)
    db.commit()


def buy(db: Session, user: User, session_id: str, amount: float, price: float) -> SessionDetailResponse:
    session = _get_session_or_404(db, session_id, user.id)
    _assert_active(session)
    _assert_not_awaiting(session)
    amt = _money(_d(amount))
    px = _price(_d(price))
    if amt <= 0 or px <= 0:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_PARAM", "message": "买入金额与成交价须大于 0"},
        )

    pos_before = _d(session.position_value)
    pos_after = _money(pos_before + amt)
    session.position_value = pos_after
    session.total_invested = _money(_d(session.total_invested) + amt)
    if session.reference_price is None:
        session.reference_price = px
    if session.first_operation_date is None:
        session.first_operation_date = session.current_date

    op = ManualTradingOperation(
        session_id=session.session_id,
        op_type="buy",
        op_date=session.current_date,
        price=px,
        buy_amount=amt,
        position_before=pos_before,
        position_after=pos_after,
        segment_pnl=None,
    )
    db.add(op)
    db.commit()
    db.refresh(session)
    return _to_detail(session)


def advance(db: Session, user: User, session_id: str, step: str) -> AdvanceResponse:
    session = _get_session_or_404(db, session_id, user.id)
    _assert_active(session)
    _assert_not_awaiting(session)
    if step not in VALID_STEPS:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_PARAM", "message": "推进步长无效"},
        )

    session.current_date = advance_date(session.current_date, step)
    session.awaiting_reval = True
    session.last_advance_step = step
    db.commit()
    db.refresh(session)
    return AdvanceResponse(
        session_id=session.session_id,
        current_date=session.current_date,
        awaiting_reval=True,
        step=step,
    )


def reval(db: Session, user: User, session_id: str, close_price: float) -> SessionDetailResponse:
    session = _get_session_or_404(db, session_id, user.id)
    _assert_active(session)
    _assert_awaiting(session)
    px = _price(_d(close_price))
    if px <= 0:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_PARAM", "message": "收盘价须大于 0"},
        )

    pos_before = _d(session.position_value)
    ref = _d(session.reference_price) if session.reference_price is not None else Decimal("0")
    if pos_before > 0 and ref > 0:
        pos_after, segment_pnl = apply_reval(pos_before, ref, px)
    else:
        pos_after, segment_pnl = pos_before, Decimal("0")

    session.position_value = pos_after
    session.reference_price = px
    session.awaiting_reval = False
    step = session.last_advance_step
    session.last_advance_step = None

    op = ManualTradingOperation(
        session_id=session.session_id,
        op_type="reval",
        op_date=session.current_date,
        price=px,
        buy_amount=None,
        advance_step=step,
        position_before=pos_before,
        position_after=pos_after,
        segment_pnl=segment_pnl if pos_before > 0 else Decimal("0"),
    )
    db.add(op)
    db.commit()
    db.refresh(session)
    return _to_detail(session)


def end_session(db: Session, user: User, session_id: str) -> SessionDetailResponse:
    session = _get_session_or_404(db, session_id, user.id)
    _assert_active(session)
    _assert_not_awaiting(session)

    has_buy = (
        db.query(ManualTradingOperation)
        .filter(
            ManualTradingOperation.session_id == session.session_id,
            ManualTradingOperation.op_type == "buy",
        )
        .count()
        > 0
    )
    if not has_buy:
        raise HTTPException(
            status_code=409,
            detail={"code": "NO_BUY_YET", "message": "尚无买入记录，无法结束交易"},
        )

    pos_before = _d(session.position_value)
    session.status = "ended"
    session.end_date = session.current_date

    op = ManualTradingOperation(
        session_id=session.session_id,
        op_type="end",
        op_date=session.current_date,
        price=session.reference_price,
        buy_amount=None,
        position_before=pos_before,
        position_after=pos_before,
        segment_pnl=None,
    )
    db.add(op)
    db.commit()
    db.refresh(session)
    return _to_detail(session)


def list_operations(db: Session, user: User, session_id: str) -> OperationsResponse:
    session = _get_session_or_404(db, session_id, user.id)
    rows = (
        db.query(ManualTradingOperation)
        .filter(ManualTradingOperation.session_id == session.session_id)
        .order_by(ManualTradingOperation.op_date.asc(), ManualTradingOperation.id.asc())
        .all()
    )
    items: list[OperationItem] = []
    prev_date: date | None = None
    for row in rows:
        days_since: int | None = None
        if prev_date is not None:
            days_since = (row.op_date - prev_date).days
        prev_date = row.op_date
        items.append(
            OperationItem(
                id=row.id,
                op_type=row.op_type,
                op_type_label=OP_TYPE_LABELS.get(row.op_type, row.op_type),
                op_date=row.op_date,
                price=float(row.price) if row.price is not None else None,
                buy_amount=float(row.buy_amount) if row.buy_amount is not None else None,
                advance_step=row.advance_step,
                position_before=float(row.position_before),
                position_after=float(row.position_after),
                segment_pnl=float(row.segment_pnl) if row.segment_pnl is not None else None,
                days_since_prev=days_since,
            )
        )
    return OperationsResponse(
        session_id=session.session_id,
        total_pnl=float(_calc_total_pnl(session)),
        total_trading_days=_calc_total_trading_days(session),
        items=items,
    )
