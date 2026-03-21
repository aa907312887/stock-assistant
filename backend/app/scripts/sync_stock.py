"""命令行执行一次股票同步。用法: python -m app.scripts.sync_stock [YYYY-MM-DD]
环境变量 SYNC_LIMIT: 若设置（如 100），仅同步前 N 条用于快速验证。"""
import logging
import os
import sys
from datetime import datetime

# 命令行运行时把进度打到控制台
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from app.database import SessionLocal
from app.services.stock_sync_service import run_sync


def main() -> None:
    trade_date = None
    if len(sys.argv) > 1:
        try:
            trade_date = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        except ValueError:
            print("Usage: python -m app.scripts.sync_stock [YYYY-MM-DD]", file=sys.stderr)
            sys.exit(1)
    limit = None
    try:
        limit = int(os.environ.get("SYNC_LIMIT", "") or 0)
        if limit <= 0:
            limit = None
    except ValueError:
        limit = None
    db = SessionLocal()
    try:
        stats = run_sync(db, trade_date=trade_date, limit=limit)
        print("OK", stats)
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
