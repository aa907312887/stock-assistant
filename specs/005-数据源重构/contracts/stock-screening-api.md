# API 契约：选股与历史日线查询

**功能**: 005-数据源重构 | **日期**: 2026-03-21

## 1. 选股列表

- **路径**: `GET /api/stock/screening`
- **鉴权**: 需要登录态
- **说明**: 基于 `stock_daily_bar` 历史日线主表进行分页与筛选，返回指定（或默认最新）交易日对应的数据。

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页条数，默认 20，上限 100 |
| `code` | string | 否 | 股票代码**模糊**匹配 |
| `name` | string | 否 | 股票名称**模糊**匹配 |
| `ma_bull` | bool | 否 | 是否**均线多头排列**：`MA5 > MA10 > MA20 > MA60` 且四线均非空；`true` 仅保留满足者，`false` 仅保留不满足者，不传为不限 |
| `macd_red` | bool | 否 | 是否 **MACD 红柱**：`macd_hist > 0`；`true` / `false` / 不传 同上 |
| `ma_cross` | bool | 否 | 是否 **MA5 上穿 MA10**：上一根 `ma5≤ma10` 且当前根 `ma5>ma10`（四值均非空）；需存在紧邻上一根同周期 K；`false` 含无上一根或未成金叉 |
| `macd_cross` | bool | 否 | 是否 **MACD 金叉**：上一根 `dif≤dea` 且当前根 `dif>dea`；需存在紧邻上一根同周期 K |
| `timeframe` | string | 否 | `daily`（日K，默认） / `weekly`（周K） / `monthly`（月K）；决定查询 `stock_daily_bar` / `stock_weekly_bar` / `stock_monthly_bar` |
| `data_date` | string | 否 | 指定周期结束日，格式 `YYYY-MM-DD`；不传则默认取该表最大日期列（日：`trade_date`，周：`trade_week_end`，月：`trade_month_end`） |

### 成功响应

```json
{
  "items": [
    {
      "code": "000001.SZ",
      "name": "平安银行",
      "exchange": "SZ",
      "trade_date": "2026-03-20",
      "open": 12.50,
      "high": 12.65,
      "low": 12.31,
      "close": 12.60,
      "price": 12.60,
      "prev_close": 12.50,
      "change_amount": 0.10,
      "pct_change": 0.80,
      "ma5": 12.55,
      "ma10": 12.40,
      "ma20": 12.20,
      "ma60": 11.90,
      "macd_dif": 0.0123,
      "macd_dea": 0.0098,
      "macd_hist": 0.0050,
      "volume": 1000000,
      "amount": 12600000.00,
      "amplitude": 2.72,
      "turnover_rate": 1.26,
      "pe": 8.20,
      "pe_ttm": 8.05,
      "pb": 0.85,
      "dv_ratio": 4.10,
      "report_date": "2025-12-31",
      "revenue": 123456789000.00,
      "net_profit": 9988776600.00,
      "eps": 2.35,
      "gross_profit_margin": 30.20,
      "updated_at": "2026-03-21T17:05:00"
    }
  ],
  "total": 5000,
  "page": 1,
  "page_size": 20,
  "timeframe": "daily",
  "data_date": "2026-03-20"
}
```

### 错误约定

- `401`：未登录
- `422`：参数格式错误或数值区间非法
- `500`：服务异常

### 空结果约定

- 返回 `200 OK`
- `items=[]`
- `total=0`
- 若已存在历史数据，仍返回 `data_date`

## 2. 最新 K 线日期（按周期）

- **路径**: `GET /api/stock/screening/latest-date`
- **鉴权**: 需要登录态
- **Query**: `timeframe` — `daily` | `weekly` | `monthly`（默认 `daily`）
- **说明**: 返回对应 bar 表最大日期列（日/周/月）

### 成功响应

```json
{
  "date": "2026-03-20",
  "timeframe": "daily"
}
```

## 3. 契约约定

- 本接口返回的“最新数据”仅指**最新历史日线日期**，不表示实时行情。
- `price` 与 `close` 保持一致，方便兼容现有前端展示逻辑。
- 财报字段取 `stock_financial_report` 中不晚于 `data_date` 的最近报告期记录。
- 均线与 MACD 展示字段来自 `stock_daily_bar`；筛选条件以服务端上述布尔/模糊逻辑为准；指标未落库时列表中可能为 `null`。
