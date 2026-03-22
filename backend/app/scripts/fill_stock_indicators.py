"""命令行：手工触发均线/MACD 回填（见 specs/006-技术指标扩展）。"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime

from app.database import SessionLocal
from app.models import StockDailyBar, StockMonthlyBar, StockWeeklyBar
from app.services.stock_indicator_fill_service import fill_indicators_for_timeframe
from app.services.tushare_client import get_latest_open_trade_date

_BAR_MODEL = {
    "daily": StockDailyBar,
    "weekly": StockWeeklyBar,
    "monthly": StockMonthlyBar,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="在已有 K 线行上填充均线与 MACD（UPDATE bar 表）。不拉取行情。",
        epilog=(
            "若 K 线表为空，请先执行 `python -m app.scripts.sync_stock`（默认已含日/周/月行情；"
            "历史回灌需 `--preset three-year` 或 backfill 日期区间）。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["incremental", "backfill", "full"],
        required=True,
        help="incremental=最近窗口；backfill=日期区间内；full=该周期表内每只股票全部 K 线",
    )
    parser.add_argument(
        "--timeframe",
        action="append",
        choices=["daily", "weekly", "monthly"],
        dest="timeframes",
        help="可多次指定；默认三者",
    )
    parser.add_argument("--trade-date", dest="trade_date", help="incremental 锚定日 YYYY-MM-DD，默认今日")
    parser.add_argument("--start-date", dest="start_date", help="仅 backfill 需要")
    parser.add_argument("--end-date", dest="end_date", help="仅 backfill 需要")
    parser.add_argument("--limit", type=int, default=None, help="仅处理前 N 只股票（小范围试跑建议 3～10）")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="打印每只标的的 K 线根数、区间、末根 close/ma5/macd 等明细（适合配合 --limit）",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True,
    )
    logging.getLogger("app.services.stock_indicator_fill_service").setLevel(log_level)

    trade_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
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

    tfs = args.timeframes or ["daily", "weekly", "monthly"]
    logging.getLogger(__name__).info(
        "开始执行 mode=%s timeframes=%s limit=%s verbose=%s",
        args.mode,
        tfs,
        args.limit,
        args.verbose,
    )
    db = SessionLocal()
    try:
        empty_tf: list[str] = []
        for tf in tfs:
            if db.query(_BAR_MODEL[tf]).count() == 0:
                empty_tf.append(tf)
        tfs_run = [tf for tf in tfs if tf not in empty_tf]
        if not tfs_run:
            print(
                "错误：所选周期 K 线表均为空。本脚本只写入指标列，不会从 Tushare 拉取任何 K 线。\n"
                "请先（在 backend 目录）执行例如（默认已含日/周/月增量）：\n"
                "  python -m app.scripts.sync_stock\n"
                "若需灌历史，再使用：\n"
                "  python -m app.scripts.sync_stock --preset three-year\n"
                "或：\n"
                "  python -m app.scripts.sync_stock --mode backfill --start-date YYYY-MM-DD --end-date YYYY-MM-DD",
                file=sys.stderr,
            )
            sys.exit(2)
        if empty_tf:
            print(
                "警告：以下周期表当前无数据，已跳过：" + "、".join(empty_tf),
                file=sys.stderr,
            )
        for tf in tfs_run:
            if args.mode == "incremental":
                anchor = trade_date or date.today()
                anchor = get_latest_open_trade_date(anchor) or anchor
                r = fill_indicators_for_timeframe(
                    db,
                    tf,
                    mode="incremental",
                    trade_date_anchor=anchor,
                    limit=args.limit,
                    verbose=args.verbose,
                )
            elif args.mode == "backfill":
                if start_date is None or end_date is None:
                    print("backfill 必须提供 --start-date 与 --end-date", file=sys.stderr)
                    sys.exit(1)
                r = fill_indicators_for_timeframe(
                    db,
                    tf,
                    mode="backfill",
                    start_date=start_date,
                    end_date=end_date,
                    limit=args.limit,
                    verbose=args.verbose,
                )
            else:
                r = fill_indicators_for_timeframe(
                    db,
                    tf,
                    mode="full",
                    limit=args.limit,
                    verbose=args.verbose,
                )
            logging.getLogger(__name__).info("周期完成 %s 结果=%s", tf, r)
        if empty_tf:
            logging.getLogger(__name__).info("已跳过无数据的周期: %s", empty_tf)
    finally:
        db.close()
        logging.getLogger(__name__).info("全部结束")


if __name__ == "__main__":
    main()
