"""APScheduler：交易日 17:00 股票数据同步；17:10/启动后大盘温度；17:20 冲高回落与恐慌回落战法自动选股落库。

历史累计高低（``cum_hist_*``）在日线写入流程内递推更新，无单独定时任务。
"""
import logging
from datetime import date, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.core.scheduled_job_logging import guess_tushare_api_from_exception, log_scheduled_job_failure
from app.database import SessionLocal
from app.models import SyncJobRun
from app.services.stock_sync_orchestrator import run_stock_sync
from app.services.sync_task_runner import (
    ensure_auto_tasks_for_trade_date,
    execute_pending_auto_sync,
    mark_stale_running_sync_tasks_failed,
)
from app.services.tushare_client import get_latest_open_trade_date
from app.services.market_temperature.temperature_job_service import run_incremental_temperature_job
from app.services.strategy.strategy_execute_service import StrategyDataNotReadyError, execute_strategy

logger = logging.getLogger(__name__)

# 定时任务已改为 sync_task 子任务表驱动；保留常量供日志说明
SCHEDULED_SYNC_MODULES = ["basic", "daily", "weekly", "monthly"]

_JOB_STOCK_SYNC = "stock_sync"
_ENTRY_SYNC = "app.core.scheduler._job_sync_stock"
_BUSINESS_RUN_SYNC = "app.services.stock_sync_service.run_sync"
_JOB_MARKET_TEMP = "market_temperature_sync"
_JOB_STRATEGY_CGHL = "strategy_chong_gao_hui_luo_daily"
_JOB_STRATEGY_PANIC = "strategy_panic_pullback_daily"

_scheduler: BackgroundScheduler | None = None
CRON_HOUR = 17
CRON_MINUTE = 0
TIMEZONE = "Asia/Shanghai"


def _job_sync_stock() -> None:
    """定时任务入口：交易日插入 auto 子任务并执行 pending（任务驱动）。"""
    today = date.today()
    latest = get_latest_open_trade_date(today)
    if latest is None or latest != today:
        logger.info("定时同步跳过：今日非交易日（最近开市日=%s）", latest)
        return
    db = SessionLocal()
    try:
        ensure_auto_tasks_for_trade_date(db, today)
        result = execute_pending_auto_sync(db, today)
        if result.get("skipped"):
            logger.info("定时同步无需执行：%s", result.get("reason", "skipped"))
            # 无 pending 子任务时不会走 sync_task_runner 末尾的大盘温度联动，在此补一次
            try:
                run_incremental_temperature_job(db)
                logger.info("大盘温度增量同步完成（无股票子任务分支）")
            except Exception as te:
                log_scheduled_job_failure(
                    logger,
                    job_id=_JOB_MARKET_TEMP,
                    scheduler_entry=_ENTRY_SYNC,
                    business_callable="run_incremental_temperature_job",
                    external_api=guess_tushare_api_from_exception(te),
                    exc=te,
                )
        else:
            logger.info(
                "定时同步完成 batch=%s status=%s",
                result.get("batch_id"),
                result.get("status"),
            )
    except Exception as e:
        log_scheduled_job_failure(
            logger,
            job_id=_JOB_STOCK_SYNC,
            scheduler_entry=_ENTRY_SYNC,
            business_callable="app.services.sync_task_runner.execute_pending_auto_sync",
            external_api=guess_tushare_api_from_exception(e),
            exc=e,
        )
    finally:
        db.close()


def _job_sync_market_temperature() -> None:
    """定时同步大盘温度（日频）。"""
    db = SessionLocal()
    try:
        result = run_incremental_temperature_job(db)
        logger.info("大盘温度定时同步完成 result=%s", result)
    except Exception as e:
        log_scheduled_job_failure(
            logger,
            job_id=_JOB_MARKET_TEMP,
            scheduler_entry="app.core.scheduler._job_sync_market_temperature",
            business_callable="app.services.market_temperature.temperature_job_service.run_incremental_temperature_job",
            external_api=guess_tushare_api_from_exception(e),
            exc=e,
        )
    finally:
        db.close()


def _job_strategy_chong_gao_hui_luo_daily() -> None:
    """定时任务：交易日每日筛选“冲高回落战法”的今日候选并落库。"""
    today = date.today()
    latest = get_latest_open_trade_date(today)
    if latest is None or latest != today:
        logger.info("冲高回落定时筛选跳过：今日非交易日（最近开市日=%s）", latest)
        return

    db = SessionLocal()
    try:
        # 依赖日线数据已同步到当天；若未就绪则跳过（避免写入不完整结果）
        execute_strategy(db, strategy_id="chong_gao_hui_luo", as_of_date=today)
        logger.info("冲高回落定时筛选完成 as_of_date=%s", today)
    except StrategyDataNotReadyError as e:
        logger.info("冲高回落定时筛选跳过：数据未就绪 as_of_date=%s reason=%s", today, e)
    except Exception as e:
        log_scheduled_job_failure(
            logger,
            job_id=_JOB_STRATEGY_CGHL,
            scheduler_entry="app.core.scheduler._job_strategy_chong_gao_hui_luo_daily",
            business_callable="app.services.strategy.strategy_execute_service.execute_strategy",
            external_api=None,
            exc=e,
        )
    finally:
        db.close()


def _job_strategy_panic_pullback_daily() -> None:
    """定时任务：交易日每日 17:20（上海时区）筛选「恐慌回落战法」当日候选并落库；规则与冲高回落定时任务相同。"""
    today = date.today()
    latest = get_latest_open_trade_date(today)
    if latest is None or latest != today:
        logger.info("恐慌回落定时筛选跳过：今日非交易日（最近开市日=%s）", latest)
        return

    db = SessionLocal()
    try:
        execute_strategy(db, strategy_id="panic_pullback", as_of_date=today)
        logger.info("恐慌回落定时筛选完成 as_of_date=%s", today)
    except StrategyDataNotReadyError as e:
        logger.info("恐慌回落定时筛选跳过：数据未就绪 as_of_date=%s reason=%s", today, e)
    except Exception as e:
        log_scheduled_job_failure(
            logger,
            job_id=_JOB_STRATEGY_PANIC,
            scheduler_entry="app.core.scheduler._job_strategy_panic_pullback_daily",
            business_callable="app.services.strategy.strategy_execute_service.execute_strategy",
            external_api=None,
            exc=e,
        )
    finally:
        db.close()


def _mark_stale_running_jobs_failed() -> None:
    """将长时间停留在 running 的记录标为失败，避免进程中断后页面永远显示运行中。"""
    db = SessionLocal()
    try:
        cutoff = datetime.now() - timedelta(hours=2)
        rows = (
            db.query(SyncJobRun)
            .filter(SyncJobRun.status == "running", SyncJobRun.started_at < cutoff)
            .all()
        )
        for row in rows:
            row.status = "failed"
            row.finished_at = datetime.now()
            row.error_message = (
                "任务未正常结束（进程中断或超时未写入完成状态）。"
                "若曾执行财报全市场逐标的同步，耗时可较长，请查看日志或缩小范围。"
            )
        if rows:
            db.commit()
            logger.warning("已将 %s 条超时仍为 running 的同步任务标为 failed", len(rows))
    finally:
        db.close()


def start_scheduler() -> None:
    """启动调度器，注册每日 17:00 的同步任务。"""
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone=TIMEZONE)
    _scheduler.add_job(
        _job_sync_stock,
        trigger=CronTrigger(hour=CRON_HOUR, minute=CRON_MINUTE, timezone=TIMEZONE),
        id=_JOB_STOCK_SYNC,
        replace_existing=True,
    )
    _scheduler.add_job(
        _job_sync_market_temperature,
        trigger=CronTrigger(hour=17, minute=10, timezone=TIMEZONE),
        id=_JOB_MARKET_TEMP,
        replace_existing=True,
    )
    _scheduler.add_job(
        _job_sync_market_temperature,
        trigger=DateTrigger(run_date=datetime.now() + timedelta(seconds=30), timezone=TIMEZONE),
        id=f"{_JOB_MARKET_TEMP}_bootstrap",
        replace_existing=True,
    )
    _scheduler.add_job(
        _job_strategy_chong_gao_hui_luo_daily,
        trigger=CronTrigger(hour=17, minute=20, timezone=TIMEZONE),
        id=_JOB_STRATEGY_CGHL,
        replace_existing=True,
    )
    _scheduler.add_job(
        _job_strategy_panic_pullback_daily,
        trigger=CronTrigger(hour=17, minute=20, timezone=TIMEZONE),
        id=_JOB_STRATEGY_PANIC,
        replace_existing=True,
    )
    _scheduler.start()
    _mark_stale_running_jobs_failed()
    _db = SessionLocal()
    try:
        mark_stale_running_sync_tasks_failed(_db)
    finally:
        _db.close()
    logger.info(
        "Scheduler started: stock_sync daily at %s:%s %s modules=%s; cum_hist 随日线写入递推（无独立 Job）",
        CRON_HOUR,
        CRON_MINUTE,
        TIMEZONE,
        SCHEDULED_SYNC_MODULES,
    )


def shutdown_scheduler() -> None:
    """关闭调度器。"""
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("Scheduler stopped")


def run_sync_once_now(
    *,
    batch_id: str | None = None,
    mode: str = "incremental",
    modules: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    requested_trade_date: date | None = None,
) -> None:
    """立即执行一次同步（供手动触发调用）。"""
    db = SessionLocal()
    try:
        run_stock_sync(
            db,
            batch_id=batch_id,
            mode=mode,
            modules=modules,
            start_date=start_date,
            end_date=end_date,
            requested_trade_date=requested_trade_date or date.today(),
        )
    finally:
        db.close()
