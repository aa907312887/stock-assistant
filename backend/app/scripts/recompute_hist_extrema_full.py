"""本机全量重算 stock_basic 历史最高价/最低价（无 HTTP）。

用法（在 backend 目录下，已配置 PYTHONPATH 或虚拟环境）::

    python -m app.scripts.recompute_hist_extrema_full

执行前请已在数据库运行 scripts/add_stock_basic_hist_extrema.sql。
"""

from __future__ import annotations

import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from app.database import SessionLocal
from app.services.stock_hist_extrema_service import run_full_recompute


def main() -> int:
    db = SessionLocal()
    try:
        t0 = time.perf_counter()
        result = run_full_recompute(db)
        elapsed = time.perf_counter() - t0
        print(
            f"历史极值全量完成: updated_rows={result.get('updated_rows')} "
            f"codes_with_daily={result.get('codes_with_daily')} "
            f"elapsed_sec={result.get('elapsed_sec')} (wall {elapsed:.2f}s)"
        )
        return 0 if result.get("ok") else 1
    except Exception as e:
        logging.exception("历史极值全量失败: %s", e)
        print(f"失败: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
