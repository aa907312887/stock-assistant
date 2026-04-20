"""指数同步白名单：`--preset common` 使用的 A 股常见 ts_code。

均为 Tushare **`index_basic` + `index_daily`** 体系（带 `.SH` / `.SZ`），与现有同步管线一致。
"""

# A 股六大常见指数（上证 / 深证成指 / 创业板 / 科创50 / 沪深300 / 中证500）
PRESET_COMMON_INDEX_TS_CODES: tuple[str, ...] = (
    "000001.SH",  # 上证综指（上证）
    "399001.SZ",  # 深证成指
    "399006.SZ",  # 创业板指（创业板）
    "000688.SH",  # 科创50
    "000300.SH",  # 沪深300（CSI）
    "000905.SH",  # 中证500（CSI）
)
