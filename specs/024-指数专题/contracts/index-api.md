# 接口契约摘要：指数专题 API

**前缀**: `/api/index`（建议）  
**鉴权**: 与 `/api/stock` 相同，需登录（`get_current_user`）。

## GET `/screening`

**Query**

| 参数 | 类型 | 说明 |
|------|------|------|
| page | int | 默认 1 |
| page_size | int | 1–100 |
| timeframe | daily \| weekly \| monthly | 默认 daily |
| code | string | 指数代码模糊 |
| name | string | 名称模糊 |
| data_date | date | 可选，指定快照日 |

**响应** `200`

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20,
  "timeframe": "daily",
  "data_date": "2026-04-18"
}
```

`items[]` 字段与综合选股列表中对齐的 OHLCV、涨跌幅、均线、MACD 等；价格语义为**指数点位**；无 PE 等个股字段时可省略或 `null`。

## GET `/screening/latest-date`

**Query**: `timeframe`

**响应**: `{ "latest_date": "2026-04-18" }`（字段名与现有 `LatestDateResponse` 对齐）

## GET `/{ts_code}/composition`

**Query**

| 参数 | 说明 |
|------|------|
| trade_date | 可选；个股 PE 百分位快照日 \(T\)，用于关联 `stock_daily_bar` |
| weight_as_of | 可选；不传则服务端按 `plan.md` 选用最近一期 `index_weight` |

**响应** `200`

```json
{
  "ts_code": "399300.SZ",
  "weight_table_date": "2026-03-31",
  "snapshot_trade_date": "2026-04-18",
  "index_pe_percentile": 45.2,
  "pe_percentile_meta": {
    "formula": "weighted_mean_renormalize",
    "participating_weight_ratio": 0.92,
    "constituents_total": 300,
    "constituents_with_pe": 278
  },
  "items": [
    { "con_code": "000001.SZ", "weight": 0.5, "pe_percentile": 40.1 }
  ]
}
```

- `index_pe_percentile`：由成分 **PE 历史百分位**与权重加权推理（见 `spec.md` **FR-010**）；无为 `null`。  
- `items[].pe_percentile`：可为 `null`，表示该股当日无 PE 百分位或未入库。

无成分：`items: []`，`index_pe_percentile` 一般为 `null`，可附 `message`。

## 错误码

与全局 FastAPI 异常约定一致；业务错误 body 含 `code` + `message`。
