"""股票同步总编排：模块调度、批次记录与状态汇总。"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.models import StockBasic, SyncJobRun
from app.services.stock_basic_sync_service import run_sync_basic_only
from app.services.stock_daily_bar_sync_service import sync_daily_bars
from app.services.stock_financial_sync_service import sync_financial_reports
from app.services.stock_monthly_bar_sync_service import sync_monthly_bars
from app.services.stock_indicator_fill_service import (
    fill_after_sync,
    fill_indicators_for_timeframe,
)
from app.services.stock_sync_utils import get_month_last_open_date, get_week_last_open_date
from app.services.stock_weekly_bar_sync_service import sync_weekly_bars
from app.services.market_temperature.temperature_job_service import (
    rebuild_temperature_range,
    run_incremental_temperature_job,
)
from app.services.tushare_client import get_latest_open_trade_date, get_open_trade_dates

logger = logging.getLogger(__name__)


def _fill_market_temperature_followup_safe(
    db: Session,
    *,
    mode: str,
    modules: list[str],
    start_date: date | None,
    end_date: date | None,
) -> None:
    """行情与指标写入后联动大盘温度（指数日线 + 公式重算）；失败仅记日志。"""
    if "daily" not in modules:
        return
    try:
        if mode == "backfill" and start_date is not None and end_date is not None:
            rebuild_temperature_range(
                db, start_date, end_date, force_refresh_source=True
            )
        elif mode == "incremental":
            run_incremental_temperature_job(db)
    except Exception:
        logger.exception(
            "大盘温度联动失败（股票行情已写入）mode=%s start=%s end=%s",
            mode,
            start_date,
            end_date,
        )


def _fill_indicators_safe_orchestrator(
    db: Session,
    timeframe: str,
    *,
    anchor_date: date,
    limit: int | None,
    sync_mode: str = "incremental",
    range_start: date | None = None,
    range_end: date | None = None,
) -> None:
    """K 线写入成功后填充指标；失败仅记日志。

    - incremental：仅重算锚点日前最近若干根（定时/单日增量）。
    - backfill：按 [range_start, range_end] 重算区间内各行（带历史前缀），与长区间行情回灌配套。
    """
    try:
        if sync_mode == "backfill" and range_start is not None and range_end is not None:
            fill_indicators_for_timeframe(
                db,
                timeframe,  # type: ignore[arg-type]
                mode="backfill",
                start_date=range_start,
                end_date=range_end,
                limit=limit,
            )
        else:
            fill_after_sync(db, timeframe, anchor_date=anchor_date, limit=limit)  # type: ignore[arg-type]
    except Exception:
        logger.exception(
            "指标填充失败（行情模块已成功）timeframe=%s anchor=%s mode=%s",
            timeframe,
            anchor_date,
            sync_mode,
        )

# 未显式指定 modules 时的默认：与定时任务 sync_task（AUTO_TASK_TYPES）一致——
# basic → daily → weekly → monthly；各周期行情写入成功后同编排内会填充该周期均线/MACD。
# 财报 financial 仍须显式传入 modules。
DEFAULT_MODULES = ["basic", "daily", "weekly", "monthly"]


def run_stock_sync(
    db: Session,
    *,
    batch_id: str | None = None,
    mode: str = "incremental",
    modules: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    requested_trade_date: date | None = None,
    limit: int | None = None,
) -> dict[str, object]:
    modules = modules or DEFAULT_MODULES.copy()
    batch_id = batch_id or f"stock-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    trade_date = _resolve_trade_date(requested_trade_date or end_date or date.today())
    job = SyncJobRun(
        job_name="stock_sync_daily",
        job_mode=mode,
        trade_date=trade_date,
        batch_id=batch_id,
        status="running",
        extra_json={"modules": {}},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info(
        "股票同步开始 batch_id=%s mode=%s modules=%s trade_date=%s start=%s end=%s",
        batch_id,
        mode,
        modules,
        trade_date,
        start_date,
        end_date,
    )
    print(
        f"[sync] 已开始 batch_id={batch_id} mode={mode} modules={modules} "
        f"周/月线回灌时每 5～10 批会打印进度，请勿误以为卡住。",
        flush=True,
    )

    def _persist_progress() -> None:
        """每完成一个模块即落库，避免任务长时间 running 时页面无任何中间状态。"""
        job.basic_rows = stats.get("basic_rows", 0)
        job.daily_rows = stats.get("daily_rows", 0)
        job.weekly_rows = stats.get("weekly_rows", 0)
        job.monthly_rows = stats.get("monthly_rows", 0)
        job.report_rows = stats.get("report_rows", 0)
        job.extra_json = {"modules": dict(module_status)}
        db.commit()
        db.refresh(job)

    errors: list[str] = []
    failed_stock_count = 0
    stats = {
        "basic_rows": 0,
        "daily_rows": 0,
        "weekly_rows": 0,
        "monthly_rows": 0,
        "report_rows": 0,
    }
    module_status: dict[str, str] = {}

    try:
        if "basic" in modules:
            _run_module(
                db,
                module_status,
                "basic",
                lambda: run_sync_basic_only(db, limit=limit),
                stats,
                errors,
            )
            _persist_progress()

        codes = _list_codes(db, limit=limit)
        job.stock_total = len(codes)
        db.commit()

        if not codes:
            raise RuntimeError("未找到可同步的股票基础信息，请先同步 stock_basic")

        if "daily" in modules:
            if mode == "backfill":
                if start_date is None or end_date is None:
                    raise ValueError("backfill 模式下 daily 模块必须提供 start_date 和 end_date")
                open_dates = get_open_trade_dates(start=start_date.strftime("%Y%m%d"), end=end_date.strftime("%Y%m%d"))
                total_daily = 0
                for current_date in open_dates:
                    total_daily += sync_daily_bars(
                        db,
                        codes=codes,
                        trade_date=current_date,
                        batch_id=batch_id,
                    )["daily_rows"]
                stats["daily_rows"] = total_daily
                module_status["daily"] = "success"
                _persist_progress()
            else:
                _run_module(
                    db,
                    module_status,
                    "daily",
                    lambda: sync_daily_bars(db, codes=codes, trade_date=trade_date, batch_id=batch_id),
                    stats,
                    errors,
                )
            _persist_progress()
            if module_status.get("daily") == "success":
                _fill_indicators_safe_orchestrator(
                    db,
                    "daily",
                    anchor_date=end_date or trade_date,
                    limit=limit,
                    sync_mode=mode,
                    range_start=start_date,
                    range_end=end_date,
                )

        if "weekly" in modules:
            _run_module(
                db,
                module_status,
                "weekly",
                lambda: sync_weekly_bars(
                    db,
                    codes=codes,
                    end_date=end_date or trade_date,
                    start_date=start_date,
                    batch_id=batch_id,
                    mode=mode,
                ),
                stats,
                errors,
            )
            _persist_progress()
            if module_status.get("weekly") == "success":
                weekly_anchor = get_week_last_open_date(end_date or trade_date) or (end_date or trade_date)
                _fill_indicators_safe_orchestrator(
                    db,
                    "weekly",
                    anchor_date=weekly_anchor,
                    limit=limit,
                    sync_mode=mode,
                    range_start=start_date,
                    range_end=end_date,
                )

        if "monthly" in modules:
            _run_module(
                db,
                module_status,
                "monthly",
                lambda: sync_monthly_bars(
                    db,
                    codes=codes,
                    end_date=end_date or trade_date,
                    start_date=start_date,
                    batch_id=batch_id,
                    mode=mode,
                ),
                stats,
                errors,
            )
            _persist_progress()
            if module_status.get("monthly") == "success":
                monthly_anchor = get_month_last_open_date(end_date or trade_date) or (end_date or trade_date)
                _fill_indicators_safe_orchestrator(
                    db,
                    "monthly",
                    anchor_date=monthly_anchor,
                    limit=limit,
                    sync_mode=mode,
                    range_start=start_date,
                    range_end=end_date,
                )

        if "financial" in modules:
            result = _run_module(
                db,
                module_status,
                "financial",
                lambda: sync_financial_reports(
                    db,
                    codes=codes,
                    end_date=end_date or trade_date,
                    start_date=start_date,
                    batch_id=batch_id,
                ),
                stats,
                errors,
            )
            failed_stock_count += int(result.get("failed_stock_count", 0))
            if failed_stock_count > 0:
                errors.append(f"财报模块有 {failed_stock_count} 只股票接口拉取失败（详见日志）")
            _persist_progress()

        _fill_market_temperature_followup_safe(
            db,
            mode=mode,
            modules=modules,
            start_date=start_date,
            end_date=end_date,
        )

        status = "success"
        if any(value == "failed" for value in module_status.values()) or failed_stock_count > 0:
            status = "partial_failed"
        _finish_job(
            db,
            job,
            status=status,
            stats=stats,
            module_status=module_status,
            failed_stock_count=failed_stock_count,
            error_message=_build_error_message(errors, module_status, failed_stock_count, status),
        )
        return {"batch_id": batch_id, "trade_date": trade_date, "status": status, **stats}
    except Exception as exc:
        logger.exception("股票同步失败 batch=%s: %s", batch_id, exc)
        errors.append(str(exc))
        _finish_job(
            db,
            job,
            status="failed",
            stats=stats,
            module_status=module_status,
            failed_stock_count=failed_stock_count,
            error_message=_build_error_message(errors, module_status, failed_stock_count, "failed"),
        )
        raise


def _build_error_message(
    errors: list[str],
    module_status: dict[str, str],
    failed_stock_count: int,
    status: str,
) -> str | None:
    """汇总入库的错误摘要：模块异常、部分股票失败、或其它兜底说明。"""
    parts = [e for e in errors if e]
    if status == "partial_failed" and not parts:
        failed_names = [name for name, st in module_status.items() if st == "failed"]
        if failed_names:
            parts.append("以下模块失败：" + "、".join(failed_names))
        elif failed_stock_count > 0:
            parts.append(f"财报等模块有 {failed_stock_count} 只股票同步失败（详见日志）")
    if not parts:
        return None
    return "；".join(parts)


def _run_module(
    db: Session,
    module_status: dict[str, str],
    module_name: str,
    func: Callable[[], dict[str, int]],
    stats: dict[str, int],
    errors: list[str],
) -> dict[str, int]:
    try:
        result = func()
        for key, value in result.items():
            if key in stats:
                stats[key] += int(value)
        module_status[module_name] = "success"
        return result
    except Exception as exc:
        module_status[module_name] = "failed"
        errors.append(f"[{module_name}] {exc}")
        db.rollback()
        logger.exception("同步模块失败 module=%s", module_name)
        return {}


def _finish_job(
    db: Session,
    job: SyncJobRun,
    *,
    status: str,
    stats: dict[str, int],
    module_status: dict[str, str],
    failed_stock_count: int,
    error_message: str | None,
) -> None:
    job.status = status
    job.finished_at = datetime.now()
    job.basic_rows = stats.get("basic_rows", 0)
    job.daily_rows = stats.get("daily_rows", 0)
    job.weekly_rows = stats.get("weekly_rows", 0)
    job.monthly_rows = stats.get("monthly_rows", 0)
    job.report_rows = stats.get("report_rows", 0)
    job.failed_stock_count = failed_stock_count
    job.error_message = error_message
    job.extra_json = {"modules": module_status}
    db.commit()


def _list_codes(db: Session, *, limit: int | None = None) -> list[str]:
    query = db.query(StockBasic.code).order_by(StockBasic.code)
    if limit is not None:
        query = query.limit(limit)
    return [code for (code,) in query.all()]


def _resolve_trade_date(ref_date: date) -> date:
    resolved = get_latest_open_trade_date(ref_date)
    if resolved is None:
        raise RuntimeError(f"未找到 {ref_date} 之前的交易日")
    return resolved
