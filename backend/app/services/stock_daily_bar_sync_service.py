"""历史日线同步服务：未复权 ``daily`` + ``adj_factor`` 合成前复权 OHLC，与 ``daily_basic`` 合并写入 stock_daily_bar。"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Iterator, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import StockAdjFactor, StockDailyBar
from app.services.stock_hist_extrema_service import apply_cum_extrema_after_daily_upsert
from app.services.stock_pe_percentile_service import apply_pe_percentile_after_daily_upsert
from app.services.stock_sync_utils import safe_decimal
from app.services.tushare_client import (
    TushareClientError,
    fetch_adj_factor_range,
    fetch_daily_unadjusted_batch,
    fetch_daily_unadjusted_range,
    get_adj_factor_by_trade_date,
    get_daily_basic_by_trade_date,
    get_daily_by_trade_date,
    get_latest_open_trade_date,
    get_open_trade_dates,
    merge_daily_unadjusted_with_adj_factor_qfq,
    normalize_bar,
)

logger = logging.getLogger(__name__)

# 全市场逐标的请求 pro_bar，每 N 只打一次进度，避免刷屏
DAILY_QFQ_PROGRESS_EVERY = 200

# backfill：每段约一个自然年（365 个自然日）；``daily`` 可多标的批量 + 多线程写库
BACKFILL_CHUNK_CALENDAR_DAYS = 365
# Tushare daily 单次返回行数上限（与历史 pro_bar 回灌留同样余量）
BACKFILL_DAILY_LIMIT = 8000


def _latest_adj_factor_by_code(db: Session, codes: list[str]) -> dict[str, Decimal]:
    """各标的在库中最新交易日的复权因子（用于增量日 P_qfq = P_raw * F_t / F_end）。"""
    if not codes:
        return {}
    sub = (
        db.query(StockAdjFactor.stock_code.label("sc"), func.max(StockAdjFactor.trade_date).label("mx"))
        .filter(StockAdjFactor.stock_code.in_(codes))
        .group_by(StockAdjFactor.stock_code)
        .subquery()
    )
    rows = (
        db.query(StockAdjFactor.stock_code, StockAdjFactor.adj_factor)
        .join(
            sub,
            (StockAdjFactor.stock_code == sub.c.sc) & (StockAdjFactor.trade_date == sub.c.mx),
        )
        .all()
    )
    return {r[0]: r[1] for r in rows}


def _upsert_adj_factor_map(
    db: Session,
    *,
    adj_map: dict[str, dict[str, Any]],
    trade_date: date,
    batch_id: str,
) -> None:
    """将某日全市场 adj_factor 接口结果写入 stock_adj_factor。"""
    for code, r in adj_map.items():
        raw_af = r.get("adj_factor")
        if raw_af is None or raw_af == "":
            continue
        dec = safe_decimal(raw_af)
        if dec is None:
            continue
        existing = (
            db.query(StockAdjFactor)
            .filter(StockAdjFactor.stock_code == code, StockAdjFactor.trade_date == trade_date)
            .first()
        )
        if existing:
            existing.adj_factor = dec
            existing.sync_batch_id = batch_id
        else:
            db.add(
                StockAdjFactor(
                    stock_code=code,
                    trade_date=trade_date,
                    adj_factor=dec,
                    sync_batch_id=batch_id,
                )
            )


class _TradeDateBasicCache:
    """按交易日懒拉 ``daily_basic``；多线程回灌时互斥填充，读路径无结构写竞争。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._m: dict[date, dict[str, dict[str, Any]]] = {}

    def row_for(self, trade_date: date, stock_code: str) -> dict[str, Any]:
        with self._lock:
            if trade_date not in self._m:
                self._m[trade_date] = get_daily_basic_by_trade_date(trade_date)
        return self._m[trade_date].get(stock_code, {})


def _backfill_one_stock_one_chunk(
    *,
    stock_code: str,
    raw_daily: list[dict[str, Any]],
    cs: date,
    ce: date,
    anchor_end: date,
    anchor_f: float | None,
    start_date: date,
    end_date: date,
    batch_id: str,
    basic_cache: _TradeDateBasicCache,
    db: Optional[Session] = None,
) -> tuple[int, str | None]:
    """
    单标的单自然年窗口：拉 adj、合并、写 ``stock_adj_factor``/``stock_daily_bar``。
    ``db`` 为 ``None`` 时在本函数内新建 ``Session``（供线程池并发）；传入外层 ``Session`` 时单线程复用连接。
    """
    own_session = db is None
    db = db or SessionLocal()
    try:
        if not raw_daily:
            return (0, None)
        try:
            if anchor_f is not None and anchor_f > 0:
                adj_rows = fetch_adj_factor_range(stock_code, cs, ce)
            else:
                adj_rows = fetch_adj_factor_range(stock_code, cs, anchor_end)
        except TushareClientError as e:
            return (0, str(e))

        try:
            merged_rows = merge_daily_unadjusted_with_adj_factor_qfq(
                raw_daily,
                adj_rows,
                anchor_end=anchor_end,
                anchor_adj_factor=anchor_f,
            )
        except TushareClientError as e:
            return (0, str(e))

        _persist_adj_factor_range_rows(db, stock_code=stock_code, adj_rows=adj_rows, batch_id=batch_id)

        parsed: list[tuple[date, dict[str, Any]]] = []
        for r in merged_rows:
            td = _row_to_trade_date(r)
            if td is None or td < start_date or td > end_date:
                continue
            parsed.append((td, r))
        parsed.sort(key=lambda x: x[0])

        stock_written = 0
        for td, r in parsed:
            raw_basic = basic_cache.row_for(td, stock_code)
            if _upsert_daily_bar(
                db,
                code=stock_code,
                trade_date=td,
                raw_bar=r,
                raw_basic=raw_basic,
                batch_id=batch_id,
            ):
                stock_written += 1
                db.flush()
                apply_cum_extrema_after_daily_upsert(db, stock_code, td)
                apply_pe_percentile_after_daily_upsert(db, stock_code, td)

        db.commit()
        db.expire_all()
        return (stock_written, None)
    except Exception as e:
        db.rollback()
        logger.exception(
            "日线回灌单标的失败 ts_code=%s 区间=%s..%s batch_id=%s",
            stock_code,
            cs,
            ce,
            batch_id,
        )
        return (0, str(e))
    finally:
        if own_session:
            db.close()


def _persist_adj_factor_range_rows(
    db: Session,
    *,
    stock_code: str,
    adj_rows: list[dict[str, Any]],
    batch_id: str,
) -> None:
    """回灌：写入某标的区间内的全部复权因子行。"""
    for r in adj_rows:
        td = _row_to_trade_date(r)
        if td is None:
            continue
        dec = safe_decimal(r.get("adj_factor"))
        if dec is None:
            continue
        existing = (
            db.query(StockAdjFactor)
            .filter(StockAdjFactor.stock_code == stock_code, StockAdjFactor.trade_date == td)
            .first()
        )
        if existing:
            existing.adj_factor = dec
            existing.sync_batch_id = batch_id
        else:
            db.add(
                StockAdjFactor(
                    stock_code=stock_code,
                    trade_date=td,
                    adj_factor=dec,
                    sync_batch_id=batch_id,
                )
            )


def _scale_unadjusted_daily_row_qfq(raw_row: dict[str, Any], *, ratio: Decimal) -> dict[str, Any]:
    """对未复权 daily 行做 P_qfq = P_raw * ratio（ratio = F_t / F_end）。"""
    row = dict(raw_row)
    for key in ("open", "high", "low", "close", "pre_close"):
        d = safe_decimal(row.get(key))
        if d is not None:
            row[key] = float(d * ratio)
    pc = safe_decimal(row.get("pre_close"))
    cl = safe_decimal(row.get("close"))
    if pc is not None and cl is not None:
        row["change"] = float(cl - pc)
        if pc != 0:
            row["pct_chg"] = float(((cl - pc) / pc) * Decimal("100"))
    return row


def _cap_to_yuan(value: Any) -> Decimal | None:
    dec = safe_decimal(value)
    if dec is None:
        return None
    return dec * Decimal("10000")


def _iter_calendar_chunks(
    start: date, end: date, *, chunk_days: int = BACKFILL_CHUNK_CALENDAR_DAYS
) -> Iterator[tuple[date, date]]:
    """按自然日切分 [start, end]，每段最多 chunk_days 天（含首尾）。"""
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=chunk_days - 1), end)
        yield (cur, chunk_end)
        cur = chunk_end + timedelta(days=1)


def _row_to_trade_date(row: dict[str, Any]) -> date | None:
    td = row.get("trade_date")
    if td is None:
        return None
    if hasattr(td, "year") and hasattr(td, "month") and hasattr(td, "day"):
        try:
            return date(td.year, td.month, td.day)  # type: ignore[arg-type]
        except Exception:
            pass
    s = str(td).replace("-", "").strip()
    if len(s) >= 8:
        try:
            return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            return None
    return None


def _upsert_daily_bar(
    db: Session,
    *,
    code: str,
    trade_date: date,
    raw_bar: dict[str, Any] | None,
    raw_basic: dict[str, Any],
    batch_id: str,
) -> bool:
    """写入一行日线；若 raw_bar 与 raw_basic 皆空则跳过。返回是否产生一行有效写入。"""
    if not raw_bar and not raw_basic:
        return False
    bar = normalize_bar(raw_bar) if raw_bar else {}
    existing = (
        db.query(StockDailyBar)
        .filter(StockDailyBar.stock_code == code, StockDailyBar.trade_date == trade_date)
        .first()
    )
    payload = {
        "open": bar.get("o"),
        "high": bar.get("h"),
        "low": bar.get("l"),
        "close": bar.get("c"),
        "prev_close": bar.get("pc"),
        "change_amount": bar.get("change"),
        "pct_change": bar.get("pct_chg"),
        "volume": bar.get("v"),
        "amount": bar.get("a"),
        "amplitude": _calc_amplitude(bar),
        "turnover_rate": safe_decimal(raw_basic.get("turnover_rate")),
        "volume_ratio": safe_decimal(raw_basic.get("volume_ratio")),
        "total_market_cap": _cap_to_yuan(raw_basic.get("total_mv")),
        "float_market_cap": _cap_to_yuan(raw_basic.get("circ_mv")),
        "pe": safe_decimal(raw_basic.get("pe")),
        "pe_ttm": safe_decimal(raw_basic.get("pe_ttm")),
        "pb": safe_decimal(raw_basic.get("pb")),
        "ps": safe_decimal(raw_basic.get("ps")),
        "dv_ratio": safe_decimal(raw_basic.get("dv_ratio")),
        "dv_ttm": safe_decimal(raw_basic.get("dv_ttm")),
        "sync_batch_id": batch_id,
        "data_source": "tushare",
    }
    if existing:
        for key, value in payload.items():
            setattr(existing, key, value)
    else:
        db.add(
            StockDailyBar(
                stock_code=code,
                trade_date=trade_date,
                **payload,
            )
        )
    return True


def sync_daily_bars(
    db: Session,
    *,
    codes: list[str],
    trade_date: date,
    batch_id: str,
) -> dict[str, int]:
    """
    全市场 ``daily``（未复权）+ ``adj_factor`` 合成前复权 OHLC，写入 ``stock_daily_bar``；
    换手率、市值、估值等仍来自当日全市场 ``daily_basic``。复权因子同时写入 ``stock_adj_factor``。
    """
    basic_map = get_daily_basic_by_trade_date(trade_date)
    adj_map = get_adj_factor_by_trade_date(trade_date)
    dmap = get_daily_by_trade_date(trade_date)
    _upsert_adj_factor_map(db, adj_map=adj_map, trade_date=trade_date, batch_id=batch_id)
    db.flush()
    end_map = _latest_adj_factor_by_code(db, codes)
    n = len(codes)
    logger.info(
        "Tushare 日线前复权 trade_date=%s：daily_basic=%s daily(未复权)=%s adj_factor=%s 待写入标的=%s",
        trade_date,
        len(basic_map),
        len(dmap),
        len(adj_map),
        n,
    )
    written = 0

    for idx, code in enumerate(codes, start=1):
        raw_row = dmap.get(code)
        if not raw_row:
            continue
        if code not in adj_map or adj_map.get(code, {}).get("adj_factor") is None:
            logger.warning(
                "缺少当日 adj_factor，跳过日线写入 ts_code=%s trade_date=%s（避免未复权冒充前复权）",
                code,
                trade_date,
            )
            continue
        f_t = safe_decimal((adj_map.get(code) or {}).get("adj_factor"))
        f_end = end_map.get(code)
        if f_end is None:
            logger.warning(
                "库内无该标的复权因子锚点，跳过日线写入 ts_code=%s trade_date=%s",
                code,
                trade_date,
            )
            continue
        if f_t is not None and f_end != 0:
            ratio = f_t / f_end
        else:
            ratio = Decimal("1")
        use_scale = abs(ratio - Decimal("1")) > Decimal("1e-12")
        raw_bar = _scale_unadjusted_daily_row_qfq(raw_row, ratio=ratio) if use_scale else raw_row
        raw_basic = basic_map.get(code, {})
        if _upsert_daily_bar(
            db,
            code=code,
            trade_date=trade_date,
            raw_bar=raw_bar,
            raw_basic=raw_basic,
            batch_id=batch_id,
        ):
            written += 1
            db.flush()
            apply_cum_extrema_after_daily_upsert(db, code, trade_date)
            apply_pe_percentile_after_daily_upsert(db, code, trade_date)
        if idx == 1 or idx == n or idx % DAILY_QFQ_PROGRESS_EVERY == 0:
            logger.info(
                "日线前复权进度 %s/%s trade_date=%s 已写入=%s",
                idx,
                n,
                trade_date,
                written,
            )

    db.commit()
    logger.info("历史日线同步完成 trade_date=%s written=%s", trade_date, written)
    if written == 0 and codes:
        sample_code = codes[:3]
        logger.warning(
            "日线写入 0 行：请核对 (1) 是否非交易日 (2) stock_basic.code 是否为 ts_code（如 000001.SZ）；"
            "示例 code=%s",
            sample_code,
        )
    return {"daily_rows": written}


def sync_daily_bars_backfill_range(
    db: Session,
    *,
    codes: list[str],
    start_date: date,
    end_date: date,
    batch_id: str,
    chunk_calendar_days: int = BACKFILL_CHUNK_CALENDAR_DAYS,
) -> dict[str, int]:
    """
    backfill 专用：按自然日切分（默认每段约一年 365 日）。未复权 ``daily`` 支持 **多标的合并请求**
    （``STOCK_DAILY_BACKFILL_DAILY_BATCH_SIZE``）；同段 ``adj_factor`` 仍按标的请求；全区间 ``F_anchor`` 由任务开始时
    **一次**全市场 ``adj_factor(trade_date=锚定日)`` 取得。``daily_basic`` 经线程安全懒缓存按日拉取。
    并行度由 ``STOCK_DAILY_BACKFILL_WORKERS`` 控制（每只标的独立 ``Session``，处理完 ``commit``）。
    Tushare 休眠见 ``TUSHARE_RATE_PAUSE_SEC_DAILY``（并发时总 QPS 上升，限流时可调大）。
    """
    n = len(codes)
    total_written = 0
    chunk_no = 0
    total_windows = sum(1 for _ in _iter_calendar_chunks(start_date, end_date, chunk_days=chunk_calendar_days))
    anchor_end = end_date
    anchor_td = get_latest_open_trade_date(anchor_end) or anchor_end
    anchor_adj_map: dict[str, dict[str, Any]] = {}
    try:
        anchor_adj_map = get_adj_factor_by_trade_date(anchor_td)
        logger.info(
            "日线回灌 | 全区间锚定复权因子 trade_date=%s 全市场行数=%s（用于 F_anchor，避免每段拉长 adj 请求）",
            anchor_td,
            len(anchor_adj_map),
        )
    except TushareClientError as e:
        logger.warning(
            "日线回灌 | 无法一次拉取锚定日 adj_factor(trade_date=%s)，将逐标的回退为长区间 adj 请求 err=%s",
            anchor_td,
            e,
        )

    for cs, ce in _iter_calendar_chunks(start_date, end_date, chunk_days=chunk_calendar_days):
        chunk_no += 1
        natural_span = (ce - cs).days + 1
        tds = get_open_trade_dates(start=cs.strftime("%Y%m%d"), end=ce.strftime("%Y%m%d"))
        workers = max(1, int(settings.stock_daily_backfill_workers))
        batch_sz = max(1, int(settings.stock_daily_backfill_daily_batch_size))
        basic_cache = _TradeDateBasicCache()

        logger.info(
            "日线回灌 | 年窗口 [%s/%s] | 自然区间=%s..%s（跨度 %s 天）| 段内交易日=%s | 标的数=%s | "
            "workers=%s daily_batch_size=%s | batch_id=%s",
            chunk_no,
            total_windows,
            cs,
            ce,
            natural_span,
            len(tds),
            n,
            workers,
            batch_sz,
            batch_id,
        )

        def _anchor_f_for_code(code: str) -> float | None:
            row_anchor = anchor_adj_map.get(code)
            if not row_anchor or row_anchor.get("adj_factor") is None:
                return None
            try:
                v = float(row_anchor["adj_factor"])
                return v if v > 0 else None
            except (TypeError, ValueError):
                return None

        for batch_start in range(0, len(codes), batch_sz):
            batch = codes[batch_start : batch_start + batch_sz]
            t_batch = time.perf_counter()
            try:
                raw_by_code = fetch_daily_unadjusted_batch(
                    batch,
                    cs,
                    ce,
                    limit=BACKFILL_DAILY_LIMIT,
                )
            except TushareClientError as e:
                logger.warning(
                    "日线回灌 | 年窗口 [%s/%s] | daily 批量失败 n=%s 将逐只回退 err=%s",
                    chunk_no,
                    total_windows,
                    len(batch),
                    e,
                )
                raw_by_code = {}

            tasks: list[tuple[str, list[dict[str, Any]], float | None]] = []
            for code in batch:
                raw_daily = raw_by_code.get(code, [])
                if not raw_daily:
                    try:
                        raw_daily = fetch_daily_unadjusted_range(
                            code,
                            cs,
                            ce,
                            limit=BACKFILL_DAILY_LIMIT,
                        )
                    except TushareClientError as e:
                        logger.warning(
                            "日线回灌 | 年窗口 [%s/%s] | ts_code=%s | daily 单只失败 err=%s",
                            chunk_no,
                            total_windows,
                            code,
                            e,
                        )
                        continue
                tasks.append((code, raw_daily, _anchor_f_for_code(code)))

            batch_written = 0
            if workers <= 1:
                for code, raw_daily, af in tasks:
                    w, err = _backfill_one_stock_one_chunk(
                        stock_code=code,
                        raw_daily=raw_daily,
                        cs=cs,
                        ce=ce,
                        anchor_end=anchor_end,
                        anchor_f=af,
                        start_date=start_date,
                        end_date=end_date,
                        batch_id=batch_id,
                        basic_cache=basic_cache,
                        db=db,
                    )
                    batch_written += w
                    if err:
                        logger.warning(
                            "日线回灌 | 年窗口 [%s/%s] | ts_code=%s | err=%s",
                            chunk_no,
                            total_windows,
                            code,
                            err,
                        )
            else:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    future_map = {
                        pool.submit(
                            _backfill_one_stock_one_chunk,
                            stock_code=code,
                            raw_daily=rd,
                            cs=cs,
                            ce=ce,
                            anchor_end=anchor_end,
                            anchor_f=af,
                            start_date=start_date,
                            end_date=end_date,
                            batch_id=batch_id,
                            basic_cache=basic_cache,
                        ): code
                        for code, rd, af in tasks
                    }
                    for fut in as_completed(future_map):
                        code = future_map[fut]
                        try:
                            w, err = fut.result()
                            batch_written += w
                            if err:
                                logger.warning(
                                    "日线回灌 | 年窗口 [%s/%s] | ts_code=%s | err=%s",
                                    chunk_no,
                                    total_windows,
                                    code,
                                    err,
                                )
                        except Exception as e:
                            logger.exception(
                                "日线回灌 | 年窗口 [%s/%s] | ts_code=%s | 线程异常 err=%s",
                                chunk_no,
                                total_windows,
                                code,
                                e,
                            )

            total_written += batch_written
            db.expire_all()
            logger.info(
                "日线回灌 | 年窗口 [%s/%s] | 子批 [%s..%s) 标的数=%s | 本批写入=%s | 耗时=%.2fs | 累计写入=%s | batch_id=%s",
                chunk_no,
                total_windows,
                batch_start,
                min(batch_start + batch_sz, n),
                len(tasks),
                batch_written,
                time.perf_counter() - t_batch,
                total_written,
                batch_id,
            )

        logger.info(
            "日线回灌 | 年窗口 [%s/%s] 结束 | 区间=%s..%s | 截至本窗口累计写入=%s | batch_id=%s",
            chunk_no,
            total_windows,
            cs,
            ce,
            total_written,
            batch_id,
        )

    if total_written == 0 and codes:
        logger.warning(
            "日线回灌 0 行：请核对 stock_basic.code 是否为 ts_code、区间是否有交易日、Tushare 是否返回空数据",
        )
    return {"daily_rows": total_written}


def _calc_amplitude(bar: dict[str, Any]) -> Decimal | None:
    high = bar.get("h")
    low = bar.get("l")
    prev_close = bar.get("pc")
    if high is None or low is None or prev_close in (None, Decimal("0")):
        return None
    try:
        return ((high - low) / prev_close) * Decimal("100")
    except Exception:
        return None
