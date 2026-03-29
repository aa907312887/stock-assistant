"""前复权日线导出对比：SDK ``pro_bar(qfq)`` vs ``daily``+``adj_factor``（最新交易日锚）。

运行（在 backend 目录）::

    python -m unittest tests.test_pro_bar_qfq_export -v

或 ``pytest tests/test_pro_bar_qfq_export.py -v -s``（须 ``-s`` 才显示路径）。

会生成两个 txt；跑完后在**控制台打印各自绝对路径**，便于在 output 目录里查找。

- ``pro_bar_000001_sz_qfq_sdk_*.txt``：``ts.pro_bar(adj='qfq')``（SDK 原实现）
- ``pro_bar_000001_sz_qfq_latest_anchor_*.txt``：不复权 ``daily`` 与 ``adj_factor`` 合并，
  **前复权价 = 不复权价 × adj_factor / 区间内最后一交易日 adj_factor**（与常见行情软件「以最新为锚」更接近）

依赖：backend/.env 中配置 TUSHARE_TOKEN。

``start_date`` 为 ``20010101``，``end_date`` 为**运行当日**。
"""

from __future__ import annotations

import os
import unittest
from datetime import date
from pathlib import Path

import pandas as pd
import tushare as ts
from dotenv import dotenv_values

BACKEND_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BACKEND_ROOT / "tests" / "output"

# 平安银行为深交所 000001.SZ（上证指数为 000001.SH + asset=I，勿混用）
DEFAULT_TS_CODE = "000001.SZ"
DEFAULT_START = "20010101"


def _make_pro() -> ts.pro_api:
    env = dotenv_values(BACKEND_ROOT / ".env")
    token = (env.get("TUSHARE_TOKEN") or os.environ.get("TUSHARE_TOKEN") or "").strip()
    if not token:
        raise unittest.SkipTest("未配置 TUSHARE_TOKEN（请在 backend/.env 或环境中设置）")
    return ts.pro_api(token=token)


def _norm_trade_date_key(s: pd.Series) -> pd.Series:
    """统一为 YYYYMMDD 字符串，便于 daily 与 adj_factor 对齐。"""
    dt = pd.to_datetime(s, errors="coerce")
    return dt.dt.strftime("%Y%m%d")


class TestProBarQfqSdkExport(unittest.TestCase):
    """Tushare SDK ``ts.pro_bar(adj='qfq')`` 导出（旧路径对照）。"""

    ts_code = DEFAULT_TS_CODE
    start_date = DEFAULT_START

    def test_export_pro_bar_qfq_sdk_to_file(self) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        pro = _make_pro()
        end_date = date.today().strftime("%Y%m%d")
        out_file = OUTPUT_DIR / f"pro_bar_000001_sz_qfq_sdk_{self.start_date}_{end_date}.txt"

        df = ts.pro_bar(
            ts_code=self.ts_code,
            api=pro,
            start_date=self.start_date,
            end_date=end_date,
            freq="D",
            asset="E",
            adj="qfq",
        )

        self.assertIsNotNone(df, "pro_bar 返回 None")
        self.assertFalse(getattr(df, "empty", True), "pro_bar 返回空表")

        if "trade_date" in df.columns:
            df = df.sort_values("trade_date").reset_index(drop=True)

        header = "\n".join(
            [
                f"ts_code={self.ts_code}",
                "方式=SDK ts.pro_bar(adj='qfq')（分母为 adj_factor 表第 0 行等，与东财可能不一致）",
                f"区间 {self.start_date} .. {end_date}",
                f"行数={len(df)}",
                "",
            ]
        )
        out_file.write_text(header + df.to_string(index=True) + "\n", encoding="utf-8")
        print(f"\n[qfq 导出] SDK pro_bar → {out_file.resolve()}\n")


class TestDailyAdjfactorQfqLatestAnchorExport(unittest.TestCase):
    """``daily``（未复权）+ ``adj_factor``，以区间内**最后一交易日**因子为锚的前复权（候选新口径）。"""

    ts_code = DEFAULT_TS_CODE
    start_date = DEFAULT_START

    def test_export_qfq_latest_anchor_to_file(self) -> None:
        """
        前复权 OHLC（及 pre_close）::

            P_qfq = P_raw * F_t / F_end

        其中 ``F_end`` 为合并、ffill/bfill 后**最后一行**的 ``adj_factor``（与常见 K 线「右端锚定」一致）。
        成交量、成交额保持 ``daily`` 原值（未按复权缩放）。
        """
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        pro = _make_pro()
        end_date = date.today().strftime("%Y%m%d")
        out_file = OUTPUT_DIR / (
            f"pro_bar_000001_sz_qfq_latest_anchor_{self.start_date}_{end_date}.txt"
        )

        daily = pro.daily(ts_code=self.ts_code, start_date=self.start_date, end_date=end_date)
        adj = pro.adj_factor(ts_code=self.ts_code, start_date=self.start_date, end_date=end_date)

        self.assertIsNotNone(daily)
        self.assertFalse(daily.empty, "daily 为空")
        self.assertIsNotNone(adj)
        self.assertFalse(adj.empty, "adj_factor 为空")

        d = daily.copy()
        a = adj[["trade_date", "adj_factor"]].copy()
        d["_td"] = _norm_trade_date_key(d["trade_date"])
        a["_td"] = _norm_trade_date_key(a["trade_date"])

        m = d.merge(a[["_td", "adj_factor"]], on="_td", how="left").sort_values("_td").reset_index(
            drop=True
        )
        m["adj_f"] = m["adj_factor"].ffill().bfill()
        f_end = float(m["adj_f"].iloc[-1])
        self.assertGreater(f_end, 0.0, "最后一行 adj_factor 无效，无法作锚")

        price_cols = [c for c in ("open", "high", "low", "close", "pre_close") if c in m.columns]
        ratio = m["adj_f"].astype(float) / f_end
        for c in price_cols:
            raw = pd.to_numeric(m[c], errors="coerce")
            m[c] = raw * ratio

        if "close" in m.columns and "pre_close" in m.columns:
            m["change_qfq"] = m["close"] - m["pre_close"]
            pc = m["pre_close"].replace(0, pd.NA)
            m["pct_chg_qfq"] = (m["change_qfq"] / pc) * 100.0

        drop_cols = [c for c in ("_td", "adj_factor") if c in m.columns]
        out_df = m.drop(columns=drop_cols, errors="ignore")
        out_df = out_df.rename(columns={"adj_f": "adj_factor_used"})

        header = "\n".join(
            [
                f"ts_code={self.ts_code}",
                "方式=daily(未复权) + adj_factor；P_qfq = P_raw * adj_f / adj_f[end]",
                f"锚点因子 F_end={f_end}（区间内最后一交易日，ffill/bfill 后）",
                f"区间 {self.start_date} .. {end_date}",
                f"行数={len(out_df)}",
                "",
            ]
        )
        out_file.write_text(header + out_df.to_string(index=True) + "\n", encoding="utf-8")
        print(f"\n[qfq 导出] daily+adj_factor（最新锚）→ {out_file.resolve()}\n")


if __name__ == "__main__":
    unittest.main()
