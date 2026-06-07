# 接口契约：月 MACD 翻红（增量）

**日期**：2026-06-06  
**路由前缀**：`/api`（与 `app/main.py` 挂载一致）

本功能**不新增独立业务路由**；通过注册新策略实例，下列既有接口的**可用取值与响应列表**增加一项。

**首期范围**：保证 **历史模拟** 与 **历史回测** 路径可用；**策略执行（选股）** 可返回空结果，**不**要求 `route_path` 与前端选股页。

---

## 1. 策略列表（增量）

**`GET /api/strategies`**

### 响应 `items[]` 新增元素示例

```json
{
  "strategy_id": "yue_macd_fan_hong",
  "name": "月 MACD 翻红",
  "version": "v1.0.0",
  "short_description": "主板；月线MACD绿转红后首个红柱月末收盘买；±20%止盈止损；后续任一月MACD红转绿月末卖。",
  "route_path": "/backtest/simulation"
}
```

| 字段 | 说明 |
|------|------|
| `strategy_id` | 固定 `yue_macd_fan_hong` |
| `route_path` | 指向历史模拟入口；Phase 2 可增选股页 |

### 错误

无变更（200）。

---

## 2. 策略详情

**`GET /api/strategies/{strategy_id}`**

当 `strategy_id=yue_macd_fan_hong` 时，返回 `describe()` 提供的 `description`、`assumptions`、`risks`。

### 错误

| 状态码 | 场景 |
|--------|------|
| 404 | `strategy_id` 未注册 |

---

## 3. 策略执行（选股）— 首期

**`POST /api/strategies/{strategy_id}/execute`**  
**`GET /api/strategies/{strategy_id}/latest`**

首期实现建议：

- 返回 **200** + 空 `candidates`，`message` 说明「本期仅支持历史模拟/回测」。

契约上**不强制**首期实现完整选股落库。

---

## 4. 历史模拟（主场景）

**`POST /api/simulation/run`**

### 请求体示例

```json
{
  "strategy_id": "yue_macd_fan_hong",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31"
}
```

### 成功响应

与 `specs/018-历史模拟优化/contracts` 一致：返回 `task_id`；轮询 `GET /api/simulation/tasks/{task_id}` 获取 `trades[]`。

### 交易明细增量约定

| 字段 | 说明 |
|------|------|
| `strategy_id` | `yue_macd_fan_hong` |
| `trigger_date` | 等于 `buy_date`（首个红柱月最后交易日） |
| `buy_price` / `sell_price` | 均为对应日 **收盘价** |
| `extra.exit_reason` | 见 `data-model.md` |

### 错误

| 状态码 | code | 场景 |
|--------|------|------|
| 400 | 参数校验失败 | 日期非法 |
| 404 | `STRATEGY_NOT_FOUND` | 未注册 |
| 401 | 未认证 | 无 Bearer Token |

---

## 5. 历史回测

**`POST /api/backtest/run`**

### 请求体示例

```json
{
  "strategy_id": "yue_macd_fan_hong",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "position_amount": 100000,
  "reserve_amount": 100000
}
```

### 成功响应

与 `specs/010-智能回测/contracts` 一致；策略层 `trades` 与模拟一致，引擎层可能附加 `not_traded`。

### 错误

同第 4 节。

---

## 6. 任务详情 exit_reason 展示（可选）

**`GET /api/simulation/tasks/{task_id}`** / **`GET /api/backtest/tasks/{task_id}`**

实现阶段可选增加 Tooltip 映射：

| `exit_reason` | 展示文案（建议） |
|---------------|------------------|
| `take_profit_20pct` | 盈利达 20%（收盘止盈） |
| `stop_loss_20pct` | 亏损达 20%（收盘止损） |
| `sell_monthly_macd_red_to_green` | 月线 MACD 红转绿（该月最后交易日收盘卖出） |
