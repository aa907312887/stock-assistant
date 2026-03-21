"""验证 Tushare 核心接口（股票列表/日线/利润表）能否拉取到数据（不写库）。"""
import sys
from datetime import date, datetime


def main() -> None:
    trade_date = date.today()
    if len(sys.argv) > 1:
        try:
            trade_date = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        except ValueError:
            print("Usage: python -m app.scripts.test_tushare_api [YYYY-MM-DD]", file=sys.stderr)
            sys.exit(1)

    from app.config import settings
    from app.services.tushare_client import (
        TushareClientError,
        get_daily_by_trade_date,
        get_fin_income,
        get_stock_list,
        normalize_daily_bar,
    )

    token = (settings.tushare_token or "").strip()
    if not token:
        print("请设置环境变量 TUSHARE_TOKEN 或在 backend/.env 中配置 TUSHARE_TOKEN", file=sys.stderr)
        sys.exit(1)

    print("trade_date:", trade_date)
    print()

    try:
        rows = get_stock_list()
        print("stock_basic: 条数 =", len(rows))
        if rows:
            print("  首条:", rows[0])
    except TushareClientError as e:
        print("stock_basic 失败:", e)
        sys.exit(1)

    if rows:
        code = rows[0].get("dm")
        if code:
            try:
                daily_map = get_daily_by_trade_date(trade_date)
                print(f"daily({trade_date}): 条数 =", len(daily_map))
                raw = daily_map.get(code)
                bar = normalize_daily_bar(raw)
                if raw:
                    print("  示例代码", code, "原始字段 keys:", list(raw.keys())[:12], "...")
                if bar:
                    print("  归一化示例:", {k: bar[k] for k in list(bar)[:8]})
            except TushareClientError as e:
                print("daily 失败:", e)

            try:
                fin = get_fin_income(
                    code,
                    start=f"{max(trade_date.year - 2, 2000)}0101",
                    end=trade_date.strftime("%Y%m%d"),
                )
                print(f"income({code}): 条数 =", len(fin))
                if fin:
                    print("  首条 keys:", list(fin[0].keys())[:16], "...")
            except TushareClientError as e:
                print("income 失败:", e)

    print("\nTushare 接口验证完成，可进行完整同步（需配置 DATABASE_URL 并执行 python -m app.scripts.sync_stock）。")


if __name__ == "__main__":
    main()
