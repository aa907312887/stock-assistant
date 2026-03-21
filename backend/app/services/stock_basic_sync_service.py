"""仅同步股票基本信息（Tushare stock_basic → stock_basic 表）。"""
import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.scheduled_job_logging import log_sync_step_failure
from app.models import StockBasic
from app.services.tushare_client import TushareClientError, get_stock_list
from app.services.stock_sync_service import _safe_date

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
BATCH_PAUSE_SEC = 0.2


def run_sync_basic_only(db: Session, *, limit: int | None = None) -> dict[str, int]:
    """
    仅拉取股票列表并写入 stock_basic，不写行情与财报。
    """
    batch_tag = datetime.now().strftime("%Y%m%d-%H%M%S")
    sync_batch_id = f"basic-{batch_tag}"
    stats = {"stock_basic": 0}
    logger.info("stock_basic 仅基础同步开始 batch=%s limit=%s", sync_batch_id, limit)
    try:
        try:
            rows = get_stock_list()
        except TushareClientError as e:
            log_sync_step_failure(
                logger,
                business_callable="stock_basic_sync_service.run_sync_basic_only",
                step="拉取全市场股票列表",
                external_api="Tushare pro.stock_basic（上市列表 list_status=L）",
                exc=e,
            )
            raise
        if limit is not None:
            rows = rows[:limit]
        total_list = len(rows)
        for i, row in enumerate(rows):
            if i > 0 and i % BATCH_SIZE == 0:
                db.commit()
                logger.info("stock_basic 仅基础 进度 %s/%s", i, total_list)
                if BATCH_PAUSE_SEC > 0:
                    time.sleep(BATCH_PAUSE_SEC)
            dm = (row.get("dm") or "").strip()
            if not dm:
                continue
            mc = row.get("mc") or ""
            jys = row.get("jys") or ""
            region = row.get("region")
            ind_name = row.get("industry_name")
            list_d = _safe_date(row.get("list_date"))
            existing = db.query(StockBasic).filter(StockBasic.code == dm).first()
            if existing:
                existing.name = mc
                existing.market = jys
                if region is not None:
                    existing.region = region
                if ind_name is not None:
                    existing.industry_name = ind_name
                if list_d is not None:
                    existing.list_date = list_d
                existing.sync_batch_id = sync_batch_id
                existing.synced_at = datetime.now(timezone.utc)
                existing.data_source = "tushare"
            else:
                db.add(
                    StockBasic(
                        code=dm,
                        name=mc,
                        market=jys,
                        region=region,
                        industry_name=ind_name,
                        list_date=list_d,
                        sync_batch_id=sync_batch_id,
                        data_source="tushare",
                    )
                )
            stats["stock_basic"] += 1
        db.commit()
        logger.info("stock_basic 仅基础同步结束 写入=%s", stats["stock_basic"])
    except Exception:
        db.rollback()
        raise
    return stats
