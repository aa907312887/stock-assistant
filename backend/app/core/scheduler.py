"""APScheduler：每日 17:00 执行股票数据同步。"""
import logging
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.scheduled_job_logging import guess_tushare_api_from_exception, log_scheduled_job_failure
from app.database import SessionLocal
from app.services.stock_sync_service import run_sync

logger = logging.getLogger(__name__)

_JOB_STOCK_SYNC = "stock_sync"
_ENTRY_SYNC = "app.core.scheduler._job_sync_stock"
_BUSINESS_RUN_SYNC = "app.services.stock_sync_service.run_sync"

_scheduler: BackgroundScheduler | None = None
CRON_HOUR = 17
CRON_MINUTE = 0
TIMEZONE = "Asia/Shanghai"


def _job_sync_stock() -> None:
    """定时任务入口：创建独立 Session 执行同步。"""
    db = SessionLocal()
    try:
        run_sync(db, trade_date=date.today())
    except Exception as e:
        log_scheduled_job_failure(
            logger,
            job_id=_JOB_STOCK_SYNC,
            scheduler_entry=_ENTRY_SYNC,
            business_callable=_BUSINESS_RUN_SYNC,
            external_api=guess_tushare_api_from_exception(e),
            exc=e,
        )
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
    _scheduler.start()
    logger.info("Scheduler started: stock_sync daily at %s:%s %s", CRON_HOUR, CRON_MINUTE, TIMEZONE)


def shutdown_scheduler() -> None:
    """关闭调度器。"""
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("Scheduler stopped")


def run_sync_once_now() -> None:
    """立即执行一次同步（供部署时或手动触发调用）。"""
    _job_sync_stock()
