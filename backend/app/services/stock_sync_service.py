"""综合选股数据同步：基于 Tushare 股票列表 + 日线行情 + 利润表。"""
import logging
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import StockBasic, StockDailyQuote, StockFinancialReport
from app.services.tushare_client import (
    TushareClientError,
    get_daily_by_trade_date,
    get_fin_income,
    get_stock_list,
    normalize_daily_bar,
)

logger = logging.getLogger(__name__)

# 每批提交条数
BATCH_SIZE = 500
BATCH_PAUSE_SEC = 0.2
# 财报接口节流（按标的请求利润表）
FIN_REQ_PAUSE_SEC = 0.08


def _safe_decimal(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def _safe_date(v: Any) -> date | None:
    if not v:
        return None
    text = str(v).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _safe_pct(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator in (None, Decimal("0")):
        return None
    try:
        return (numerator / denominator) * Decimal("100")
    except Exception:
        return None


def run_sync(db: Session, trade_date: date | None = None, limit: int | None = None) -> dict[str, int]:
    """
    执行一次全量同步：
    1) 拉股票列表写 stock_basic
    2) 拉取当日全市场日线写 stock_daily_quote（开高低收、成交量额等）
    3) 按股票逐只拉利润表写 stock_financial_report（基本面信息）
    trade_date 不传则用今天。
    limit: 若传入，仅处理前 limit 条股票列表（用于快速验证）。
    返回 {"stock_basic": n, "stock_daily_quote": n, "stock_financial_report": n}。
    """
    trade_date = trade_date or date.today()
    stats = {"stock_basic": 0, "stock_daily_quote": 0, "stock_financial_report": 0}
    logger.info("同步开始 trade_date=%s limit=%s", trade_date, limit)
    try:
        # 1) 股票列表 -> stock_basic
        try:
            rows = get_stock_list()
        except TushareClientError as e:
            logger.error("拉取股票列表失败: %s", e)
            raise
        if limit is not None:
            rows = rows[:limit]
        valid_codes = {(row.get("dm") or "").strip() for row in rows if (row.get("dm") or "").strip()}
        # 清理当日已存在但不在全市场股票列表中的脏数据，保证当日记录与全市场一致
        existing_codes = {
            code for (code,) in db.query(StockDailyQuote.stock_code).filter(StockDailyQuote.trade_date == trade_date).all()
        }
        extra_codes = existing_codes - valid_codes
        if extra_codes:
            db.query(StockDailyQuote).filter(
                StockDailyQuote.trade_date == trade_date,
                StockDailyQuote.stock_code.in_(extra_codes),
            ).delete(synchronize_session=False)
            db.commit()
        total_list = len(rows)
        for i, row in enumerate(rows):
            if i > 0 and i % BATCH_SIZE == 0:
                db.commit()
                logger.info("stock_basic 进度 %s/%s", i, total_list)
                if BATCH_PAUSE_SEC > 0:
                    time.sleep(BATCH_PAUSE_SEC)
            dm = (row.get("dm") or "").strip()
            if not dm:
                continue
            mc = row.get("mc") or ""
            jys = row.get("jys") or ""
            region = row.get("region")
            ind_name = row.get("industry_name")
            list_d = _safe_date(row.get("list_date"))
            existing = db.query(StockBasic).filter(StockBasic.code == dm).first()
            if existing:
                existing.name = mc
                existing.market = jys
                if region is not None:
                    existing.region = region
                if ind_name is not None:
                    existing.industry_name = ind_name
                if list_d is not None:
                    existing.list_date = list_d
                existing.sync_batch_id = f"{trade_date}-sync"
            else:
                db.add(
                    StockBasic(
                        code=dm,
                        name=mc,
                        market=jys,
                        region=region,
                        industry_name=ind_name,
                        list_date=list_d,
                        sync_batch_id=f"{trade_date}-sync",
                    )
                )
            stats["stock_basic"] += 1
        db.commit()
        logger.info("stock_basic 写入 %s 条", stats["stock_basic"])

        try:
            daily_map = get_daily_by_trade_date(trade_date)
        except TushareClientError as e:
            logger.error("拉取全市场日线失败: %s", e)
            raise
        logger.info("全市场日线条数: %s", len(daily_map))

        # 2) 当日全市场行情（Tushare daily 一次性拉取后按代码匹配）
        for i, row in enumerate(rows):
            if i > 0 and i % BATCH_SIZE == 0:
                db.commit()
                logger.info("历史分时进度 %s/%s", i, total_list)
                if BATCH_PAUSE_SEC > 0:
                    time.sleep(BATCH_PAUSE_SEC)

            dm = (row.get("dm") or "").strip()  # 000001.SZ
            if not dm:
                continue

            raw_daily = daily_map.get(dm)
            quote_row = normalize_daily_bar(raw_daily)

            o = quote_row.get("o") if quote_row else None
            h = quote_row.get("h") if quote_row else None
            l = quote_row.get("l") if quote_row else None
            c = quote_row.get("c") if quote_row else None
            amount = quote_row.get("a") if quote_row else None
            volume = quote_row.get("v") if quote_row else None
            prev_close = quote_row.get("pc") if quote_row else None
            change_amount = quote_row.get("change") if quote_row else None
            if change_amount is None and c is not None and prev_close is not None:
                change_amount = c - prev_close
            pct = quote_row.get("pct_chg") if quote_row else None
            if pct is None:
                pct = _safe_pct(change_amount, prev_close)
            amplitude = _safe_pct((h - l) if h is not None and l is not None else None, prev_close)

            existing_q = (
                db.query(StockDailyQuote)
                .filter(
                    StockDailyQuote.stock_code == dm,
                    StockDailyQuote.trade_date == trade_date,
                )
                .first()
            )
            if existing_q:
                existing_q.open = o
                existing_q.high = h
                existing_q.low = l
                existing_q.close = c
                existing_q.pct_change = pct
                existing_q.amount = amount
                existing_q.volume = volume
                existing_q.prev_close = prev_close
                existing_q.change_amount = change_amount
                existing_q.amplitude = amplitude
                existing_q.turnover_rate = None
                existing_q.total_market_cap = None
                existing_q.float_market_cap = None
                existing_q.sync_batch_id = f"{trade_date}-sync"
            else:
                db.add(
                    StockDailyQuote(
                        stock_code=dm,
                        trade_date=trade_date,
                        open=o,
                        high=h,
                        low=l,
                        close=c,
                        pct_change=pct,
                        amount=amount,
                        volume=volume,
                        prev_close=prev_close,
                        change_amount=change_amount,
                        turnover_rate=None,
                        amplitude=amplitude,
                        total_market_cap=None,
                        float_market_cap=None,
                        sync_batch_id=f"{trade_date}-sync",
                    )
                )
            stats["stock_daily_quote"] += 1

            # 3) 利润表（选最近报告期）
            fin_row: dict[str, Any] | None = None
            try:
                fin_rows = get_fin_income(
                    dm,
                    start=f"{max(trade_date.year - 2, 2000)}0101",
                    end=trade_date.strftime("%Y%m%d"),
                )
                if fin_rows:
                    fin_candidates: list[tuple[date, dict[str, Any]]] = []
                    for fr in fin_rows:
                        report_date = _safe_date(fr.get("end_date"))
                        if report_date and report_date <= trade_date:
                            fin_candidates.append((report_date, fr))
                    if fin_candidates:
                        fin_candidates.sort(key=lambda x: x[0])
                        fin_row = fin_candidates[-1][1]
            except TushareClientError as e:
                logger.warning("拉取利润表失败 code=%s error=%s", dm, e)
            if FIN_REQ_PAUSE_SEC > 0:
                time.sleep(FIN_REQ_PAUSE_SEC)

            if fin_row:
                report_date = _safe_date(fin_row.get("end_date"))
                if report_date:
                    revenue = _safe_decimal(fin_row.get("total_revenue"))
                    net_profit = _safe_decimal(fin_row.get("n_income_attr_p")) or _safe_decimal(
                        fin_row.get("n_income")
                    )
                    eps = _safe_decimal(fin_row.get("basic_eps")) or _safe_decimal(fin_row.get("diluted_eps"))
                    yysr = _safe_decimal(fin_row.get("total_revenue"))
                    yycb = _safe_decimal(fin_row.get("oper_cost"))
                    gross_margin = _safe_pct((yysr - yycb) if yysr is not None and yycb is not None else None, yysr)

                    existing_r = (
                        db.query(StockFinancialReport)
                        .filter(
                            StockFinancialReport.stock_code == dm,
                            StockFinancialReport.report_date == report_date,
                        )
                        .first()
                    )
                    if existing_r:
                        existing_r.report_type = "income"
                        existing_r.revenue = revenue
                        existing_r.net_profit = net_profit
                        existing_r.eps = eps
                        existing_r.roe = None
                        existing_r.gross_margin = gross_margin
                        existing_r.sync_batch_id = f"{trade_date}-sync"
                    else:
                        db.add(
                            StockFinancialReport(
                                stock_code=dm,
                                report_date=report_date,
                                report_type="income",
                                revenue=revenue,
                                net_profit=net_profit,
                                eps=eps,
                                roe=None,
                                gross_margin=gross_margin,
                                sync_batch_id=f"{trade_date}-sync",
                            )
                        )
                    stats["stock_financial_report"] += 1

        db.commit()
        logger.info(
            "同步结束 stock_daily_quote=%s stock_financial_report=%s",
            stats["stock_daily_quote"],
            stats["stock_financial_report"],
        )
    except Exception as e:
        db.rollback()
        logger.exception("同步失败: %s", e)
        raise
    return stats
