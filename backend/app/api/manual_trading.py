"""手动模拟交易 API。

路由前缀：/api/manual-trading
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.manual_trading import (
    AdvanceRequest,
    AdvanceResponse,
    BuyRequest,
    CreateSessionRequest,
    OperationsResponse,
    SessionDetailResponse,
    SessionListResponse,
    RevalRequest,
)
from app.services import manual_trading_service as svc

router = APIRouter(prefix="/manual-trading", tags=["manual-trading"])


@router.post("/sessions", response_model=SessionDetailResponse, status_code=status.HTTP_201_CREATED)
def api_create_session(
    body: CreateSessionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """创建手动模拟会话。"""
    return svc.create_session(
        db, current_user, body.asset_name, body.start_date, body.name
    )


@router.get("/sessions", response_model=SessionListResponse)
def api_list_sessions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
):
    """查询当前用户的会话列表。"""
    return svc.list_sessions(db, current_user, status_filter, page, page_size)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def api_get_session(
    session_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """查询会话详情。"""
    return svc.get_session(db, current_user, session_id)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_session(
    session_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """删除会话及全部流水。"""
    svc.delete_session(db, current_user, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/{session_id}/buy", response_model=SessionDetailResponse)
def api_buy(
    session_id: str,
    body: BuyRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """当前模拟日买入。"""
    return svc.buy(db, current_user, session_id, body.amount, body.price)


@router.post("/sessions/{session_id}/advance", response_model=AdvanceResponse)
def api_advance(
    session_id: str,
    body: AdvanceRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """快捷推进模拟日。"""
    return svc.advance(db, current_user, session_id, body.step)


@router.post("/sessions/{session_id}/reval", response_model=SessionDetailResponse)
def api_reval(
    session_id: str,
    body: RevalRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """录入收盘价，完成估值推进。"""
    return svc.reval(db, current_user, session_id, body.close_price)


@router.post("/sessions/{session_id}/end", response_model=SessionDetailResponse)
def api_end_session(
    session_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """结束交易。"""
    return svc.end_session(db, current_user, session_id)


@router.get("/sessions/{session_id}/operations", response_model=OperationsResponse)
def api_list_operations(
    session_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """操作流水与复盘汇总。"""
    return svc.list_operations(db, current_user, session_id)
