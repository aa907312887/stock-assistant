"""指数数据同步：index_basic、日/周/月 K 线（Tushare index_*）。"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from app.models.index_basic import IndexBasic
from app.models.index_daily_bar import IndexDailyBar
from app.models.index_monthly_bar import IndexMonthlyBar
from app.models.index_weekly_bar import IndexWeeklyBar
from app.models.index_weight import IndexWeight
from app.services.index_indicator_fill_service import (
    fill_index_indicators_for_timeframe,
    fill_index_after_daily_sync,
)
from app.services.stock_sync_utils import safe_decimal
from app.services.index_pe_percentile_service import normalize_ts_code
from app.services.tushare_client import (
    INDEX_BASIC_MARKETS,
    TushareClientError,
    get_index_basic,
    get_index_daily_range,
    get_index_monthly_range,
    get_index_weekly_range,
    get_index_weight_range,
    get_latest_open_trade_date,
)

logger = logging.getLogger(__name__)

# Tushare index_daily 单次行数上限留余量
DAILY_CHUNK_DAYS = 3000
# 周/月线单次 1000 行
WM_CHUNK_DAYS = 800


def _normalized_ts_set(codes: list[str] | None) -> frozenset[str] | None:
    """将 ts_code 列表规范为集合；空则 None（表示不限制）。"""
    if not codes:
        return None
    s = {normalize_ts_code(c) for c in codes if (c or "").strip()}
    return frozenset(s) if s else None


def _parse_tushare_date(s: str | None) -> date | None:
    if not s or len(str(s)) < 8:
        return None
    t = str(s).replace("-", "")[:8]
    try:
        return date(int(t[0:4]), int(t[4:6]), int(t[6:8]))
    except Exception:
        return None


def _upsert_index_basic_row(db: Session, r: dict[str, Any], batch: str) -> None:
    ts = (r.get("ts_code") or "").strip()
    if not ts:
        return
    row = (
        {
            "ts_code": ts,
            "name": (r.get("name") or None) and str(r.get("name"))[:128],
            "fullname": (r.get("fullname") or None) and str(r.get("fullname"))[:255],
            "market": (r.get("market") or None) and str(r.get("market"))[:16],
            "publisher": (r.get("publisher") or None) and str(r.get("publisher"))[:64],
            "index_type": (r.get("index_type") or None) and str(r.get("index_type"))[:64],
            "category": (r.get("category") or None) and str(r.get("category"))[:64],
            "base_date": _parse_tushare_date(str(r.get("base_date") or "")),
            "base_point": safe_decimal(r.get("base_point")),
            "list_date": _parse_tushare_date(str(r.get("list_date") or "")),
            "weight_rule": (r.get("weight_rule") or None) and str(r.get("weight_rule"))[:255],
            "description": (r.get("desc") or r.get("description") or None),
            "exp_date": _parse_tushare_date(str(r.get("exp_date") or "")),
            "data_source": "tushare",
            "synced_at": datetime.now(),
        }
    )
    stmt = mysql_insert(IndexBasic).values(**row)
    stmt = stmt.on_duplicate_key_update(
        name=stmt.inserted.name,
        fullname=stmt.inserted.fullname,
        market=stmt.inserted.market,
        publisher=stmt.inserted.publisher,
        index_type=stmt.inserted.index_type,
        category=stmt.inserted.category,
        base_date=stmt.inserted.base_date,
        base_point=stmt.inserted.base_point,
        list_date=stmt.inserted.list_date,
        weight_rule=stmt.inserted.weight_rule,
        description=stmt.inserted.description,
        exp_date=stmt.inserted.exp_date,
        synced_at=stmt.inserted.synced_at,
    )
    db.execute(stmt)


def sync_index_basic(db: Session, *, only_ts_codes: frozenset[str] | None = None) -> int:
    """按市场循环拉取 index_basic 并 upsert。only_ts_codes 非空时仅写入白名单内代码。"""
    count = 0
    seen: set[str] = set()
    for mkt in INDEX_BASIC_MARKETS:
        try:
            rows = get_index_basic(market=mkt)
        except TushareClientError as e:
            logger.warning("index_basic market=%s 跳过: %s", mkt, e)
            continue
        for r in rows:
            ts = (r.get("ts_code") or "").strip()
            if not ts:
                continue
            tsn = normalize_ts_code(ts)
            if only_ts_codes is not None and tsn not in only_ts_codes:
                continue
            if tsn in seen:
                continue
            seen.add(tsn)
            _upsert_index_basic_row(db, r, "")
            count += 1
    db.commit()
    logger.info("index_basic 写入条数=%s distinct=%s", count, len(seen))
    return count


def _calc_amplitude(high: Decimal | None, low: Decimal | None, prev_close: Decimal | None) -> Decimal | None:
    if high is None or low is None or prev_close is None or prev_close == 0:
        return None
    try:
        return ((high - low) / prev_close * Decimal("100")).quantize(Decimal("0.0001"))
    except Exception:
        return None


def upsert_index_daily_rows(
    db: Session,
    index_code: str,
    rows: list[dict[str, Any]],
    *,
    batch_id: str,
) -> int:
    """将 index_daily 接口行写入 index_daily_bar。"""
    n = 0
    for r in rows:
        td = _parse_tushare_date(str(r.get("trade_date") or ""))
        if td is None:
            continue
        oc = safe_decimal(r.get("open"))
        hi = safe_decimal(r.get("high"))
        lo = safe_decimal(r.get("low"))
        cl = safe_decimal(r.get("close"))
        prev_c = safe_decimal(r.get("pre_close"))
        chg = safe_decimal(r.get("change"))
        pct = safe_decimal(r.get("pct_chg"))
        vol = safe_decimal(r.get("vol"))
        amt = safe_decimal(r.get("amount"))
        # Tushare：成交额千元 → 与个股 stock_daily_bar.amount（元）对齐时 ×1000
        amt_yuan = None
        if amt is not None:
            amt_yuan = (amt * Decimal("1000")).quantize(Decimal("0.01"))
        amp = _calc_amplitude(hi, lo, prev_c)

        vals = {
            "index_code": index_code,
            "trade_date": td,
            "open": oc,
            "high": hi,
            "low": lo,
            "close": cl,
            "prev_close": prev_c,
            "change_amount": chg,
            "pct_change": pct,
            "volume": vol,
            "amount": amt_yuan,
            "amplitude": amp,
            "data_source": "tushare",
            "sync_batch_id": batch_id,
            "synced_at": datetime.now(),
        }
        stmt = mysql_insert(IndexDailyBar).values(**vals)
        stmt = stmt.on_duplicate_key_update(
            open=stmt.inserted.open,
            high=stmt.inserted.high,
            low=stmt.inserted.low,
            close=stmt.inserted.close,
            prev_close=stmt.inserted.prev_close,
            change_amount=stmt.inserted.change_amount,
            pct_change=stmt.inserted.pct_change,
            volume=stmt.inserted.volume,
            amount=stmt.inserted.amount,
            amplitude=stmt.inserted.amplitude,
            sync_batch_id=stmt.inserted.sync_batch_id,
            synced_at=stmt.inserted.synced_at,
        )
        db.execute(stmt)
        n += 1
    return n


def sync_index_daily_range(
    db: Session,
    index_code: str,
    start_date: date,
    end_date: date,
    *,
    batch_id: str,
) -> int:
    """分段拉取 index_daily 并写入。"""
    total = 0
    cur_start = start_date
    while cur_start <= end_date:
        cur_end = min(cur_start + timedelta(days=DAILY_CHUNK_DAYS), end_date)
        rows = get_index_daily_range(index_code, start_date=cur_start, end_date=cur_end)
        total += upsert_index_daily_rows(db, index_code, rows, batch_id=batch_id)
        db.commit()
        cur_start = cur_end + timedelta(days=1)
    return total


def _latest_daily_date(db: Session, index_code: str) -> date | None:
    return (
        db.query(func.max(IndexDailyBar.trade_date)).filter(IndexDailyBar.index_code == index_code).scalar()
    )


def sync_index_daily_incremental(
    db: Session,
    *,
    anchor_date: date | None = None,
    limit_codes: int | None = None,
    only_ts_codes: frozenset[str] | None = None,
) -> dict[str, Any]:
    """
    对每个指数：从「库中最后一根交易日+1」增量到 anchor_date（默认最近开市日）。
    limit_codes：仅处理前 N 个指数（大批量时控制时长）。
    only_ts_codes：仅处理白名单内的 ts_code（与 index_basic 交集）。
    """
    ad = anchor_date or get_latest_open_trade_date(date.today()) or date.today()
    batch_id = f"idx-{uuid.uuid4().hex[:12]}"
    codes = db.query(IndexBasic.ts_code).order_by(IndexBasic.ts_code).all()
    code_list = [normalize_ts_code(c[0]) for c in codes if c[0]]
    if only_ts_codes is not None:
        code_list = [c for c in code_list if c in only_ts_codes]
    if limit_codes is not None:
        code_list = code_list[:limit_codes]

    rows_total = 0
    failed: list[str] = []
    for ts in code_list:
        try:
            last = _latest_daily_date(db, ts)
            if last is None:
                start = date(2010, 1, 1)
            else:
                start = last + timedelta(days=1)
            if start > ad:
                continue
            n = sync_index_daily_range(db, ts, start, ad, batch_id=batch_id)
            rows_total += n
        except Exception as e:
            db.rollback()
            logger.warning("指数日线增量失败 code=%s err=%s", ts, e)
            failed.append(f"{ts}: {e}")
    db.commit()

    fill_index_after_daily_sync(
        db,
        anchor_date=ad,
        limit=None if only_ts_codes is not None else limit_codes,
        only_index_codes=only_ts_codes,
    )
    return {
        "batch_id": batch_id,
        "anchor_date": str(ad),
        "daily_rows": rows_total,
        "failed": failed,
    }


def _upsert_wm_row(
    db: Session,
    model: type,
    date_attr: str,
    index_code: str,
    r: dict[str, Any],
    batch_id: str,
) -> None:
    td = _parse_tushare_date(str(r.get("trade_date") or ""))
    if td is None:
        return
    oc = safe_decimal(r.get("open"))
    hi = safe_decimal(r.get("high"))
    lo = safe_decimal(r.get("low"))
    cl = safe_decimal(r.get("close"))
    vol = safe_decimal(r.get("vol"))
    amt = safe_decimal(r.get("amount"))
    amt_yuan = (amt * Decimal("1000")).quantize(Decimal("0.01")) if amt is not None else None
    chg = safe_decimal(r.get("change"))
    pct = safe_decimal(r.get("pct_chg"))

    vals = {
        "index_code": index_code,
        date_attr: td,
        "open": oc,
        "high": hi,
        "low": lo,
        "close": cl,
        "change_amount": chg,
        "pct_change": pct,
        "volume": vol,
        "amount": amt_yuan,
        "data_source": "tushare",
        "sync_batch_id": batch_id,
        "synced_at": datetime.now(),
    }
    uk = {"index_code", date_attr}
    stmt = mysql_insert(model).values(**vals)
    upd = {k: getattr(stmt.inserted, k) for k in vals if k not in uk}
    stmt = stmt.on_duplicate_key_update(**upd)
    db.execute(stmt)


def sync_index_weekly_range(
    db: Session,
    index_code: str,
    start_date: date,
    end_date: date,
    *,
    batch_id: str,
) -> int:
    total = 0
    cur = start_date
    while cur <= end_date:
        chunk_end = min(cur + timedelta(days=WM_CHUNK_DAYS), end_date)
        rows = get_index_weekly_range(index_code, start_date=cur, end_date=chunk_end)
        for r in rows:
            _upsert_wm_row(db, IndexWeeklyBar, "trade_week_end", index_code, r, batch_id)
            total += 1
        db.commit()
        cur = chunk_end + timedelta(days=1)
    return total


def sync_index_monthly_range(
    db: Session,
    index_code: str,
    start_date: date,
    end_date: date,
    *,
    batch_id: str,
) -> int:
    total = 0
    cur = start_date
    while cur <= end_date:
        chunk_end = min(cur + timedelta(days=WM_CHUNK_DAYS), end_date)
        rows = get_index_monthly_range(index_code, start_date=cur, end_date=chunk_end)
        for r in rows:
            _upsert_wm_row(db, IndexMonthlyBar, "trade_month_end", index_code, r, batch_id)
            total += 1
        db.commit()
        cur = chunk_end + timedelta(days=1)
    return total


def sync_index_weight_for_month(
    db: Session,
    index_code: str,
    start_date: date,
    end_date: date,
) -> int:
    rows = get_index_weight_range(index_code, start_date=start_date, end_date=end_date)
    n = 0
    for r in rows:
        ic = (r.get("index_code") or index_code).strip()
        cc = (r.get("con_code") or "").strip()
        td = _parse_tushare_date(str(r.get("trade_date") or ""))
        w = safe_decimal(r.get("weight"))
        if not cc or td is None or w is None:
            continue
        vals = {
            "index_code": ic,
            "con_code": cc,
            "trade_date": td,
            "weight": w,
            "synced_at": datetime.now(),
        }
        stmt = mysql_insert(IndexWeight).values(**vals)
        stmt = stmt.on_duplicate_key_update(weight=stmt.inserted.weight, synced_at=stmt.inserted.synced_at)
        db.execute(stmt)
        n += 1
    db.commit()
    return n


def run_index_sync(
    db: Session,
    *,
    modules: list[str],
    mode: str = "incremental",
    start_date: date | None = None,
    end_date: date | None = None,
    limit_codes: int | None = None,
    only_ts_codes: list[str] | None = None,
) -> dict[str, Any]:
    """编排入口：modules 含 basic、daily、weekly、monthly、weight。only_ts_codes 非空时各模块仅处理这些代码。"""
    out: dict[str, Any] = {"modules": {}, "only_ts_codes": list(only_ts_codes) if only_ts_codes else None}
    anchor = end_date or get_latest_open_trade_date(date.today()) or date.today()
    fts = _normalized_ts_set(only_ts_codes)

    if "basic" in modules:
        out["modules"]["basic"] = sync_index_basic(db, only_ts_codes=fts)

    if "daily" in modules:
        if mode == "backfill" and start_date and end_date:
            bid = f"idx-bf-{uuid.uuid4().hex[:10]}"
            codes = [normalize_ts_code(c[0]) for c in db.query(IndexBasic.ts_code).all()]
            if fts is not None:
                codes = [c for c in codes if c in fts]
            elif limit_codes:
                codes = codes[:limit_codes]
            total = 0
            for ts in codes:
                total += sync_index_daily_range(db, ts, start_date, end_date, batch_id=bid)
            db.commit()
            fill_index_indicators_for_timeframe(
                db,
                "daily",
                mode="backfill",
                trade_date_anchor=None,
                start_date=start_date,
                end_date=end_date,
                limit=None if fts is not None else limit_codes,
                only_index_codes=fts,
            )
            out["modules"]["daily"] = {"rows": total, "mode": "backfill"}
        else:
            out["modules"]["daily"] = sync_index_daily_incremental(
                db,
                anchor_date=anchor,
                limit_codes=limit_codes,
                only_ts_codes=fts,
            )

    if "weekly" in modules and start_date and end_date:
        bid = f"idx-w-{uuid.uuid4().hex[:8]}"
        codes = [normalize_ts_code(c[0]) for c in db.query(IndexBasic.ts_code).all()]
        if fts is not None:
            codes = [c for c in codes if c in fts]
        elif limit_codes:
            codes = codes[:limit_codes]
        tw = 0
        for ts in codes:
            tw += sync_index_weekly_range(db, ts, start_date, end_date, batch_id=bid)
        db.commit()
        fill_index_indicators_for_timeframe(
            db,
            "weekly",
            mode="backfill",
            start_date=start_date,
            end_date=end_date,
            limit=None if fts is not None else limit_codes,
            only_index_codes=fts,
        )
        out["modules"]["weekly"] = tw

    if "monthly" in modules and start_date and end_date:
        bid = f"idx-m-{uuid.uuid4().hex[:8]}"
        codes = [normalize_ts_code(c[0]) for c in db.query(IndexBasic.ts_code).all()]
        if fts is not None:
            codes = [c for c in codes if c in fts]
        elif limit_codes:
            codes = codes[:limit_codes]
        tm = 0
        for ts in codes:
            tm += sync_index_monthly_range(db, ts, start_date, end_date, batch_id=bid)
        db.commit()
        fill_index_indicators_for_timeframe(
            db,
            "monthly",
            mode="backfill",
            start_date=start_date,
            end_date=end_date,
            limit=None if fts is not None else limit_codes,
            only_index_codes=fts,
        )
        out["modules"]["monthly"] = tm

    if "weight" in modules and start_date and end_date:
        codes = [normalize_ts_code(c[0]) for c in db.query(IndexBasic.ts_code).all()]
        if fts is not None:
            codes = [c for c in codes if c in fts]
        elif limit_codes:
            codes = codes[:limit_codes]
        twg = 0
        for ts in codes:
            twg += sync_index_weight_for_month(db, ts, start_date, end_date)
        out["modules"]["weight"] = twg

    return out
