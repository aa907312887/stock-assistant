"""管理接口：手动触发股票同步等。"""
from datetime import date, datetime
import logging
import threading

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.core.scheduler import run_sync_once_now
from app.database import get_db
from app.models import SyncJobRun, SyncTask, User
from app.services.tushare_client import get_latest_open_trade_date
from app.services.stock_indicator_fill_service import fill_indicators_for_timeframe
from app.schemas.stock_indicators import (
    TriggerStockIndicatorsRequest,
    TriggerStockIndicatorsResponse,
)
from app.schemas.sync_job import (
    SyncJobDetailResponse,
    SyncJobItem,
    SyncJobListResponse,
    SyncTaskItem,
    SyncTaskListResponse,
    TriggerSyncRequest,
    TriggerSyncResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["管理"])
SYNC_MONITOR_USER_ID = 2
SYNC_MONITOR_USERNAME = "杨佳兴"


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


def _check_sync_monitor_viewer(current_user: User) -> None:
    """同步任务监控仅允许指定用户查看。"""
    if current_user.id != SYNC_MONITOR_USER_ID or current_user.username != SYNC_MONITOR_USERNAME:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅允许杨佳兴查看同步任务监控",
        )


def _run_stock_indicators_background(
    batch_id: str,
    payload: TriggerStockIndicatorsRequest,
) -> None:
    """后台线程：按 timeframes 执行指标回填。"""
    from app.database import SessionLocal

    db = SessionLocal()
    rows_summary: dict[str, int] = {}
    errors: list[str] = []
    try:
        tfs = payload.timeframes or ["daily", "weekly", "monthly"]
        for tf in tfs:
            if tf not in ("daily", "weekly", "monthly"):
                errors.append(f"非法 timeframes 项: {tf}")
                continue
            if payload.mode == "incremental":
                anchor = payload.trade_date or date.today()
                resolved = get_latest_open_trade_date(anchor) or anchor
                r = fill_indicators_for_timeframe(
                    db,
                    tf,  # type: ignore[arg-type]
                    mode="incremental",
                    trade_date_anchor=resolved,
                    limit=payload.limit,
                )
            elif payload.mode == "full":
                r = fill_indicators_for_timeframe(
                    db,
                    tf,  # type: ignore[arg-type]
                    mode="full",
                    limit=payload.limit,
                )
            else:
                if payload.start_date is None or payload.end_date is None:
                    errors.append("backfill 需要 start_date 与 end_date")
                    break
                r = fill_indicators_for_timeframe(
                    db,
                    tf,  # type: ignore[arg-type]
                    mode="backfill",
                    start_date=payload.start_date,
                    end_date=payload.end_date,
                    limit=payload.limit,
                )
            rows_summary[tf] = int(r.get("rows_updated", 0))
            for f in r.get("failed_stocks") or []:
                errors.append(f"{tf}: {f}")
        logger.info(
            "指标回填完成 batch=%s summary=%s err_count=%s",
            batch_id,
            rows_summary,
            len(errors),
        )
    except Exception as exc:
        logger.exception("指标回填异常 batch=%s", batch_id)
        errors.append(str(exc))
    finally:
        db.close()


@router.post("/stock-indicators")
async def trigger_stock_indicators(
    payload: TriggerStockIndicatorsRequest = Body(...),
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
):
    """手工触发均线/MACD 回填（后台执行）。返回 202。"""
    _check_admin(x_admin_secret)
    batch_id = f"ind-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    def _runner() -> None:
        _run_stock_indicators_background(batch_id, payload)

    threading.Thread(target=_runner, daemon=True).start()
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=TriggerStockIndicatorsResponse(
            batch_id=batch_id,
            status="started",
            rows_updated=None,
            error_message=None,
        ).model_dump(),
    )


@router.post("/stock-sync")
async def trigger_stock_sync(
    payload: TriggerSyncRequest = Body(default_factory=TriggerSyncRequest),
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
):
    """手动触发一次股票数据同步。返回 202，同步在后台执行。"""
    _check_admin(x_admin_secret)
    batch_id = f"stock-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    def _runner() -> None:
        run_sync_once_now(
            batch_id=batch_id,
            mode=payload.mode,
            modules=payload.modules,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
    threading.Thread(target=_runner, daemon=True).start()
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=TriggerSyncResponse(
            status="started",
            batch_id=batch_id,
            mode=payload.mode,
            message="同步任务已触发",
        ).model_dump(),
    )


@router.get("/sync-jobs", response_model=SyncJobListResponse)
def list_sync_jobs(
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    job_mode: str | None = Query(None),
    job_name: str | None = Query(None),
    db: Session = Depends(get_db),
) -> SyncJobListResponse:
    _check_sync_monitor_viewer(current_user)
    query = db.query(SyncJobRun)
    if status_filter:
        query = query.filter(SyncJobRun.status == status_filter)
    if job_mode:
        query = query.filter(SyncJobRun.job_mode == job_mode)
    if job_name:
        query = query.filter(SyncJobRun.job_name == job_name)
    total = query.count()
    rows = (
        query.order_by(SyncJobRun.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        SyncJobItem(
            batch_id=row.batch_id,
            job_name=row.job_name,
            job_mode=row.job_mode,
            status=row.status,
            trade_date=row.trade_date,
            started_at=row.started_at,
            finished_at=row.finished_at,
            basic_rows=row.basic_rows,
            daily_rows=row.daily_rows,
            weekly_rows=row.weekly_rows,
            monthly_rows=row.monthly_rows,
            report_rows=row.report_rows,
            failed_stock_count=row.failed_stock_count,
            error_message=row.error_message,
        )
        for row in rows
    ]
    return SyncJobListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/sync-tasks", response_model=SyncTaskListResponse)
def list_sync_tasks(
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    task_type: str | None = Query(None),
    trigger_type: str | None = Query(None),
    trade_date_from: str | None = Query(None, description="YYYY-MM-DD"),
    trade_date_to: str | None = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> SyncTaskListResponse:
    """子任务状态列表（任务驱动表 sync_task）。"""
    _check_sync_monitor_viewer(current_user)

    query = db.query(SyncTask)
    if status_filter:
        query = query.filter(SyncTask.status == status_filter)
    if task_type:
        query = query.filter(SyncTask.task_type == task_type)
    if trigger_type:
        query = query.filter(SyncTask.trigger_type == trigger_type)
    if trade_date_from:
        try:
            d0 = date.fromisoformat(trade_date_from)
            query = query.filter(SyncTask.trade_date >= d0)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="trade_date_from 格式无效")
    if trade_date_to:
        try:
            d1 = date.fromisoformat(trade_date_to)
            query = query.filter(SyncTask.trade_date <= d1)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="trade_date_to 格式无效")
    total = query.count()
    rows = (
        query.order_by(SyncTask.trade_date.desc(), SyncTask.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        SyncTaskItem(
            id=row.id,
            trade_date=row.trade_date,
            task_type=row.task_type,
            trigger_type=row.trigger_type,
            status=row.status,
            batch_id=row.batch_id,
            rows_affected=row.rows_affected,
            error_message=row.error_message,
            started_at=row.started_at,
            finished_at=row.finished_at,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return SyncTaskListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/sync-jobs/{batch_id}", response_model=SyncJobDetailResponse)
def get_sync_job_detail(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyncJobDetailResponse:
    _check_sync_monitor_viewer(current_user)
    row = db.query(SyncJobRun).filter(SyncJobRun.batch_id == batch_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批次号不存在")
    return SyncJobDetailResponse(
        batch_id=row.batch_id,
        job_name=row.job_name,
        job_mode=row.job_mode,
        status=row.status,
        trade_date=row.trade_date,
        started_at=row.started_at,
        finished_at=row.finished_at,
        basic_rows=row.basic_rows,
        daily_rows=row.daily_rows,
        weekly_rows=row.weekly_rows,
        monthly_rows=row.monthly_rows,
        report_rows=row.report_rows,
        failed_stock_count=row.failed_stock_count,
        error_message=row.error_message,
        stock_total=row.stock_total,
        extra_json=row.extra_json,
    )
