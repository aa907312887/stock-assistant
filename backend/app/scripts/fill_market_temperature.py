"""初始化/回补大盘温度历史数据。"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from app.database import SessionLocal
from app.services.market_temperature.temperature_job_service import rebuild_temperature_range
from app.services.market_temperature.index_quote_service import sync_index_quotes


def main() -> None:
    parser = argparse.ArgumentParser(description="填充大盘温度历史数据")
    parser.add_argument("--years", type=int, default=3, help="入库年数")
    parser.add_argument("--warmup-years", type=int, default=1, help="预热年数")
    parser.add_argument("--version", type=str, default="v1.0.0", help="公式版本")
    args = parser.parse_args()

    end_date = date.today()
    start_date = end_date - timedelta(days=365 * args.years)
    warmup_start = start_date - timedelta(days=365 * args.warmup_years)

    db = SessionLocal()
    try:
        sync_rows = sync_index_quotes(db, warmup_start, end_date)
        result = rebuild_temperature_range(db, warmup_start, end_date, formula_version=args.version)
        print(
            {
                "sync_rows": sync_rows,
                "rows_updated": result.get("rows_updated", 0),
                "start_date": str(warmup_start),
                "end_date": str(end_date),
                "formula_version": args.version,
            }
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
