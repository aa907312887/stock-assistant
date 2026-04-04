"""手动同步全量财务数据（income + fina_indicator）。

用法:
    cd backend
    python scripts/manual_sync_financial.py

可选参数（环境变量）:
    LIMIT=100          只同步前 N 只股票（调试用）
    START_DATE=20200101 指定财报起始日期（默认: end_date 往前 3 年）
"""

import logging
import sys
import time
from datetime import date
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

from app.database import SessionLocal
from app.models import StockBasic, StockFinancialReport
from app.services.stock_sync_utils import safe_date, safe_decimal, safe_pct
from app.services.tushare_client import get_fin_income, get_fina_indicator

# ── 日志配置：同时输出到终端和文件 ──
LOG_FILE = Path(__file__).resolve().parent / "manual_sync_financial.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("manual_sync_financial")

FIN_REQ_PAUSE_SEC = 0.05


def _build_fina_indicator_map(rows: list[dict]) -> dict[date, dict]:
    result: dict[date, dict] = {}
    for row in rows:
        rd = safe_date(row.get("end_date"))
        if rd is not None:
            result[rd] = row
    return result


def run(limit: int | None = None, start_date_str: str | None = None) -> None:
    db = SessionLocal()

    query = db.query(StockBasic.code).order_by(StockBasic.code)
    if limit:
        query = query.limit(limit)
    codes = [c for (c,) in query.all()]

    end_date = date.today()
    end = end_date.strftime("%Y%m%d")
    if start_date_str:
        start = start_date_str
    else:
        start = date(2019, 1, 1).strftime("%Y%m%d")

    batch_id = f"manual-financial-{end}"
    total = len(codes)
    written = 0
    failed = 0
    t0 = time.time()

    logger.info("=" * 60)
    logger.info("财务数据同步开始")
    logger.info("股票总数: %d  报告期范围: %s ~ %s", total, start, end)
    logger.info("batch_id: %s", batch_id)
    logger.info("日志文件: %s", LOG_FILE)
    logger.info("=" * 60)

    for idx, code in enumerate(codes, 1):
        stock_written = 0

        # ── 1. 拉取利润表 ──
        try:
            income_rows = get_fin_income(code, start=start, end=end)
        except Exception as exc:
            failed += 1
            logger.warning("[%d/%d] %s  income 拉取失败: %s", idx, total, code, exc)
            continue

        # ── 2. 拉取财务指标（降级处理） ──
        fina_map: dict[date, dict] = {}
        try:
            fina_rows = get_fina_indicator(code, start=start, end=end)
            fina_map = _build_fina_indicator_map(fina_rows)
        except Exception as exc:
            logger.warning("[%d/%d] %s  fina_indicator 拉取失败（仅写 income）: %s", idx, total, code, exc)

        # ── 3. 合并并写入 ──
        all_report_dates: dict[date, dict] = {}
        for row in income_rows:
            rd = safe_date(row.get("end_date"))
            if rd is not None:
                all_report_dates[rd] = row
        for rd in fina_map:
            if rd not in all_report_dates:
                all_report_dates[rd] = {}

        for report_date, income_row in all_report_dates.items():
            fina_row = fina_map.get(report_date, {})

            revenue = safe_decimal(income_row.get("total_revenue"))
            oper_cost = safe_decimal(income_row.get("oper_cost"))
            net_profit = safe_decimal(income_row.get("n_income_attr_p")) or safe_decimal(income_row.get("n_income"))
            eps = safe_decimal(income_row.get("basic_eps")) or safe_decimal(income_row.get("diluted_eps"))
            gross_margin_calc = safe_pct(
                (revenue - oper_cost) if revenue is not None and oper_cost is not None else None,
                revenue,
            )

            ann_date = safe_date(fina_row.get("ann_date"))
            roe = safe_decimal(fina_row.get("roe"))
            roe_dt = safe_decimal(fina_row.get("roe_dt"))
            roe_waa = safe_decimal(fina_row.get("roe_waa"))
            roa = safe_decimal(fina_row.get("roa"))
            bps = safe_decimal(fina_row.get("bps"))
            net_margin = safe_decimal(fina_row.get("netprofit_margin"))
            debt_to_assets = safe_decimal(fina_row.get("debt_to_assets"))
            current_ratio = safe_decimal(fina_row.get("current_ratio"))
            quick_ratio = safe_decimal(fina_row.get("quick_ratio"))
            cfps = safe_decimal(fina_row.get("cfps"))
            ebit = safe_decimal(fina_row.get("ebit"))
            ocf_to_profit = safe_decimal(fina_row.get("ocf_to_profit"))

            fina_gross = safe_decimal(fina_row.get("grossprofit_margin"))
            gross_margin = fina_gross if fina_gross is not None else gross_margin_calc

            has_fina = bool(fina_row)
            report_type = "income+indicator" if has_fina else "income"

            payload = {
                "report_type": report_type,
                "ann_date": ann_date,
                "revenue": revenue,
                "net_profit": net_profit,
                "eps": eps,
                "bps": bps,
                "roe": roe,
                "roe_dt": roe_dt,
                "roe_waa": roe_waa,
                "roa": roa,
                "debt_to_assets": debt_to_assets,
                "current_ratio": current_ratio,
                "quick_ratio": quick_ratio,
                "gross_margin": gross_margin,
                "net_margin": net_margin,
                "cfps": cfps,
                "ebit": ebit,
                "ocf_to_profit": ocf_to_profit,
                "sync_batch_id": batch_id,
                "data_source": "tushare",
            }

            existing = (
                db.query(StockFinancialReport)
                .filter(
                    StockFinancialReport.stock_code == code,
                    StockFinancialReport.report_date == report_date,
                )
                .first()
            )
            if existing:
                for key, value in payload.items():
                    if value is not None:
                        setattr(existing, key, value)
                existing.sync_batch_id = batch_id
                existing.report_type = report_type
            else:
                db.add(StockFinancialReport(stock_code=code, report_date=report_date, **payload))
            stock_written += 1

        written += stock_written

        # 每只股票写完后立即 commit，避免长事务
        if stock_written > 0:
            db.commit()

        # ── 4. 进度日志 ──
        elapsed = time.time() - t0
        speed = idx / elapsed if elapsed > 0 else 0
        eta = (total - idx) / speed if speed > 0 else 0

        if idx % 50 == 0 or idx == total or failed > 0:
            logger.info(
                "[%d/%d] %s  本次写入 %d 条  |  累计: 写入 %d, 失败 %d  |  %.1f 只/分  ETA %.0f 分钟",
                idx, total, code, stock_written,
                written, failed,
                speed * 60, eta / 60,
            )

        if FIN_REQ_PAUSE_SEC > 0:
            time.sleep(FIN_REQ_PAUSE_SEC)

    db.close()
    elapsed = time.time() - t0

    logger.info("=" * 60)
    logger.info("同步完成!")
    logger.info("写入: %d 条  |  失败股票: %d 只  |  耗时: %.1f 分钟", written, failed, elapsed / 60)
    logger.info("=" * 60)


if __name__ == "__main__":
    limit = int(os.environ.get("LIMIT", "0")) or None
    start_date_str = os.environ.get("START_DATE") or None
    run(limit=limit, start_date_str=start_date_str)
