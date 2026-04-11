# API 契约：历史模拟交易

**日期**: 2026-04-09 | **路由前缀**: `/api/paper-trading`

> 时间节点说明：每个交易日分「开盘（open）」和「收盘（close）」两个 phase。
> 会话 `current_phase` 字段标识当前所处节点，影响图表数据、快捷价格按钮和操作权限。

---

## 1. 创建模拟交易会话

**POST** `/api/paper-trading/sessions`

**请求体**：
```json
{
  "start_date": "2021-01-04",
  "initial_cash": 100000.00,
  "name": "2021年牛市复盘"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `start_date` | string (YYYY-MM-DD) | 是 | 模拟起始日期，必须是交易日 |
| `initial_cash` | number | 是 | 初始资金（元），最小 1000 |
| `name` | string | 否 | 会话名称，默认为空 |

**响应 201**：
```json
{
  "session_id": "pt-a1b2c3d4",
  "start_date": "2021-01-04",
  "current_date": "2021-01-04",
  "current_phase": "open",
  "initial_cash": 100000.00,
  "available_cash": 100000.00,
  "status": "active",
  "created_at": "2026-04-09T10:00:00"
}
```

**错误**：
- `400 INVALID_DATE`：start_date 不是交易日或超出数据范围
- `400 INVALID_CASH`：initial_cash < 1000

---

## 2. 查询会话列表

**GET** `/api/paper-trading/sessions`

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `status` | string | 不限 | `active` / `ended` |
| `page` | int | 1 | 页码 |
| `page_size` | int | 20 | 每页数量，最大 50 |

**响应 200**：
```json
{
  "total": 5,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "session_id": "pt-a1b2c3d4",
      "name": "2021年牛市复盘",
      "start_date": "2021-01-04",
      "current_date": "2021-03-15",
      "initial_cash": 100000.00,
      "available_cash": 85000.00,
      "total_asset": 112000.00,
      "status": "active",
      "created_at": "2026-04-09T10:00:00"
    }
  ]
}
```

---

## 3. 查询会话详情

**GET** `/api/paper-trading/sessions/{session_id}`

**响应 200**：
```json
{
  "session_id": "pt-a1b2c3d4",
  "name": "2021年牛市复盘",
  "start_date": "2021-01-04",
  "current_date": "2021-03-15",
  "initial_cash": 100000.00,
  "available_cash": 85000.00,
  "status": "active",
  "positions": [
    {
      "stock_code": "000001.SZ",
      "stock_name": "平安银行",
      "total_quantity": 300,
      "avg_cost_price": 20.50,
      "current_price": 22.10,
      "market_value": 6630.00,
      "profit_loss": 480.00,
      "profit_loss_pct": 0.0781,
      "can_sell_quantity": 200
    }
  ],
  "closed_stocks": [
    {
      "stock_code": "600000.SH",
      "stock_name": "浦发银行",
      "closed_batch_count": 2,
      "realized_profit_loss": 1280.5,
      "realized_profit_loss_pct": 0.0525
    }
  ],
  "total_asset": 112000.00,
  "total_profit_loss": 12000.00,
  "total_profit_loss_pct": 0.12,
  "created_at": "2026-04-09T10:00:00",
  "market_temp_ref_date": "2021-03-12",
  "market_temp_score": 62.50,
  "market_temp_level": "偏热"
}
```

> `market_temp_ref_date` / `market_temp_score` / `market_temp_level`：界面展示用的大盘温度，对应**当前模拟日 `current_date` 的上一交易日**收盘后的结果（非模拟当日），与 `market_temperature_daily` 中该交易日、当前公式版本一致；若无上一交易日或尚无温度记录则 `market_temp_ref_date` 可为 `null`，分数与级别可为 `null`。

> `can_sell_quantity`：当日可卖数量（排除当日买入批次后的剩余数量）

> `closed_stocks`：当前对该代码**已无** `holding` 批次、但存在 `closed` 批次的股票（曾全部卖出）；用于前端「已清仓」列表。若该股再次买入，则不再出现在此列表中。`realized_profit_loss` / `realized_profit_loss_pct` 为本会话内该代码**已实现**盈亏：卖出净入金（成交额减卖手续费）减买入净出金（成交额加买手续费）；比例分母为买入总成本（含买手续费）。

**错误**：`404 SESSION_NOT_FOUND`

---

## 4. 推进到收盘

**POST** `/api/paper-trading/sessions/{session_id}/advance-to-close`

无请求体。将当日 phase 从 `open` 推进到 `close`，持仓市值改用收盘价重算。

**响应 200**：
```json
{
  "current_date": "2021-03-15",
  "current_phase": "close",
  "available_cash": 85000.00,
  "positions": [
    {
      "stock_code": "000001.SZ",
      "stock_name": "平安银行",
      "total_quantity": 300,
      "avg_cost_price": 20.50,
      "current_price": 22.10,
      "market_value": 6630.00,
      "profit_loss": 480.00,
      "profit_loss_pct": 0.0781,
      "can_sell_quantity": 200
    }
  ],
  "closed_stocks": [],
  "market_temp_ref_date": "2021-03-12",
  "market_temp_score": 62.50,
  "market_temp_level": "偏热"
}
```

**错误**：
- `400 ALREADY_CLOSED`：当日已处于收盘状态
- `400 SESSION_NOT_ACTIVE`：会话已结束

---

## 5. 进入下一交易日

**POST** `/api/paper-trading/sessions/{session_id}/next-day`

无请求体。仅在 `current_phase='close'` 时允许调用。

**响应 200**：
```json
{
  "previous_date": "2021-03-15",
  "current_date": "2021-03-16",
  "current_phase": "open",
  "available_cash": 85000.00,
  "positions": [],
  "closed_stocks": [],
  "market_temp_ref_date": "2021-03-15",
  "market_temp_score": 58.00,
  "market_temp_level": "中性"
}
```

**错误**：
- `400 PHASE_NOT_CLOSE`：当日尚未推进到收盘，不能进入下一天
- `400 ALREADY_ENDED`：会话已结束
- `400 NO_MORE_DATES`：已到达数据最新日期

---

## 6. 结束会话

**POST** `/api/paper-trading/sessions/{session_id}/end`

无请求体。

**响应 200**：
```json
{ "session_id": "pt-a1b2c3d4", "status": "ended" }
```

---

## 6. 买入股票

**POST** `/api/paper-trading/sessions/{session_id}/buy`

**请求体**：
```json
{
  "stock_code": "000001.SZ",
  "price": 20.50,
  "quantity": 100
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `stock_code` | string | 是 | 股票代码 |
| `price` | number | 是 | 买入价格（元），用户手动输入 |
| `quantity` | int | 是 | 买入数量（股），必须为 100 的整数倍 |

**响应 200**：
```json
{
  "order_id": 123,
  "stock_code": "000001.SZ",
  "stock_name": "平安银行",
  "price": 20.50,
  "quantity": 100,
  "amount": 2050.00,
  "commission": 5.00,
  "cash_after": 82945.00,
  "position_id": 456
}
```

**错误**：
- `400 STOCK_SUSPENDED`：股票当日停牌（无数据）
- `400 PRICE_OUT_OF_LIMIT`：价格超出涨跌停范围，附带 `limit_up` 和 `limit_down` 字段
- `400 INVALID_QUANTITY`：数量不是 100 的整数倍
- `400 INSUFFICIENT_CASH`：资金不足，附带 `required` 和 `available` 字段
- `400 SESSION_NOT_ACTIVE`：会话已结束

---

## 7. 卖出股票

**POST** `/api/paper-trading/sessions/{session_id}/sell`

**请求体**：
```json
{
  "stock_code": "000001.SZ",
  "price": 22.10,
  "quantity": 100
}
```

**响应 200**：
```json
{
  "order_id": 124,
  "stock_code": "000001.SZ",
  "stock_name": "平安银行",
  "price": 22.10,
  "quantity": 100,
  "amount": 2210.00,
  "commission": 5.00,
  "cash_after": 85150.00
}
```

**错误**：
- `400 STOCK_SUSPENDED`：股票当日停牌
- `400 PRICE_OUT_OF_LIMIT`：价格超出涨跌停范围
- `400 INVALID_QUANTITY`：数量不是 100 的整数倍
- `400 T1_RESTRICTION`：当日买入的股票不可当日卖出
- `400 INSUFFICIENT_POSITION`：持仓不足，附带 `available_quantity` 字段
- `400 SESSION_NOT_ACTIVE`：会话已结束

---

## 8. 查询交易记录

**GET** `/api/paper-trading/sessions/{session_id}/orders`

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `order_type` | string | 不限 | `buy` / `sell` |
| `stock_code` | string | 不限 | 按股票筛选 |
| `page` | int | 1 | 页码 |
| `page_size` | int | 50 | 每页数量，最大 500 |
| `sort` | string | `desc` | 按订单创建时间：`asc` 正序（先旧后新）/ `desc` 倒序 |

**响应 200**：
```json
{
  "total": 10,
  "page": 1,
  "page_size": 50,
  "items": [
    {
      "order_id": 123,
      "order_type": "buy",
      "stock_code": "000001.SZ",
      "stock_name": "平安银行",
      "trade_date": "2021-01-04",
      "price": 20.50,
      "quantity": 100,
      "amount": 2050.00,
      "commission": 5.00,
      "cash_after": 82945.00,
      "created_at": "2026-04-10T14:32:01"
    }
  ]
}
```

---

## 9. 获取股票图表数据

**GET** `/api/paper-trading/chart-data`

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `stock_code` | string | 是 | 股票代码 |
| `end_date` | string | 是 | 截止日期（当前模拟日期） |
| `phase` | string | 是 | `open` / `close`。**日线**：`open` 时最新一根的 high/low/close、volume、pct_change、MACD 为 null。**周线/月线**：仅返回 `trade_week_end` / `trade_month_end` ≤ `end_date` 的 K 线（不超模拟日）；均线与 MACD 取自 `stock_weekly_bar` / `stock_monthly_bar`。周线、月线在 **`open` 且最新一根的周期末端日期等于 `end_date`** 时，对最新一根同样掩码 high/low/close、volume、pct_change 与 MACD（不提前暴露周期结果）；MA 字段与日线规则一致仍返回库中值。`close` 时上述掩码字段补全。 |
| `period` | string | 否 | `daily`（默认）/ `weekly` / `monthly` |
| `limit` | int | 否 | 返回条数，默认 300，最大 500 |

**响应 200**：
```json
{
  "stock_code": "000001.SZ",
  "stock_name": "平安银行",
  "period": "daily",
  "open_price": 20.10,
  "close_price": 20.50,
  "data": [
    {
      "date": "2021-01-04",
      "open": 20.10,
      "high": 20.80,
      "low": 19.90,
      "close": 20.50,
      "volume": 1234567,
      "prev_close": 19.80,
      "pct_change": 3.54,
      "ma5": 20.20,
      "ma10": 19.80,
      "ma20": 19.50,
      "ma60": 18.90,
      "macd_dif": 0.1234,
      "macd_dea": 0.0987,
      "macd_hist": 0.0494
    }
  ],
  "limit_up": 21.78,
  "limit_down": 17.82
}
```

> `limit_up` / `limit_down`：当日（end_date）的涨跌停价格，方便前端展示快捷填充按钮

---

## 9.1 解析股票（代码 / 名称）

**GET** `/api/paper-trading/resolve-stock`

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `q` | string | 是 | 股票代码或名称片段 |
| `limit` | int | 否 | 返回条数上限，默认 30，最大 50 |

**行为**：先按 `code` 精确匹配；未命中则对 `code`、`name` 做 `LIKE %q%` 模糊查询，按代码排序截断。

**响应 200**：
```json
{
  "items": [
    { "stock_code": "000001.SZ", "stock_name": "平安银行" }
  ]
}
```

---

## 9.2 股票资料快照（基本信息 + 日线 + 财报）

**GET** `/api/paper-trading/stock-info`

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `stock_code` | string | 是 | 股票代码（ts_code） |
| `end_date` | string | 是 | 当前模拟日期 |
| `phase` | string | 是 | `open` / `close`；open 时日线块不返回未揭晓的高、低、收、涨跌幅、振幅；**成交量（volume）、成交额（amount）** 与图表口径一致，亦不提前返回 |

**响应 200**：包含 `basic`（上市信息/行业等）、`daily`（该日 `stock_daily_bar` 一行，无则用 null/空态）、`financial`（`report_date <= end_date` 最近一期 `stock_financial_report`，无则 null）。

**错误**：`404 STOCK_NOT_FOUND`（基础表中无此代码）

---

## 10. 获取当日推荐股票

**GET** `/api/paper-trading/recommend`

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `trade_date` | string | 是 | 当前模拟日期 |
| `phase` | string | 是 | `open` / `close`；open 时 close/pct_change 返回 null |
| `count` | int | 否 | 推荐数量，默认 10 |

**响应 200**：
```json
{
  "trade_date": "2021-01-04",
  "phase": "open",
  "items": [
    {
      "stock_code": "000001.SZ",
      "stock_name": "平安银行",
      "open": 20.10,
      "close": null,
      "pct_change": null,
      "volume": 1234567,
      "limit_up": 21.78,
      "limit_down": 17.82
    }
  ]
}
```

---

## 11. 自定义筛选股票

**GET** `/api/paper-trading/screen`

**查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `trade_date` | string | 必填，当前模拟日期 |
| `pct_change_min` | float | 涨跌幅下限（%），如 `3.0` |
| `pct_change_max` | float | 涨跌幅上限（%） |
| `volume_min` | float | 成交量下限（手） |
| `volume_max` | float | 成交量上限（手） |
| `ma_golden_cross` | string | 均线金叉类型：`ma5_ma10` / `ma5_ma20` |
| `macd_golden_cross` | bool | 是否 MACD 金叉（DIF 上穿 DEA） |
| `page` | int | 页码，默认 1 |
| `page_size` | int | 每页数量，默认 20，最大 100 |

**响应 200**：
```json
{
  "trade_date": "2021-01-04",
  "total": 45,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "stock_code": "000001.SZ",
      "stock_name": "平安银行",
      "open": 20.10,
      "close": 20.50,
      "pct_change": 3.54,
      "volume": 1234567,
      "ma5": 20.20,
      "ma10": 19.80,
      "macd_dif": 0.1234,
      "macd_dea": 0.0987,
      "limit_up": 21.78,
      "limit_down": 17.82
    }
  ]
}
```

---

## 12. 获取交易日列表

**GET** `/api/paper-trading/trading-dates`

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `start` | string | 是 | 起始日期 |
| `end` | string | 是 | 结束日期 |

**响应 200**：
```json
{
  "dates": ["2021-01-04", "2021-01-05", "2021-01-06", "..."],
  "min_date": "2015-01-05",
  "max_date": "2026-04-08"
}
```

---

## 错误响应通用格式

```json
{
  "code": "ERROR_CODE",
  "message": "中文错误说明",
  "detail": {}
}
```
