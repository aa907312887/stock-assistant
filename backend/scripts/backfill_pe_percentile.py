"""手动全量回填 PE 历史百分位（pe_percentile）。

用法:
    cd backend
    python scripts/backfill_pe_percentile.py

可选参数（环境变量）:
    LIMIT=100   只处理前 N 只股票（调试用）
"""

import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import StockDailyBar
from app.services.stock_pe_percentile_service import (
    _recompute_pe_percentile_for_code,
)

LOG_FILE = Path(__file__).resolve().parent / "backfill_pe_percentile.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("backfill_pe_percentile")


def run(limit: int | None = None) -> None:
    db = SessionLocal()
    query = db.query(StockDailyBar.stock_code).distinct().order_by(StockDailyBar.stock_code)
    if limit:
        query = query.limit(limit)
    codes = [c[0] for c in query.all()]

    total = len(codes)
    total_rows = 0
    failed = 0
    t0 = time.time()

    logger.info("=" * 60)
    logger.info("PE 历史百分位回填开始")
    logger.info("股票总数: %d", total)
    logger.info("日志文件: %s", LOG_FILE)
    logger.info("=" * 60)

    for idx, code in enumerate(codes, 1):
        try:
            rows = _recompute_pe_percentile_for_code(db, code)
            total_rows += rows
            db.commit()
        except Exception as exc:
            failed += 1
            db.rollback()
            logger.warning("[%d/%d] %s  回填失败: %s", idx, total, code, exc)
            continue

        elapsed = time.time() - t0
        speed = idx / elapsed if elapsed > 0 else 0
        eta = (total - idx) / speed if speed > 0 else 0

        if idx % 50 == 0 or idx == total:
            logger.info(
                "[%d/%d] %s  |  累计更新 %d 行, 失败 %d  |  %.1f 只/分  ETA %.0f 分钟",
                idx, total, code,
                total_rows, failed,
                speed * 60, eta / 60,
            )

    db.close()
    elapsed = time.time() - t0

    logger.info("=" * 60)
    logger.info("回填完成!")
    logger.info("更新: %d 行  |  失败: %d 只  |  耗时: %.1f 分钟", total_rows, failed, elapsed / 60)
    logger.info("=" * 60)


if __name__ == "__main__":
    limit = int(os.environ.get("LIMIT", "0")) or None
    run(limit=limit)
