"""Tushare Pro API 封装：股票列表、日线、周线、月线、日级指标、财报与交易日历。"""
import json
import logging
import time
from datetime import date, timedelta
from decimal import Decimal
from threading import Lock
from typing import Any

import pandas as pd
import tushare as ts

from app.config import settings

logger = logging.getLogger(__name__)

# 与定时任务/同步链路检索一致，标明 Tushare 封装层
TUSHARE_CLIENT_ALERT = "[Tushare客户端告警]"

MAX_RETRIES = 3
RETRY_INTERVAL_SEC = 5
RATE_PAUSE_SEC = 0.06

_pro_lock = Lock()
_pro_api: Any = None
_cached_token: str | None = None


class TushareClientError(Exception):
    """Tushare 请求失败或解析异常"""

    pass


def _get_pro() -> Any:
    """
    使用显式 token 初始化 pro_api（仅来自 app.config.settings，即 backend/.env）。
    不调用 ts.set_token()，避免写入 ~/tk.csv 或与系统环境变量 TUSHARE_TOKEN 混用。
    """
    global _pro_api, _cached_token
    token = (settings.tushare_token or "").strip()
    if not token:
        logger.error(
            "%s 调用方法=tushare_client._get_pro | 接口=未初始化 pro_api | 原因=TUSHARE_TOKEN 未配置（请在 backend/.env 中设置）",
            TUSHARE_CLIENT_ALERT,
        )
        raise TushareClientError("TUSHARE_TOKEN 未配置（请在 backend/.env 中设置）")
    with _pro_lock:
        if _pro_api is None or _cached_token != token:
            _pro_api = ts.pro_api(token=token)
            _cached_token = token
        return _pro_api


def _df_to_records(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _exchange_from_ts_code(ts_code: str) -> str:
    suf = ts_code.split(".")[-1].upper() if "." in ts_code else ""
    if suf == "SZ":
        return "SZ"
    if suf == "SH":
        return "SH"
    if suf == "BJ":
        return "BJ"
    return suf


def get_stock_list() -> list[dict[str, Any]]:
    """
    上市股票列表，对应 Tushare Pro 接口 **stock_basic**（见官方文档）。
    返回每行含：dm/mc/jys（与下游同步逻辑兼容键）及 area/industry/list_date 等原始字段映射。
    """
    pro = _get_pro()
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            df = pro.stock_basic(
                exchange="",
                list_status="L",
                fields="ts_code,symbol,name,area,industry,list_date,market,exchange",
            )
            rows = _df_to_records(df)
            out: list[dict[str, Any]] = []
            for r in rows:
                tc = (r.get("ts_code") or "").strip()
                if not tc:
                    continue
                area = (r.get("area") or "").strip()
                industry = (r.get("industry") or "").strip()
                ld_raw = r.get("list_date")
                if ld_raw is None:
                    ld_val = None
                else:
                    try:
                        ld_val = None if isinstance(ld_raw, float) and pd.isna(ld_raw) else str(ld_raw).strip() or None
                    except Exception:
                        ld_val = str(ld_raw).strip() or None
                out.append(
                    {
                        "dm": tc,
                        "mc": r.get("name") or "",
                        "jys": _exchange_from_ts_code(tc),
                        "region": area or None,
                        "industry_name": industry or None,
                        "list_date": ld_val,
                    }
                )
            return out
        except Exception as e:
            last_err = e
            logger.warning("Tushare stock_basic 失败 attempt=%s error=%s", attempt + 1, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_INTERVAL_SEC)
    raise TushareClientError(f"Tushare stock_basic 失败: {last_err}") from last_err


def get_daily_by_trade_date(trade_date: date) -> dict[str, dict[str, Any]]:
    """
    指定交易日的全市场日线，键为 ts_code（如 000001.SZ）。
    amount 单位为千元，vol 单位为手（与 Tushare 文档一致）。
    """
    pro = _get_pro()
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            df = pro.daily(trade_date=trade_date.strftime("%Y%m%d"))
            rows = _df_to_records(df)
            return {str(r["ts_code"]): r for r in rows if r.get("ts_code")}
        except Exception as e:
            last_err = e
            logger.warning("Tushare daily 失败 attempt=%s error=%s", attempt + 1, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_INTERVAL_SEC)
    raise TushareClientError(f"Tushare daily 失败: {last_err}") from last_err


def normalize_bar(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    将 Tushare daily 行转为与旧同步逻辑兼容的字段：o/h/l/c/pc/a/v，
    其中成交额转为元、成交量转为股；pct_chg、change 为涨跌幅与涨跌额。
    """
    if not row:
        return None

    def _dec(v: Any) -> Decimal | None:
        if v is None or v == "":
            return None
        try:
            if isinstance(v, float) and pd.isna(v):
                return None
        except Exception:
            pass
        try:
            return Decimal(str(v))
        except Exception:
            return None

    o = _dec(row.get("open"))
    h = _dec(row.get("high"))
    l = _dec(row.get("low"))
    c = _dec(row.get("close"))
    pc = _dec(row.get("pre_close"))
    vol_hand = _dec(row.get("vol"))
    amt_k = _dec(row.get("amount"))
    # 千元 -> 元；手 -> 股（1 手 100 股）
    amount_yuan = (amt_k * Decimal("1000")) if amt_k is not None else None
    volume_shares = (vol_hand * Decimal("100")) if vol_hand is not None else None
    pct_chg = _dec(row.get("pct_chg"))
    change_amt = _dec(row.get("change"))
    return {
        "o": o,
        "h": h,
        "l": l,
        "c": c,
        "pc": pc,
        "a": amount_yuan,
        "v": volume_shares,
        "pct_chg": pct_chg,
        "change": change_amt,
    }


def normalize_daily_bar(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """兼容旧调用，内部复用通用 K 线标准化。"""
    return normalize_bar(row)


def get_daily_basic_by_trade_date(trade_date: date) -> dict[str, dict[str, Any]]:
    """
    指定交易日的全市场日级指标，键为 ts_code。
    total_mv / circ_mv 若返回为万元，调用方可按需要换算。
    """
    pro = _get_pro()
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            df = pro.daily_basic(
                trade_date=trade_date.strftime("%Y%m%d"),
                fields="ts_code,trade_date,turnover_rate,volume_ratio,pe,pe_ttm,pb,ps,dv_ratio,dv_ttm,total_mv,circ_mv",
            )
            rows = _df_to_records(df)
            return {str(r["ts_code"]): r for r in rows if r.get("ts_code")}
        except Exception as e:
            last_err = e
            logger.warning("Tushare daily_basic 失败 attempt=%s error=%s", attempt + 1, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_INTERVAL_SEC)
    raise TushareClientError(f"Tushare daily_basic 失败: {last_err}") from last_err


def get_weekly_bars(ts_code: str, *, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    """获取单只股票的历史周线。"""
    pro = _get_pro()
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            if RATE_PAUSE_SEC > 0:
                time.sleep(RATE_PAUSE_SEC)
            df = pro.weekly(
                ts_code=ts_code,
                start_date=start or "20000101",
                end_date=end or "20991231",
            )
            return _df_to_records(df)
        except Exception as e:
            last_err = e
            logger.warning("Tushare weekly 失败 attempt=%s code=%s error=%s", attempt + 1, ts_code, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_INTERVAL_SEC)
    raise TushareClientError(f"Tushare weekly 失败: {last_err}") from last_err


def get_stk_weekly_monthly_by_trade_date(trade_date: date, freq: str) -> list[dict[str, Any]]:
    """
    全市场周/月线（stk_weekly_monthly），按交易日期一次拉取，单次最多约 6000 行。
    官方文档：trade_date 为每周或每月最后一个交易日；freq 为 week 或 month。
    需较高积分，详见 Tushare 文档 doc_id=336。
    """
    freq = freq.strip().lower()
    if freq not in ("week", "month"):
        raise TushareClientError(f"stk_weekly_monthly freq 必须为 week 或 month，收到: {freq}")
    pro = _get_pro()
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            if RATE_PAUSE_SEC > 0:
                time.sleep(RATE_PAUSE_SEC)
            df = pro.stk_weekly_monthly(trade_date=trade_date.strftime("%Y%m%d"), freq=freq)
            rows = _df_to_records(df)
            if len(rows) >= 6000:
                logger.warning(
                    "%s stk_weekly_monthly 返回行数=%s，接近或达到单次上限 6000，可能不完整",
                    TUSHARE_CLIENT_ALERT,
                    len(rows),
                )
            return rows
        except Exception as e:
            last_err = e
            logger.warning(
                "Tushare stk_weekly_monthly 失败 attempt=%s trade_date=%s freq=%s error=%s",
                attempt + 1,
                trade_date,
                freq,
                e,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_INTERVAL_SEC)
    raise TushareClientError(f"Tushare stk_weekly_monthly 失败: {last_err}") from last_err


def get_stk_weekly_monthly_latest_by_anchor(anchor_date: date, freq: str) -> list[dict[str, Any]]:
    """
    基于锚点日期获取全市场周/月 K 最新快照（每日可用）：
    1) 先按 trade_date=anchor_date 直查；
    2) 若为空，再按日期区间回退查询，并按 ts_code 保留 <=anchor_date 的最新一条。

    说明：官方文档中 trade_date 口径存在「周/月最后日期」限制，实盘中某些日期会返回空；
    为保证每日增量可补偿，统一在客户端做回退兜底。
    """
    freq = freq.strip().lower()
    if freq not in ("week", "month"):
        raise TushareClientError(f"stk_weekly_monthly freq 必须为 week 或 month，收到: {freq}")
    rows = get_stk_weekly_monthly_by_trade_date(anchor_date, freq)
    if rows:
        return rows

    pro = _get_pro()
    if freq == "week":
        start_date = anchor_date - timedelta(days=14)
    else:
        # 月线按当月起始回退；若当月为空再扩展到近 62 天兜底
        start_date = date(anchor_date.year, anchor_date.month, 1)
    end_date = anchor_date

    def _query_range(start_d: date, end_d: date) -> list[dict[str, Any]]:
        last_err: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                if RATE_PAUSE_SEC > 0:
                    time.sleep(RATE_PAUSE_SEC)
                df = pro.stk_weekly_monthly(
                    start_date=start_d.strftime("%Y%m%d"),
                    end_date=end_d.strftime("%Y%m%d"),
                    freq=freq,
                )
                return _df_to_records(df)
            except Exception as e:
                last_err = e
                logger.warning(
                    "Tushare stk_weekly_monthly 区间查询失败 attempt=%s start=%s end=%s freq=%s error=%s",
                    attempt + 1,
                    start_d,
                    end_d,
                    freq,
                    e,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_INTERVAL_SEC)
        raise TushareClientError(f"Tushare stk_weekly_monthly 区间查询失败: {last_err}") from last_err

    range_rows = _query_range(start_date, end_date)
    if not range_rows and freq == "month":
        range_rows = _query_range(anchor_date - timedelta(days=62), end_date)
    latest_rows = _pick_latest_rows_by_code(range_rows, anchor_date)
    logger.info(
        "stk_weekly_monthly 回退查询 anchor=%s freq=%s raw_rows=%s latest_rows=%s",
        anchor_date,
        freq,
        len(range_rows),
        len(latest_rows),
    )
    return latest_rows


def _pick_latest_rows_by_code(rows: list[dict[str, Any]], anchor_date: date) -> list[dict[str, Any]]:
    """按 ts_code 选取不晚于 anchor_date 的最新一条。"""
    latest: dict[str, tuple[date, dict[str, Any]]] = {}
    for row in rows:
        code = str(row.get("ts_code") or "").strip()
        if not code:
            continue
        d = _safe_trade_date(str(row.get("end_date") or row.get("trade_date") or ""))
        if d is None or d > anchor_date:
            continue
        cur = latest.get(code)
        if cur is None or d >= cur[0]:
            latest[code] = (d, row)
    return [v[1] for v in latest.values()]


def get_monthly_bars(ts_code: str, *, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    """获取单只股票的历史月线。"""
    pro = _get_pro()
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            if RATE_PAUSE_SEC > 0:
                time.sleep(RATE_PAUSE_SEC)
            df = pro.monthly(
                ts_code=ts_code,
                start_date=start or "20000101",
                end_date=end or "20991231",
            )
            return _df_to_records(df)
        except Exception as e:
            last_err = e
            logger.warning("Tushare monthly 失败 attempt=%s code=%s error=%s", attempt + 1, ts_code, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_INTERVAL_SEC)
    raise TushareClientError(f"Tushare monthly 失败: {last_err}") from last_err


def get_fin_income(
    ts_code: str,
    *,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    """
    利润表（按公告日期区间筛选）。返回行中含 end_date、total_revenue、oper_cost 等。
    start/end 为 YYYYMMDD，对应 Tushare income 的公告日期区间。
    """
    pro = _get_pro()
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            if RATE_PAUSE_SEC > 0:
                time.sleep(RATE_PAUSE_SEC)
            df = pro.income(
                ts_code=ts_code,
                start_date=start or "20000101",
                end_date=end or "20991231",
            )
            return _df_to_records(df)
        except Exception as e:
            last_err = e
            logger.warning("Tushare income 失败 attempt=%s code=%s error=%s", attempt + 1, ts_code, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_INTERVAL_SEC)
    raise TushareClientError(f"Tushare income 失败: {last_err}") from last_err


def get_open_trade_dates(*, start: str, end: str, exchange: str = "SSE") -> list[date]:
    """返回指定区间内的开市日期列表。"""
    pro = _get_pro()
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            df = pro.trade_cal(
                exchange=exchange,
                start_date=start,
                end_date=end,
                fields="cal_date,is_open",
            )
            rows = _df_to_records(df)
            out: list[date] = []
            for row in rows:
                if str(row.get("is_open") or "0") != "1":
                    continue
                cal_date = row.get("cal_date")
                if cal_date:
                    out_date = _safe_trade_date(str(cal_date))
                    if out_date:
                        out.append(out_date)
            out.sort()
            return out
        except Exception as e:
            last_err = e
            logger.warning("Tushare trade_cal 失败 attempt=%s error=%s", attempt + 1, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_INTERVAL_SEC)
    raise TushareClientError(f"Tushare trade_cal 失败: {last_err}") from last_err


def get_latest_open_trade_date(ref_date: date) -> date | None:
    """返回不晚于 ref_date 的最近一个开市日。"""
    start = date(ref_date.year, 1, 1)
    open_dates = get_open_trade_dates(start=start.strftime("%Y%m%d"), end=ref_date.strftime("%Y%m%d"))
    if not open_dates:
        return None
    return open_dates[-1]


def get_index_daily_range(ts_code: str, *, start_date: date, end_date: date) -> list[dict[str, Any]]:
    """获取指数区间日线（index_daily）。"""
    pro = _get_pro()
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            df = pro.index_daily(
                ts_code=ts_code,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
            return _df_to_records(df)
        except Exception as e:
            last_err = e
            logger.warning(
                "Tushare index_daily 失败 attempt=%s code=%s start=%s end=%s error=%s",
                attempt + 1,
                ts_code,
                start_date,
                end_date,
                e,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_INTERVAL_SEC)
    raise TushareClientError(f"Tushare index_daily 失败: {last_err}") from last_err


def _safe_trade_date(text: str) -> date | None:
    text = text.strip()
    if not text:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return date.fromisoformat(text) if fmt == "%Y-%m-%d" else date(
                int(text[0:4]), int(text[4:6]), int(text[6:8])
            )
        except Exception:
            continue
    return None
