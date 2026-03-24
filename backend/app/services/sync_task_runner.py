"""交易日自动同步：由 sync_task 子任务表驱动，汇总写入 sync_job_run。"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import StockBasic, SyncJobRun, SyncTask
from app.services.stock_basic_sync_service import run_sync_basic_only
from app.services.stock_daily_bar_sync_service import sync_daily_bars
from app.services.stock_monthly_bar_sync_service import sync_monthly_bars_batch
from app.services.stock_weekly_bar_sync_service import sync_weekly_bars_batch
from app.services.stock_indicator_fill_service import fill_after_sync
from app.services.stock_sync_utils import get_month_last_open_date, get_week_last_open_date
from app.services.stock_sync_orchestrator import _build_error_message

logger = logging.getLogger(__name__)


def _fill_indicators_safe(
    db: Session,
    timeframe: str,
    *,
    anchor_date: date,
    limit: int | None,
) -> None:
    """行情写入成功后填充均线/MACD；失败仅记日志，不推翻子任务成功状态。"""
    try:
        fill_after_sync(db, timeframe, anchor_date=anchor_date, limit=limit)  # type: ignore[arg-type]
    except Exception:
        logger.exception("指标填充失败（子任务已成功）timeframe=%s anchor=%s", timeframe, anchor_date)

# 定时自动任务类型顺序（不声明强依赖，但基础信息优先有利于后续模块）
AUTO_TASK_TYPES: list[str] = ["basic", "daily", "weekly", "monthly"]


def ensure_auto_tasks_for_trade_date(db: Session, trade_date: date) -> None:
    """为指定交易日插入 auto 子任务（幂等：已存在则跳过）。"""
    for task_type in AUTO_TASK_TYPES:
        exists = (
            db.query(SyncTask)
            .filter(
                SyncTask.trade_date == trade_date,
                SyncTask.task_type == task_type,
                SyncTask.trigger_type == "auto",
            )
            .first()
        )
        if exists is None:
            db.add(
                SyncTask(
                    trade_date=trade_date,
                    task_type=task_type,
                    trigger_type="auto",
                    status="pending",
                )
            )
    db.commit()


def mark_stale_running_sync_tasks_failed(db: Session, *, max_age_hours: int = 2) -> int:
    """将长时间停留在 running 的子任务标为失败（进程中断时）。"""
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    rows = (
        db.query(SyncTask)
        .filter(SyncTask.status == "running", SyncTask.started_at.isnot(None), SyncTask.started_at < cutoff)
        .all()
    )
    for row in rows:
        row.status = "failed"
        row.finished_at = datetime.now()
        row.error_message = (
            row.error_message or ""
        ) + "；任务未正常结束（可能进程中断），已标记为失败，不自动重试。"
    if rows:
        db.commit()
        logger.warning("已将 %s 条超时仍为 running 的 sync_task 标为 failed", len(rows))
    return len(rows)


def execute_pending_auto_sync(db: Session, trade_date: date, *, limit: int | None = None) -> dict[str, Any]:
    """
    执行当日所有 status=pending 的 auto 子任务，并写入一条 sync_job_run。
    若无 pending（例如已全部成功），则不创建 job_run，返回 skipped。
    """
    pending = (
        db.query(SyncTask)
        .filter(
            SyncTask.trade_date == trade_date,
            SyncTask.trigger_type == "auto",
            SyncTask.status == "pending",
        )
        .all()
    )
    if not pending:
        logger.info("无待执行 auto 子任务 trade_date=%s（可能已全部完成或已失败）", trade_date)
        return {"skipped": True, "reason": "no_pending_tasks"}

    order_index = {t: i for i, t in enumerate(AUTO_TASK_TYPES)}
    pending.sort(key=lambda x: order_index.get(x.task_type, 99))

    batch_id = f"stock-auto-{trade_date.strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}"
    job = SyncJobRun(
        job_name="stock_sync_auto",
        job_mode="incremental",
        trade_date=trade_date,
        batch_id=batch_id,
        status="running",
        extra_json={"modules": {}, "task_driven": True},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    stats = {
        "basic_rows": 0,
        "daily_rows": 0,
        "weekly_rows": 0,
        "monthly_rows": 0,
        "report_rows": 0,
    }
    module_status: dict[str, str] = {}

    for task in pending:
        task_id = task.id
        ttype = task.task_type
        task.batch_id = batch_id
        task.status = "running"
        task.started_at = datetime.now()
        task.error_message = None
        db.commit()

        try:
            result = _run_module_by_type(
                db,
                ttype,
                trade_date=trade_date,
                batch_id=batch_id,
                limit=limit,
            )
            rows = _rows_from_result(ttype, result)
            task = db.query(SyncTask).filter(SyncTask.id == task_id).one()
            task.status = "success"
            task.rows_affected = rows
            task.finished_at = datetime.now()
            module_status[ttype] = "success"
            _merge_stats(stats, ttype, rows)
        except Exception as exc:
            logger.exception("子任务失败 trade_date=%s type=%s", trade_date, ttype)
            db.rollback()
            task = db.query(SyncTask).filter(SyncTask.id == task_id).one()
            task.status = "failed"
            task.error_message = str(exc)[:2000]
            task.finished_at = datetime.now()
            module_status[ttype] = "failed"

        db.commit()

        job = db.query(SyncJobRun).filter(SyncJobRun.batch_id == batch_id).one()
        job.basic_rows = stats["basic_rows"]
        job.daily_rows = stats["daily_rows"]
        job.weekly_rows = stats["weekly_rows"]
        job.monthly_rows = stats["monthly_rows"]
        job.report_rows = stats["report_rows"]
        codes = _list_codes(db, limit=limit)
        job.stock_total = len(codes)
        job.extra_json = {"modules": dict(module_status), "task_driven": True}
        db.commit()

    job = db.query(SyncJobRun).filter(SyncJobRun.batch_id == batch_id).one()
    status = "success"
    if any(v == "failed" for v in module_status.values()):
        status = "partial_failed" if any(v == "success" for v in module_status.values()) else "failed"
    job.status = status
    job.finished_at = datetime.now()
    failed_tasks = (
        db.query(SyncTask)
        .filter(SyncTask.batch_id == batch_id, SyncTask.status == "failed")
        .all()
    )
    err_parts = [f"[{t.task_type}] {t.error_message or '未知错误'}" for t in failed_tasks]
    job.error_message = _build_error_message(err_parts, module_status, 0, status)
    db.commit()

    return {
        "skipped": False,
        "batch_id": batch_id,
        "trade_date": trade_date,
        "status": status,
        **stats,
    }


def _list_codes(db: Session, *, limit: int | None = None) -> list[str]:
    query = db.query(StockBasic.code).order_by(StockBasic.code)
    if limit is not None:
        query = query.limit(limit)
    return [code for (code,) in query.all()]


def _run_module_by_type(
    db: Session,
    task_type: str,
    *,
    trade_date: date,
    batch_id: str,
    limit: int | None,
) -> dict[str, int]:
    if task_type == "basic":
        return run_sync_basic_only(db, limit=limit)
    if task_type == "daily":
        codes = _list_codes(db, limit=limit)
        if not codes:
            raise RuntimeError("未找到可同步的股票基础信息，请先同步 stock_basic")
        out = sync_daily_bars(db, codes=codes, trade_date=trade_date, batch_id=batch_id)
        _fill_indicators_safe(db, "daily", anchor_date=trade_date, limit=limit)
        return out
    if task_type == "weekly":
        out = sync_weekly_bars_batch(db, trade_date=trade_date, batch_id=batch_id)
        weekly_anchor = get_week_last_open_date(trade_date) or trade_date
        _fill_indicators_safe(db, "weekly", anchor_date=weekly_anchor, limit=limit)
        return out
    if task_type == "monthly":
        out = sync_monthly_bars_batch(db, trade_date=trade_date, batch_id=batch_id)
        monthly_anchor = get_month_last_open_date(trade_date) or trade_date
        _fill_indicators_safe(db, "monthly", anchor_date=monthly_anchor, limit=limit)
        return out
    raise ValueError(f"未知任务类型: {task_type}")


def _rows_from_result(task_type: str, result: dict[str, int]) -> int:
    key_map = {
        "basic": "basic_rows",
        "daily": "daily_rows",
        "weekly": "weekly_rows",
        "monthly": "monthly_rows",
    }
    key = key_map.get(task_type)
    if key and key in result:
        return int(result[key])
    return int(sum(result.values()) or 0)


def _merge_stats(stats: dict[str, int], task_type: str, rows: int) -> None:
    key_map = {
        "basic": "basic_rows",
        "daily": "daily_rows",
        "weekly": "weekly_rows",
        "monthly": "monthly_rows",
    }
    k = key_map.get(task_type)
    if k:
        stats[k] = rows
