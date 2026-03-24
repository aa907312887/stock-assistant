# API 契约：个人服务 / 个人持仓

**功能**: 007-个人持仓 | **日期**: 2026-03-22 | **基路径**: `/api/portfolio`

**鉴权**：除特别说明外，均需 HTTP Header `Authorization: Bearer <access_token>`。未携带或无效 → `401`，正文 `{ "detail": "..." }`。

**通用错误**：

| HTTP | 说明 |
|------|------|
| 400 | 参数校验失败、业务规则不允许（如同股重复建仓） |
| 401 | 未登录 / 令牌无效 |
| 404 | 资源不存在或不属于当前用户 |
| 413 | 上传文件过大 |
| 415 | 图片类型不允许 |
| 500 | 服务端异常（如磁盘写入失败等，正文 `{ "detail": "..." }`） |

---

## 1. 当前进行中的交易（持仓列表）

### `GET /api/portfolio/open-trades`

**说明**：返回当前用户所有 `status=open` 的交易，附带汇总展示字段（代码、名称、数量、成本、参考价、参考盈亏等）。

**响应 200**（示例结构）：

```json
{
  "items": [
    {
      "trade_id": 1,
      "stock_code": "600000.SH",
      "stock_name": "浦发银行",
      "total_qty": 1000,
      "avg_cost": 10.5,
      "ref_close": 10.8,
      "ref_close_date": "2026-03-21",
      "ref_market_value": 10800.0,
      "ref_pnl": 300.0,
      "ref_pnl_pct": 0.0286,
      "has_ref_price": true
    }
  ]
}
```

- `ref_*`：无日线时 `has_ref_price: false`，`ref_close` 等可为 `null`（规格：不伪造）。

---

## 2. 已完结交易列表

### `GET /api/portfolio/closed-trades`

**查询参数**（可选）：

| 参数 | 类型 | 说明 |
|------|------|------|
| page | int | 默认 1 |
| page_size | int | 默认 20，最大 100 |
| stock_code | string | 按代码筛选 |

**响应 200**：

```json
{
  "total": 5,
  "items": [
    {
      "trade_id": 10,
      "stock_code": "600000.SH",
      "stock_name": "浦发银行",
      "closed_at": "2026-03-20T15:00:00",
      "realized_pnl": -120.5,
      "realized_pnl_rate": -0.0115,
      "review_text": "止损及时",
      "image_count": 2
    }
  ]
}
```

---

## 3. 交易详情（含操作记录）

### `GET /api/portfolio/trades/{trade_id}`

**响应 200**：

```json
{
  "trade": {
    "id": 10,
    "stock_code": "600000.SH",
    "stock_name": "浦发银行",
    "status": "closed",
    "opened_at": "2026-01-10T00:00:00",
    "closed_at": "2026-03-20T00:00:00",
    "avg_cost": 10.5,
    "total_qty": 0,
    "realized_pnl": -120.5,
    "realized_pnl_rate": -0.0115,
    "review_text": "..."
  },
  "operations": [
    {
      "id": 101,
      "op_type": "open",
      "op_date": "2026-01-10",
      "qty": 1000,
      "price": 10.5,
      "operation_rating": "good",
      "note": null
    }
  ],
  "images": [
    { "id": 1, "url": "/api/portfolio/images/1/file" }
  ]
}
```

- `images`：已上传复盘图的元数据列表；无图时为 `[]`。
- `trade.realized_pnl_rate`：整笔盈亏比例，口径为 `realized_pnl / (建仓+加仓金额及手续费总和)`，分母为 0 时返回 `null`。

---

## 4. 建仓（新开一笔交易）

### `POST /api/portfolio/trades/open`

**前置条件**：该用户**不存在**同一 `stock_code` 的 `open` 交易。

**请求体**：

```json
{
  "stock_code": "600000.SH",
  "op_date": "2026-03-22",
  "qty": 1000,
  "price": 10.5,
  "fee": 0
}
```

**响应 201**：返回 `{ "trade_id": 1, "operation_id": 1 }`。

**错误 400**：`同一股票已存在未完结持仓，请先清仓或删除该持仓`。

---

## 5. 加仓 / 减仓

### `POST /api/portfolio/trades/{trade_id}/operations`

**请求体**：

```json
{
  "op_type": "add",
  "op_date": "2026-03-23",
  "qty": 500,
  "price": 10.5,
  "fee": 0,
  "operation_rating": null,
  "note": ""
}
```

- `op_type`：`add` | `reduce`。

**响应 201**：`{ "operation_id": 2 }`。

---

## 6. 清仓（结束交易）

### `POST /api/portfolio/trades/{trade_id}/close`

**请求体**：

```json
{
  "op_date": "2026-03-25",
  "qty": 1500,
  "price": 10.2,
  "fee": 5,
  "operation_rating": "good",
  "note": "止损"
}
```

**规则**：`qty` 必须等于当前剩余持仓数量（或等价：仅允许一次 `close` 卖光）。

**响应 200**：`{ "trade_id": 1, "realized_pnl": -120.5 }`。

---

## 7. 更新复盘文字

### `PATCH /api/portfolio/trades/{trade_id}/review`

**请求体**：

```json
{
  "review_text": "心得..."
}
```

**约束**：建议仅 `status=closed` 时可写；若允许 open 中草稿，需在实现中注明（本期建议 **closed 后**）。

---

## 8. 复盘图片上传

### `POST /api/portfolio/trades/{trade_id}/images`

**Content-Type**: `multipart/form-data`，字段名 `file`。

**响应 201**：

```json
{
  "image_id": 5,
  "url": "/api/portfolio/images/5/file"
}
```

### `DELETE /api/portfolio/images/{image_id}`

删除元数据与磁盘文件。

### `GET /api/portfolio/images/{image_id}/file`

返回图片二进制流（`Content-Type` 与存储一致）；**仅本人**可访问。

---

## 9. 对操作记录自评

### `PATCH /api/portfolio/operations/{operation_id}/rating`

**请求体**：

```json
{
  "operation_rating": "good"
}
```

或 `null` 表示清除自评。

---

## 10. 删除进行中的交易（可选）

### `DELETE /api/portfolio/trades/{trade_id}`

**约束**：仅 `status=open`；级联删除 `operations`。

**响应 204**。

---

## 11. 胜率与汇总

### `GET /api/portfolio/stats`

**查询参数**（可选）：`from_date`、`to_date`（按 `closed_at` 或 `op_date` 过滤，实现时约定一种）。

**响应 200**：

```json
{
  "stock_win_rate": {
    "won": 3,
    "lost": 2,
    "breakeven": 0,
    "total": 5,
    "rate": 0.6
  },
  "operation_win_rate": {
    "good": 8,
    "bad": 2,
    "unrated": 5,
    "rated_total": 10,
    "rate": 0.8
  },
  "overall_pnl": {
    "total_profit": 5600.2,
    "total_loss": -2130.6,
    "net_pnl": 3469.6,
    "net_pnl_rate": 0.449
  }
}
```

- `operation_win_rate.rate` = `good / (good+bad)`，无分母时返回 `null` 或 `0` 并带 `unrated` 说明。
- `overall_pnl.total_profit` 为已完结交易中正收益求和；`total_loss` 为负收益求和（负数）。
- `overall_pnl.net_pnl` = `total_profit + total_loss`；`net_pnl_rate` = `net_pnl / (total_profit + |total_loss|)`，分母为 0 时返回 `null`。

---

## 12. 删除持仓（规格验收）

与「删除」一致：对 `open` 的 `trade` 调用 `DELETE /api/portfolio/trades/{trade_id}`。
