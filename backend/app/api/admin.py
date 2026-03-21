"""管理接口：手动触发股票同步等。"""
import logging
import threading

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.scheduler import run_sync_once_now

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["管理"])


def _check_admin( x_admin_secret: str | None = None) -> None:
    """鉴权：请求头 X-Admin-Secret 与配置一致。"""
    secret = (settings.admin_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="未配置 ADMIN_SECRET，无法调用管理接口",
        )
    if (x_admin_secret or "").strip() != secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鉴权失败",
        )


@router.post("/stock-sync")
async def trigger_stock_sync(
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
):
    """手动触发一次股票数据同步。返回 202，同步在后台执行。"""
    _check_admin(x_admin_secret)
    threading.Thread(target=run_sync_once_now, daemon=True).start()
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"status": "started", "message": "同步任务已触发"},
    )
