"""手动模拟交易单元测试。"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.manual_trading import ManualTradingSession
from app.services import manual_trading_service as svc


def test_apply_reval_ratio():
    pos_after, pnl = svc.apply_reval(Decimal("100000"), Decimal("2000"), Decimal("1800"))
    assert pos_after == Decimal("90000.00")
    assert pnl == Decimal("-10000.00")


def test_apply_reval_zero_position():
    pos_after, pnl = svc.apply_reval(Decimal("0"), Decimal("2000"), Decimal("1800"))
    assert pos_after == Decimal("0")
    assert pnl == Decimal("0")


def test_advance_date_steps():
    base = date(2001, 1, 1)
    assert svc.advance_date(base, "day") == date(2001, 1, 2)
    assert svc.advance_date(base, "week") == date(2001, 1, 8)
    assert svc.advance_date(base, "month") == date(2001, 2, 1)
    assert svc.advance_date(base, "year") == date(2002, 1, 1)


def test_assert_not_awaiting_blocks():
    session = ManualTradingSession(
        session_id="mt-test",
        user_id=1,
        asset_name="x",
        start_date=date(2001, 1, 1),
        current_date=date(2001, 1, 1),
        awaiting_reval=True,
        status="active",
    )
    with pytest.raises(HTTPException) as exc:
        svc._assert_not_awaiting(session)
    assert _detail_code(exc.value) == "AWAITING_REVAL"


def test_assert_awaiting_requires_flag():
    session = ManualTradingSession(
        session_id="mt-test",
        user_id=1,
        asset_name="x",
        start_date=date(2001, 1, 1),
        current_date=date(2001, 1, 1),
        awaiting_reval=False,
        status="active",
    )
    with pytest.raises(HTTPException) as exc:
        svc._assert_awaiting(session)
    assert _detail_code(exc.value) == "NOT_AWAITING_REVAL"


def test_assert_active_blocks_ended():
    session = ManualTradingSession(
        session_id="mt-test",
        user_id=1,
        asset_name="x",
        start_date=date(2001, 1, 1),
        current_date=date(2001, 1, 1),
        status="ended",
    )
    with pytest.raises(HTTPException) as exc:
        svc._assert_active(session)
    assert _detail_code(exc.value) == "SESSION_ENDED"


def test_calc_total_pnl():
    session = ManualTradingSession(
        session_id="mt-test",
        user_id=1,
        asset_name="x",
        start_date=date(2001, 1, 1),
        current_date=date(2002, 1, 1),
        position_value=Decimal("90000"),
        total_invested=Decimal("100000"),
        status="active",
    )
    assert svc._calc_total_pnl(session) == Decimal("-10000.00")


def _detail_code(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        return detail.get("code", "")
    return str(detail)
