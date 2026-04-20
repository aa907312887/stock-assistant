"""命令行执行指数同步（index_basic / 日周月 K / index_weight）。"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from app.constants.index_sync_allowlist import PRESET_COMMON_INDEX_TS_CODES
from app.database import SessionLocal
from app.services.index_sync_service import run_index_sync


def main() -> None:
    parser = argparse.ArgumentParser(
        description="指数数据同步：与 specs/024-指数专题 plan 一致，支持 incremental / backfill。",
    )
    parser.add_argument("--mode", choices=["incremental", "backfill"], default="incremental")
    parser.add_argument("--modules", nargs="+", default=["basic", "daily"], help="basic daily weekly monthly weight")
    parser.add_argument("--start-date", dest="start_date")
    parser.add_argument("--end-date", dest="end_date")
    parser.add_argument(
        "--limit-codes",
        type=int,
        default=None,
        help="仅处理前 N 个指数 ts_code（调试或控制单次时长）",
    )
    parser.add_argument(
        "--preset",
        choices=["common"],
        default=None,
        help="common=A 股六大常见指数（上证/深证成指/创业板/科创50/沪深300/中证500）",
    )
    parser.add_argument(
        "--ts-codes",
        dest="ts_codes",
        default=None,
        help="逗号或空格分隔的 ts_code，仅同步列表中的指数（可与 --preset 叠加后去重）",
    )
    args = parser.parse_args()

    start_date = None
    end_date = None
    try:
        if args.start_date:
            start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        if args.end_date:
            end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    except ValueError:
        print("日期格式必须为 YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)

    if args.mode == "backfill" and (
        "weekly" in args.modules or "monthly" in args.modules or "weight" in args.modules
    ):
        if start_date is None or end_date is None:
            print("backfill 且包含 weekly/monthly/weight 时必须提供 --start-date 与 --end-date", file=sys.stderr)
            sys.exit(1)

    only_list: list[str] = []
    if args.preset == "common":
        only_list.extend(PRESET_COMMON_INDEX_TS_CODES)
    if args.ts_codes:
        only_list.extend(p for p in re.split(r"[\s,]+", args.ts_codes.strip()) if p)
    only_ts_codes = list(dict.fromkeys(only_list)) if only_list else None

    db = SessionLocal()
    try:
        out = run_index_sync(
            db,
            modules=args.modules,
            mode=args.mode,
            start_date=start_date,
            end_date=end_date,
            limit_codes=args.limit_codes,
            only_ts_codes=only_ts_codes,
        )
        print(json.dumps(out, default=str, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
