"""验证 `fetch_pro_bar_qfq_daily`：仅 SDK `ts.pro_bar`（含 pandas 兼容补丁），不写库。"""

import argparse
import sys
from datetime import date, datetime


def main() -> None:
    parser = argparse.ArgumentParser(description="测试前复权日线拉取（pro_bar 优先）")
    parser.add_argument("--ts-code", default="000001.SZ", help="如 000001.SZ")
    parser.add_argument("--date", default="", help="单日 YYYY-MM-DD，默认今天")
    args = parser.parse_args()
    d = date.today()
    if args.date:
        try:
            d = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print("日期须为 YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)

    from app.services.tushare_client import TushareClientError, fetch_pro_bar_qfq_daily

    print("ts_code=", args.ts_code, "trade_date=", d)
    try:
        rows = fetch_pro_bar_qfq_daily(args.ts_code, d, d, limit=50)
    except TushareClientError as e:
        print("失败:", e)
        sys.exit(1)
    print("行数:", len(rows))
    if rows:
        print("首行样例:", rows[0])


if __name__ == "__main__":
    main()
