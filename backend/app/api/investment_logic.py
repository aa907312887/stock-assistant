"""投资逻辑 CRUD，契约见 specs/004-首页投资逻辑/contracts/investment-logic-api.md。"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.investment_logic_entry import InvestmentLogicEntry
from app.models.user import User
from app.schemas.investment_logic import (
    InvestmentLogicCreateIn,
    InvestmentLogicCurrentOut,
    InvestmentLogicEntryOut,
    InvestmentLogicListOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/investment-logic", tags=["投资逻辑"])


def _to_http_exc(e: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/current", response_model=InvestmentLogicCurrentOut)
def get_current(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.investment_logic_service import get_current_entry

    entry = get_current_entry(db, current_user.id)
    return InvestmentLogicCurrentOut(entry=InvestmentLogicEntryOut.model_validate(entry) if entry else None)


@router.get("/entries", response_model=InvestmentLogicListOut)
def list_entries_api(
    order: str = "created_desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if order not in ("created_desc", "created_asc"):
        raise HTTPException(status_code=400, detail="order 须为 created_desc 或 created_asc")
    from app.services.investment_logic_service import list_entries

    rows = list_entries(db, current_user.id, order=order)
    return InvestmentLogicListOut(items=[InvestmentLogicEntryOut.model_validate(r) for r in rows])


@router.post("/entries", response_model=InvestmentLogicEntryOut, status_code=status.HTTP_201_CREATED)
def create_entry(
    body: InvestmentLogicCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services import investment_logic_service as svc

    try:
        t, f, m = svc.validate_contents(
            body.technical_content,
            body.fundamental_content,
            body.message_content,
        )
        svc.validate_weights(body.weight_technical, body.weight_fundamental, body.weight_message)
        svc.validate_extra_json(body.extra_json)
    except ValueError as e:
        raise _to_http_exc(e) from e

    row = InvestmentLogicEntry(
        user_id=current_user.id,
        technical_content=t,
        fundamental_content=f,
        message_content=m,
        weight_technical=body.weight_technical,
        weight_fundamental=body.weight_fundamental,
        weight_message=body.weight_message,
        extra_json=body.extra_json,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("投资逻辑已新增 id=%s user_id=%s", row.id, current_user.id)
    return InvestmentLogicEntryOut.model_validate(row)


@router.put("/entries/{entry_id}", response_model=InvestmentLogicEntryOut)
async def update_entry(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services import investment_logic_service as svc

    raw: dict[str, Any] = await request.json()
    try:
        body = InvestmentLogicCreateIn.model_validate(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"请求体无效: {e}") from e

    row = (
        db.query(InvestmentLogicEntry)
        .filter(
            InvestmentLogicEntry.id == entry_id,
            InvestmentLogicEntry.user_id == current_user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记录不存在")

    try:
        t, f, m = svc.validate_contents(
            body.technical_content,
            body.fundamental_content,
            body.message_content,
        )
        svc.validate_weights(body.weight_technical, body.weight_fundamental, body.weight_message)
        if "extra_json" in raw:
            if raw["extra_json"] is None:
                row.extra_json = None
            else:
                svc.validate_extra_json(body.extra_json)
                row.extra_json = body.extra_json
    except ValueError as e:
        raise _to_http_exc(e) from e

    row.technical_content = t
    row.fundamental_content = f
    row.message_content = m
    row.weight_technical = body.weight_technical
    row.weight_fundamental = body.weight_fundamental
    row.weight_message = body.weight_message

    db.commit()
    db.refresh(row)
    logger.info("投资逻辑已更新 id=%s user_id=%s", row.id, current_user.id)
    return InvestmentLogicEntryOut.model_validate(row)


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(InvestmentLogicEntry)
        .filter(
            InvestmentLogicEntry.id == entry_id,
            InvestmentLogicEntry.user_id == current_user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记录不存在")
    db.delete(row)
    db.commit()
    logger.info("投资逻辑已删除 id=%s user_id=%s", entry_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
