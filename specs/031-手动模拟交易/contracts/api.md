# API 契约：手动模拟交易

**日期**: 2026-06-06 | **路由前缀**: `/api/manual-trading`  
**鉴权**: 所有端点须 `Authorization: Bearer <access_token>`（`get_current_user`）

---

## 通用错误

| HTTP | code | 说明 |
|------|------|------|
| 401 | — | 未登录或令牌无效 |
| 403 | `FORBIDDEN` | 非本人会话 |
| 404 | `SESSION_NOT_FOUND` | session_id 不存在 |
| 400 | `INVALID_PARAM` | 参数非法（空名称、非正金额/价格等） |
| 409 | `SESSION_ENDED` | 会话已结束 |
| 409 | `AWAITING_REVAL` | 待录价中，不可买入/推进/结束 |
| 409 | `NOT_AWAITING_REVAL` | 当前不在待录价状态 |
| 409 | `NO_BUY_YET` | 尚无买入，不可结束 |

---

## 1. 创建会话

**POST** `/api/manual-trading/sessions`

**请求体**：

```json
{
  "asset_name": "纳斯达克100",
  "start_date": "2001-01-01",
  "name": "2001起算"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `asset_name` | string | 是 | 自定义标的名称，1～100 字 |
| `start_date` | string | 是 | YYYY-MM-DD |
| `name` | string | 否 | 会话备注 |

**响应 201**：`SessionDetailResponse`（见 §8）

---

## 2. 会话列表

**GET** `/api/manual-trading/sessions`

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `status` | string | 不限 | `active` / `ended` |
| `page` | int | 1 | ≥1 |
| `page_size` | int | 20 | 1～50 |

**响应 200**：

```json
{
  "total": 1,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "session_id": "mt-a1b2c3d4",
      "name": "2001起算",
      "asset_name": "纳斯达克100",
      "start_date": "2001-01-01",
      "current_date": "2002-01-01",
      "position_value": 90000.0,
      "total_invested": 100000.0,
      "total_pnl": -10000.0,
      "status": "active",
      "awaiting_reval": false,
      "created_at": "2026-06-06T10:00:00"
    }
  ]
}
```

---

## 3. 会话详情

**GET** `/api/manual-trading/sessions/{session_id}`

**响应 200** — `SessionDetailResponse`：

```json
{
  "session_id": "mt-a1b2c3d4",
  "name": "2001起算",
  "asset_name": "纳斯达克100",
  "start_date": "2001-01-01",
  "current_date": "2001-01-01",
  "reference_price": 2000.0,
  "position_value": 100000.0,
  "total_invested": 100000.0,
  "total_pnl": 0.0,
  "total_pnl_pct": 0.0,
  "total_trading_days": null,
  "status": "active",
  "awaiting_reval": false,
  "end_date": null,
  "first_operation_date": "2001-01-01",
  "created_at": "2026-06-06T10:00:00",
  "updated_at": "2026-06-06T10:05:00"
}
```

---

## 4. 删除会话

**DELETE** `/api/manual-trading/sessions/{session_id}`

**响应 204** 无 body。级联删除流水。

---

## 5. 买入

**POST** `/api/manual-trading/sessions/{session_id}/buy`

**请求体**：

```json
{
  "amount": 100000.0,
  "price": 2000.0
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `amount` | number | 是 | 买入金额（元），>0 |
| `price` | number | 是 | 成交价，>0 |

**行为**：

- `position_value += amount`，`total_invested += amount`
- 若 `reference_price` 为空，设为 `price`
- 写入 `buy` 流水；首笔买入时设置 `first_operation_date = current_date`

**响应 200**：`SessionDetailResponse`

---

## 6. 快捷推进时间

**POST** `/api/manual-trading/sessions/{session_id}/advance`

**请求体**：

```json
{
  "step": "year"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `step` | string | 是 | `day` / `week` / `month` / `year` |

**行为**：

- `current_date` 按步长递增
- `awaiting_reval = true`（内存中暂存 `last_advance_step` 供录价流水使用，可存 session 扩展字段或 service 层暂存；**推荐**会话表增加 `last_advance_step` VARCHAR(10) NULL）

**响应 200**：

```json
{
  "session_id": "mt-a1b2c3d4",
  "current_date": "2002-01-01",
  "awaiting_reval": true,
  "step": "year"
}
```

---

## 7. 录入收盘价（完成估值推进）

**POST** `/api/manual-trading/sessions/{session_id}/reval`

**请求体**：

```json
{
  "close_price": 1800.0
}
```

**行为**（`position_value > 0` 且 `reference_price > 0`）：

- `position_after = position_before × (close_price / reference_price)`
- `segment_pnl = position_after − position_before`
- 更新 `reference_price = close_price`，`awaiting_reval = false`
- 写入 `reval` 流水（含 `advance_step`）

若 `position_value = 0`：仅更新 `reference_price` 与 `awaiting_reval`，`segment_pnl = 0`。

**响应 200**：`SessionDetailResponse`

---

## 8. 结束交易

**POST** `/api/manual-trading/sessions/{session_id}/end`

**行为**：

- `status = ended`，`end_date = current_date`
- 写入 `end` 流水

**响应 200**：`SessionDetailResponse`（含 `total_trading_days`）

---

## 9. 操作流水（复盘）

**GET** `/api/manual-trading/sessions/{session_id}/operations`

**响应 200**：

```json
{
  "session_id": "mt-a1b2c3d4",
  "total_pnl": -10000.0,
  "total_trading_days": 365,
  "items": [
    {
      "id": 1,
      "op_type": "buy",
      "op_type_label": "买入",
      "op_date": "2001-01-01",
      "price": 2000.0,
      "buy_amount": 100000.0,
      "advance_step": null,
      "position_before": 0.0,
      "position_after": 100000.0,
      "segment_pnl": null,
      "days_since_prev": null
    },
    {
      "id": 2,
      "op_type": "reval",
      "op_type_label": "估值推进",
      "op_date": "2002-01-01",
      "price": 1800.0,
      "buy_amount": null,
      "advance_step": "year",
      "position_before": 100000.0,
      "position_after": 90000.0,
      "segment_pnl": -10000.0,
      "days_since_prev": 365
    }
  ]
}
```

`op_type_label` 由后端映射：`buy`→买入，`reval`→估值推进，`end`→结束交易。

---

## 数据流摘要

```text
前端 ManualTradingView
  → POST/GET /api/manual-trading/*（Bearer）
    → manual_trading_service（Decimal 计算、状态校验）
      → manual_trading_session / manual_trading_operation（MySQL）
```
