"""个人持仓 API：/api/portfolio/*"""

import logging
import os
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.portfolio_operation import PortfolioOperation
from app.models.portfolio_trade import PortfolioTrade
from app.models.portfolio_trade_image import PortfolioTradeImage
from app.models.user import User
import app.schemas.portfolio as schemas
from app.services import portfolio_service as psvc
from app.services.portfolio_price_service import get_latest_close
from app.services.portfolio_service import ZERO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio", tags=["个人持仓"])

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
UPLOAD_ROOT = os.path.join(_BACKEND_ROOT, "uploads", "portfolio")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _ensure_upload_dir(user_id: int, trade_id: int) -> str:
    d = os.path.join(UPLOAD_ROOT, str(user_id), str(trade_id))
    os.makedirs(d, exist_ok=True)
    return d


@router.get("/open-trades", response_model=schemas.OpenTradesResponse)
def list_open_trades(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    trades = (
        db.query(PortfolioTrade)
        .filter(
            PortfolioTrade.user_id == current_user.id,
            PortfolioTrade.status == "open",
        )
        .order_by(PortfolioTrade.id.desc())
        .all()
    )
    items: list[schemas.OpenTradeItem] = []
    for t in trades:
        name = psvc.get_stock_name(db, t.stock_code)
        ref_close, ref_date = get_latest_close(db, t.stock_code)
        tq = t.total_qty if t.total_qty is not None else ZERO
        ac = t.avg_cost if t.avg_cost is not None else ZERO
        tcb = t.total_cost_basis if t.total_cost_basis is not None else ZERO
        acc_realized = t.accumulated_realized_pnl if t.accumulated_realized_pnl is not None else ZERO
        has_ref = ref_close is not None and tq > ZERO
        ref_mv = ref_pnl = ref_pct = None
        if has_ref and ref_close is not None:
            ref_mv = tq * ref_close
            floating_pnl = ref_mv - tcb
            # 开放仓位的“总盈亏”= 历史减仓已实现 + 当前剩余浮盈亏
            ref_pnl = acc_realized + floating_pnl
            # 收益率口径：按当前持仓成本（剩余仓位成本）计算，更贴近券商持仓页展示
            if tcb > ZERO:
                ref_pct = ref_pnl / tcb
        items.append(
            schemas.OpenTradeItem(
                trade_id=t.id,
                stock_code=t.stock_code,
                stock_name=name,
                total_qty=t.total_qty,
                avg_cost=t.avg_cost,
                ref_close=ref_close,
                ref_close_date=ref_date,
                ref_market_value=ref_mv,
                ref_pnl=ref_pnl,
                ref_pnl_pct=ref_pct,
                has_ref_price=bool(has_ref),
            )
        )
    return schemas.OpenTradesResponse(items=items)


@router.post("/trades/open", response_model=schemas.OpenTradeResponse, status_code=status.HTTP_201_CREATED)
def open_trade(
    body: schemas.TradeOpenBody,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        trade, op = psvc.create_open_trade(
            db,
            current_user.id,
            body.stock_code,
            body.op_date,
            body.qty,
            body.price,
            body.fee,
        )
        db.commit()
        logger.info("portfolio open trade user=%s trade=%s code=%s", current_user.id, trade.id, trade.stock_code)
        return schemas.OpenTradeResponse(trade_id=trade.id, operation_id=op.id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception:
        db.rollback()
        raise


@router.post(
    "/trades/{trade_id}/operations",
    response_model=schemas.OperationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_operation(
    trade_id: int,
    body: schemas.OperationBody,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        op = psvc.add_or_reduce(
            db,
            current_user.id,
            trade_id,
            body.op_type,
            body.op_date,
            body.qty,
            body.price,
            body.fee,
            body.operation_rating,
            body.note,
        )
        db.commit()
        logger.info("portfolio operation user=%s trade=%s op=%s", current_user.id, trade_id, op.id)
        return schemas.OperationCreateResponse(operation_id=op.id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception:
        db.rollback()
        raise


@router.post("/trades/{trade_id}/close", response_model=schemas.CloseTradeResponse)
def close_trade(
    trade_id: int,
    body: schemas.CloseBody,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        trade, pnl = psvc.close_trade(
            db,
            current_user.id,
            trade_id,
            body.op_date,
            body.qty,
            body.price,
            body.fee,
            body.operation_rating,
            body.note,
        )
        db.commit()
        logger.info("portfolio close user=%s trade=%s pnl=%s", current_user.id, trade_id, pnl)
        return schemas.CloseTradeResponse(trade_id=trade.id, realized_pnl=trade.realized_pnl)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception:
        db.rollback()
        raise


@router.delete("/trades/{trade_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trade(
    trade_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        ok = psvc.delete_open_trade(db, current_user.id, trade_id)
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="交易不存在")
        db.commit()
        logger.info("portfolio delete open trade user=%s trade=%s", current_user.id, trade_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.get("/closed-trades", response_model=schemas.ClosedTradesResponse)
def list_closed_trades(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    stock_code: str | None = None,
):
    q = db.query(PortfolioTrade).filter(
        PortfolioTrade.user_id == current_user.id,
        PortfolioTrade.status == "closed",
    )
    if stock_code:
        q = q.filter(PortfolioTrade.stock_code == stock_code.strip())
    total = q.count()
    rows = (
        q.order_by(desc(PortfolioTrade.closed_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for t in rows:
        img_count = (
            db.query(func.count(PortfolioTradeImage.id))
            .filter(PortfolioTradeImage.trade_id == t.id)
            .scalar()
            or 0
        )
        total_buy_cost = (
            db.query(
                func.coalesce(
                    func.sum(
                        func.coalesce(PortfolioOperation.amount, ZERO)
                        + func.coalesce(PortfolioOperation.fee, ZERO)
                    ),
                    ZERO,
                )
            )
            .filter(
                PortfolioOperation.trade_id == t.id,
                PortfolioOperation.op_type.in_(("open", "add")),
            )
            .scalar()
            or ZERO
        )
        realized_pnl_rate = None
        if t.realized_pnl is not None and total_buy_cost > ZERO:
            realized_pnl_rate = t.realized_pnl / total_buy_cost
        items.append(
            schemas.ClosedTradeItem(
                trade_id=t.id,
                stock_code=t.stock_code,
                stock_name=psvc.get_stock_name(db, t.stock_code),
                closed_at=t.closed_at,
                realized_pnl=t.realized_pnl,
                realized_pnl_rate=realized_pnl_rate,
                review_text=t.review_text,
                image_count=int(img_count),
            )
        )
    return schemas.ClosedTradesResponse(total=total, items=items)


@router.get("/trades/{trade_id}", response_model=schemas.TradeDetailResponse)
def get_trade_detail(
    trade_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    trade = psvc.get_trade_for_user(db, trade_id, current_user.id)
    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="交易不存在")
    ops = (
        db.query(PortfolioOperation)
        .filter(PortfolioOperation.trade_id == trade_id)
        .order_by(PortfolioOperation.op_date, PortfolioOperation.id)
        .all()
    )
    total_buy_cost = ZERO
    for o in ops:
        if o.op_type in ("open", "add"):
            total_buy_cost += (o.amount or ZERO) + (o.fee or ZERO)
    realized_pnl_rate = None
    if trade.realized_pnl is not None and total_buy_cost > ZERO:
        realized_pnl_rate = trade.realized_pnl / total_buy_cost
    tout = schemas.TradeOut(
        id=trade.id,
        stock_code=trade.stock_code,
        stock_name=psvc.get_stock_name(db, trade.stock_code),
        status=trade.status,
        opened_at=trade.opened_at,
        closed_at=trade.closed_at,
        avg_cost=trade.avg_cost,
        total_qty=trade.total_qty,
        realized_pnl=trade.realized_pnl,
        realized_pnl_rate=realized_pnl_rate,
        review_text=trade.review_text,
    )
    olist = [
        schemas.OperationOut(
            id=o.id,
            op_type=o.op_type,
            op_date=o.op_date,
            qty=o.qty,
            price=o.price,
            operation_rating=o.operation_rating,
            note=o.note,
        )
        for o in ops
    ]
    imgs = (
        db.query(PortfolioTradeImage)
        .filter(PortfolioTradeImage.trade_id == trade_id)
        .order_by(PortfolioTradeImage.sort_order, PortfolioTradeImage.id)
        .all()
    )
    img_out = [
        schemas.TradeImageOut(id=im.id, url=f"/api/portfolio/images/{im.id}/file") for im in imgs
    ]
    return schemas.TradeDetailResponse(trade=tout, operations=olist, images=img_out)


@router.patch("/trades/{trade_id}/review")
def patch_review(
    trade_id: int,
    body: schemas.ReviewPatchBody,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    trade = psvc.get_trade_for_user(db, trade_id, current_user.id)
    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="交易不存在")
    if trade.status != "closed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅已完结交易可写复盘")
    trade.review_text = body.review_text
    db.commit()
    return {"ok": True}


@router.post("/trades/{trade_id}/images", response_model=schemas.ImageUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    trade_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
):
    trade = psvc.get_trade_for_user(db, trade_id, current_user.id)
    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="交易不存在")
    if trade.status != "closed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅已完结交易可上传复盘图")
    ct = file.content_type or ""
    if ct not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="仅支持 JPEG/PNG/WebP")
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="单张图片不超过 5MB")
    if "jpeg" in ct or "jpg" in ct:
        suffix = ".jpg"
    elif "png" in ct:
        suffix = ".png"
    else:
        suffix = ".webp"
    uid = str(uuid.uuid4())
    subdir = _ensure_upload_dir(current_user.id, trade_id)
    fname = f"{uid}{suffix}"
    fpath = os.path.join(subdir, fname)
    rel = os.path.join(str(current_user.id), str(trade_id), fname)
    try:
        with open(fpath, "wb") as f:
            f.write(data)
    except OSError as e:
        logger.exception("portfolio upload write failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="保存文件失败") from e
    row = PortfolioTradeImage(
        trade_id=trade_id,
        user_id=current_user.id,
        file_path=rel.replace("\\", "/"),
        mime_type=ct,
        size_bytes=len(data),
        sort_order=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(
        "portfolio upload image user=%s trade=%s image_id=%s bytes=%s",
        current_user.id,
        trade_id,
        row.id,
        len(data),
    )
    url = f"/api/portfolio/images/{row.id}/file"
    return schemas.ImageUploadResponse(image_id=row.id, url=url)


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(
    image_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    row = (
        db.query(PortfolioTradeImage)
        .filter(
            PortfolioTradeImage.id == image_id,
            PortfolioTradeImage.user_id == current_user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")
    abs_path = os.path.join(UPLOAD_ROOT, row.file_path.replace("/", os.sep))
    db.delete(row)
    db.commit()
    if os.path.isfile(abs_path):
        try:
            os.remove(abs_path)
        except OSError:
            logger.warning("portfolio image delete file failed: %s", abs_path)


@router.get("/images/{image_id}/file")
def get_image_file(
    image_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    row = (
        db.query(PortfolioTradeImage)
        .filter(
            PortfolioTradeImage.id == image_id,
            PortfolioTradeImage.user_id == current_user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")
    abs_path = os.path.join(UPLOAD_ROOT, row.file_path.replace("/", os.sep))
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件已丢失")
    return FileResponse(abs_path, media_type=row.mime_type)


@router.patch("/operations/{operation_id}/rating")
def patch_operation_rating(
    operation_id: int,
    body: schemas.OperationRatingBody,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    op = psvc.get_operation_for_user(db, operation_id, current_user.id)
    if not op:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="操作不存在")
    op.operation_rating = body.operation_rating
    db.commit()
    return {"ok": True}


@router.get("/stats", response_model=schemas.StatsResponse)
def get_stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    from_date: date | None = None,
    to_date: date | None = None,
):
    raw = psvc.aggregate_stats(db, current_user.id, from_date, to_date)
    sw = raw["stock_win_rate"]
    ow = raw["operation_win_rate"]
    opnl = raw["overall_pnl"]
    return schemas.StatsResponse(
        stock_win_rate=schemas.StockWinRate(
            won=sw["won"],
            lost=sw["lost"],
            breakeven=sw["breakeven"],
            total=sw["total"],
            rate=sw["rate"],
        ),
        operation_win_rate=schemas.OperationWinRate(
            good=ow["good"],
            bad=ow["bad"],
            unrated=ow["unrated"],
            rated_total=ow["rated_total"],
            rate=ow["rate"],
        ),
        overall_pnl=schemas.OverallPnlSummary(
            total_profit=opnl["total_profit"],
            total_loss=opnl["total_loss"],
            net_pnl=opnl["net_pnl"],
            net_pnl_rate=opnl["net_pnl_rate"],
        ),
    )
