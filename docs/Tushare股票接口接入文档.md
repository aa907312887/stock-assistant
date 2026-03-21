# Tushare 接入说明

本项目综合选股的数据源为 **Tushare Pro**（[tushare.pro](https://tushare.pro/)）。请在官网注册并获取 **Token**，在 `backend/.env` 中配置 `TUSHARE_TOKEN`。

**Token 来源**：后端**只读取** `backend/.env` 里的 `TUSHARE_TOKEN`，不会使用终端里 `export TUSHARE_TOKEN=...`，也不会依赖 Tushare 默认写入用户目录的 `token.csv`；与官方示例里先 `set_token` 再 `pro_api()` 的用法不同，本项目统一用 `pro_api(token=...)` 并传入上述配置。

## Python 版本

官方说明建议在 **Python 3.7+** 环境下使用。本仓库后端当前使用 **Python 3.12**，已满足要求，**无需仅为 Tushare 升级或降级 Python**。

## 安装 SDK

```bash
pip install tushare
```

若安装超时，可使用国内 PyPI 镜像，例如：

```bash
pip install tushare -i https://pypi.tuna.tsinghua.edu.cn/simple
```

升级：

```bash
pip install tushare --upgrade
```

查看版本：

```python
import tushare

print(tushare.__version__)
```

## 本项目中的用法

- 同步逻辑见 `backend/app/services/tushare_client.py`（封装 `stock_basic`、`daily`、`income`）。
- 拉数前请确认 Token 有效且账户权限覆盖所需接口（日线、利润表等积分要求以 Tushare 官网为准）。
- 接口探活（不写库）：在 `backend` 目录执行  
  `python -m app.scripts.test_tushare_api [YYYY-MM-DD]`

### 文档维护约定

**每次在项目中首次调用新的 Tushare 接口（或扩大 `pro.xxx` 的入参/字段）时**，须在本文档 **「已接入接口清单」** 中追加一节，至少包含：

1. **接口 API**：Python SDK 调用形式（如 `pro.stock_basic(...)`）及官方文档链接（若有）。
2. **功能简介**：在本项目中的业务用途。
3. **入参 / 出参**：本仓库实际传入的参数、请求或解析的字段说明（可与官方字段对照）。
4. **返回数据简短示例**：1～2 行 JSON 或表格字段示例，便于联调对照。

---

## 已接入接口清单

以下为当前 `backend/app/services/tushare_client.py` 中使用的接口；官方总文档入口：[Tushare 数据接口](https://tushare.pro/document/2)。

---

### 1. `stock_basic` — 股票列表（基础信息）

| 项目 | 说明 |
|------|------|
| **接口 API** | `pro.stock_basic(...)`，对应官方 **股票列表** 接口。参考：[stock_basic](https://tushare.pro/document/2?doc_id=25)。 |
| **功能简介** | 拉取 **上市** 状态股票的基础信息，用于写入 `stock_basic` 表、股票基本信息页与综合选股主数据。 |
| **入参（本项目实际传入）** | `exchange=""`（全市场）、`list_status="L"`（上市）、`fields="ts_code,symbol,name,area,industry,list_date,market,exchange"`。 |
| **出参（本项目使用）** | 对返回 DataFrame 逐行解析后，映射为内部字典：`dm`←`ts_code`，`mc`←`name`，`jys`←由 `ts_code` 后缀推导（SZ/SH/BJ），`region`←`area`，`industry_name`←`industry`，`list_date`←`list_date`（字符串/日期）。 |
| **返回数据简短示例** | 封装函数 `get_stock_list()` 单条元素示例：<br>`{"dm": "000001.SZ", "mc": "平安银行", "jys": "SZ", "region": "深圳", "industry_name": "银行", "list_date": "1991-04-03"}` |

---

### 2. `daily` — 日线行情

| 项目 | 说明 |
|------|------|
| **接口 API** | `pro.daily(...)`，对应官方 **A 股日线行情** 接口。参考：[daily](https://tushare.pro/document/2?doc_id=27)。 |
| **功能简介** | 按 **自然日** 拉取 **全市场** 当日（或指定交易日）日线，用于写入 `stock_daily_quote`、综合选股展示价量与涨跌幅等。 |
| **入参（本项目实际传入）** | `trade_date`：字符串 `YYYYMMDD`（由 `date` 格式化为 `%Y%m%d`）。未传 `ts_code`，表示全市场。 |
| **出参（本项目使用）** | 转为 `dict`，键为 `ts_code`；行内使用字段包括 `open`、`high`、`low`、`close`、`pre_close`、`vol`、`amount`、`pct_chg`、`change` 等，经 `normalize_daily_bar` 转为内部单位（成交额元、成交量股）。 |
| **返回数据简短示例** | 原始行示例（字段名以接口为准）：<br>`{"ts_code": "000001.SZ", "trade_date": "20260320", "open": 10.5, "high": 10.8, "low": 10.4, "close": 10.6, "pre_close": 10.5, "vol": 123456.0, "amount": 98765.0, "pct_chg": 0.95, "change": 0.1}` |

---

### 3. `income` — 利润表（上市公司财务）

| 项目 | 说明 |
|------|------|
| **接口 API** | `pro.income(...)`，对应官方 **利润表** 接口。参考：[income](https://tushare.pro/document/2?doc_id=33)。 |
| **功能简介** | 按股票代码拉取利润表数据，用于 `stock_financial_report` 及综合选股中的营收、净利润、毛利率等（与同步服务中的处理逻辑配合）。 |
| **入参（本项目实际传入）** | `ts_code`：必填；`start_date`：默认 `"20000101"`；`end_date`：默认 `"20991231"`（可在调用 `get_fin_income` 时传入 `start`/`end` 覆盖，格式 `YYYYMMDD`）。 |
| **出参（本项目使用）** | `DataFrame` 转 `list[dict]` 原样返回；下游会用到如 `end_date`、`total_revenue`、`oper_cost` 等（以官方字段名为准，随报表类型可能略有差异）。 |
| **返回数据简短示例** | 单行示意：<br>`{"ts_code": "000001.SZ", "ann_date": "20240420", "end_date": "20231231", "total_revenue": 1.23e10, "oper_cost": 8.5e9, ...}` |

---

## 其他安装方式（官方摘录）

- 自 [PyPI](https://pypi.python.org/pypi/tushare/) 下载源码包后执行：`python setup.py install`
- 自 [GitHub waditu/tushare](https://github.com/waditu/tushare) clone 后进入目录执行：`python setup.py install`
