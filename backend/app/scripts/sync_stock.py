"""命令行执行股票同步。"""

import argparse
import logging
import os
import sys
from datetime import date, datetime

# 命令行运行时把进度打到控制台
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from app.database import SessionLocal
from app.models import StockDailyBar, StockMonthlyBar, StockWeeklyBar
from app.services.stock_sync_orchestrator import DEFAULT_MODULES, run_stock_sync
from app.services.stock_sync_utils import subtract_years


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "执行股票同步：从 Tushare 拉行情写入 bar 表。默认与定时任务一致："
            "basic + daily + weekly + monthly（各周期写入后会填充该周期均线/MACD）。"
        ),
        epilog=(
            "历史回灌：`--preset three-year`（约近三年）、`--preset since-2019`（2019-01-01 至今日），"
            "或 `--mode backfill` + `--start-date` / `--end-date`。"
            "同区间重复执行时，行情按唯一键 upsert，指标按区间重算覆盖，可安全重跑。"
            "仅跑 `fill_stock_indicators` 不会拉取任何 K 线。"
            "若只想同步部分模块，可传 `--modules basic daily` 等覆盖默认。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--mode", choices=["incremental", "backfill"], default="incremental")
    parser.add_argument(
        "--preset",
        choices=["none", "three-year", "since-2019"],
        default="none",
        help="three-year：回灌约近三年；since-2019：2019-01-01 至今日（需 Tushare 积分与较长耗时）",
    )
    parser.add_argument("--start-date", dest="start_date")
    parser.add_argument("--end-date", dest="end_date")
    parser.add_argument("--modules", nargs="*", default=None)
    parser.add_argument("trade_date", nargs="?", help="兼容旧用法：YYYY-MM-DD")
    args = parser.parse_args()

    trade_date = None
    start_date = None
    end_date = None
    try:
        if args.trade_date:
            trade_date = datetime.strptime(args.trade_date, "%Y-%m-%d").date()
        if args.start_date:
            start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        if args.end_date:
            end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    except ValueError:
        print("日期格式必须为 YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)

    mode = args.mode
    modules = args.modules
    if args.preset == "three-year":
        mode = "backfill"
        end_date = date.today()
        start_date = subtract_years(end_date, 3)
        if modules is None:
            modules = ["basic", "daily", "weekly", "monthly"]

    if args.preset == "since-2019":
        mode = "backfill"
        end_date = date.today()
        start_date = date(2019, 1, 1)
        if modules is None:
            modules = ["basic", "daily", "weekly", "monthly"]

    if mode == "backfill" and (start_date is None or end_date is None):
        print(
            "backfill 模式必须提供 --start-date 和 --end-date，或使用 --preset three-year / since-2019",
            file=sys.stderr,
        )
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
        stats = run_stock_sync(
            db,
            mode=mode,
            modules=modules,
            start_date=start_date,
            end_date=end_date,
            requested_trade_date=trade_date,
            limit=limit,
        )
        print("OK", stats)
        nd = db.query(StockDailyBar).count()
        nw = db.query(StockWeeklyBar).count()
        nm = db.query(StockMonthlyBar).count()
        print(
            f"当前库内 K 线行数: daily={nd} weekly={nw} monthly={nm} "
            f"(本次任务 daily_rows={stats.get('daily_rows', 0)} weekly_rows={stats.get('weekly_rows', 0)})"
        )
        eff_mod = modules if modules is not None else list(DEFAULT_MODULES)
        if nw == 0:
            if "weekly" not in eff_mod:
                print(
                    "提示: 本次任务未包含 weekly，周线表仍为空属正常；需要周/月线请使用 "
                    "`--preset three-year` 或 `--modules basic daily weekly monthly`。",
                    file=sys.stderr,
                )
            elif stats.get("weekly_rows", 0) == 0:
                print(
                    "提示: 任务已包含 weekly 但本次写入 0 行，请查日志中 stk_weekly_monthly 与 Tushare 积分。",
                    file=sys.stderr,
                )
        if stats.get("daily_rows", 0) == 0 and nd == 0 and "daily" in eff_mod:
            print(
                "提示: 本次未写入任何日线，请检查 backend/.env 中 TUSHARE_TOKEN、"
                "交易日是否为开市日、以及日志中 Tushare 是否返回空数据。",
                file=sys.stderr,
            )
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
