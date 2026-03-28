"""初始化/回补大盘温度历史数据。"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from app.database import SessionLocal
from app.services.market_temperature.temperature_job_service import rebuild_temperature_range
from app.services.market_temperature.index_quote_service import sync_index_quotes


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "拉取指数日线并计算大盘温度（写入 market_temperature_*）。"
            "可用 --start-date/--end-date 指定区间，或用 --years 从今日往前推算。"
        )
    )
    parser.add_argument("--years", type=int, default=3, help="未指定起止日时：从今日往前推算的入库年数（默认 3）")
    parser.add_argument("--warmup-years", type=int, default=1, help="在计算区间之前多拉的指数预热年数，供公式用历史窗口")
    parser.add_argument("--version", type=str, default="v1.0.0", help="公式版本")
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="计算区间起始 YYYY-MM-DD（须与 --end-date 同用）",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="计算区间结束 YYYY-MM-DD（须与 --start-date 同用）",
    )
    args = parser.parse_args()

    if (args.start_date is None) ^ (args.end_date is None):
        print("错误：--start-date 与 --end-date 须同时提供或同时省略", file=sys.stderr)
        sys.exit(2)

    if args.start_date and args.end_date:
        try:
            start_date = date.fromisoformat(args.start_date)
            end_date = date.fromisoformat(args.end_date)
        except ValueError:
            print("日期格式须为 YYYY-MM-DD", file=sys.stderr)
            sys.exit(2)
        if start_date > end_date:
            print("错误：start_date 不能晚于 end_date", file=sys.stderr)
            sys.exit(2)
    else:
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
