"""财报历史同步服务。"""

from __future__ import annotations

import logging
import time
from datetime import date

from sqlalchemy.orm import Session

from app.models import StockFinancialReport
from app.services.stock_sync_utils import safe_date, safe_decimal, safe_pct
from app.services.tushare_client import get_fin_income

logger = logging.getLogger(__name__)

FIN_REQ_PAUSE_SEC = 0.05


def sync_financial_reports(
    db: Session,
    *,
    codes: list[str],
    end_date: date,
    batch_id: str,
    start_date: date | None = None,
) -> dict[str, int]:
    written = 0
    failed = 0
    start = (start_date or date(max(end_date.year - 3, 2000), 1, 1)).strftime("%Y%m%d")
    end = end_date.strftime("%Y%m%d")
    for code in codes:
        try:
            rows = get_fin_income(code, start=start, end=end)
        except Exception as exc:
            failed += 1
            logger.warning("财报同步失败 code=%s error=%s", code, exc)
            continue
        for row in rows:
            report_date = safe_date(row.get("end_date"))
            if report_date is None:
                continue
            revenue = safe_decimal(row.get("total_revenue"))
            oper_cost = safe_decimal(row.get("oper_cost"))
            net_profit = safe_decimal(row.get("n_income_attr_p")) or safe_decimal(row.get("n_income"))
            eps = safe_decimal(row.get("basic_eps")) or safe_decimal(row.get("diluted_eps"))
            gross_margin = safe_pct((revenue - oper_cost) if revenue is not None and oper_cost is not None else None, revenue)
            existing = (
                db.query(StockFinancialReport)
                .filter(StockFinancialReport.stock_code == code, StockFinancialReport.report_date == report_date)
                .first()
            )
            payload = {
                "report_type": "income",
                "revenue": revenue,
                "net_profit": net_profit,
                "eps": eps,
                "gross_margin": gross_margin,
                "sync_batch_id": batch_id,
                "data_source": "tushare",
            }
            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
            else:
                db.add(StockFinancialReport(stock_code=code, report_date=report_date, **payload))
            written += 1
        if FIN_REQ_PAUSE_SEC > 0:
            time.sleep(FIN_REQ_PAUSE_SEC)
    db.commit()
    logger.info("财报历史同步完成 end_date=%s written=%s failed=%s", end_date, written, failed)
    return {"report_rows": written, "failed_stock_count": failed}
