# API 契约：60 日均线买入法（复用现有端点）

**日期**: 2026-04-16 | **路由前缀**: `/api`  
**策略标识**: `strategy_id = ma60_slope_buy`

> 本功能**不新增** HTTP 路径；以下均为既有契约上新增**允许的 strategy_id 取值**与响应字段语义说明。

---

## 1. 列出策略（回测下拉、前端展示）

**GET** `/api/strategies`

**响应 200**：`ListStrategiesResponse`（结构不变）。`items[]` 中新增一项，例如：

```json
{
  "strategy_id": "ma60_slope_buy",
  "name": "60日均线买入法",
  "version": "v1.0.0",
  "short_description": "MA60斜率由负转正并经次日确认后，按确认日收盘价买入；盈利15%或亏损8%以收盘价止盈止损。",
  "route_path": "/strategy/ma60-slope-buy"
}
```

**错误**：无新增错误码。

---

## 2. 策略详情

**GET** `/api/strategies/ma60_slope_buy`

**响应 200**：`GetStrategyResponse`，`description` / `assumptions` / `risks` 与 `describe()` 一致。

**错误**：

- `404`：`{"code":"NOT_FOUND","message":"策略不存在"}`（仅当注册遗漏时）

---

## 3. 手动执行选股（可选页面）

**POST** `/api/strategies/ma60_slope_buy/execute`

**请求体**：`ExecuteStrategyRequest`（与现有一致）

```json
{
  "as_of_date": "2024-06-28"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `as_of_date` | string (YYYY-MM-DD) | 否 | 不传则按服务端默认「最近可用交易日」规则（与现有策略一致） |

**响应 200**：`ExecuteStrategyResponse`

- `items[]`：`StrategySelectionItem`，`trigger_date` 为 **\(t\)**；`summary` 建议含 `slope_t_minus_1`、`slope_t`、`slope_t_plus_1`、`buy_would_be_close`（确认日收盘价）等便于核对。  
- `signals[]`：可选 `event_type` 为 `trigger` / `note`，payload 携带关键数值。

**错误**：

- `404`：`NOT_FOUND`  
- `409`：`DATA_NOT_READY`（行情未同步到 `as_of_date`）  
- `500`：`INTERNAL_ERROR`

---

## 4. 发起历史回测

**POST** `/api/backtest/run`

**请求体**（与 `RunBacktestRequest` 一致，仅 `strategy_id` 取值扩展）：

```json
{
  "strategy_id": "ma60_slope_buy",
  "start_date": "2023-01-01",
  "end_date": "2024-12-31",
  "position_amount": 100000,
  "reserve_amount": 100000
}
```

**响应**：与现网 `RunBacktestResponse` 相同。

**错误**：`400` 参数校验；策略不存在时由引擎或前置校验返回与现有一致结构。

---

## 5. 任务详情 / 交易明细 / 筛选复算

**GET** `/api/backtest/tasks/{task_id}`  
**GET** `/api/backtest/tasks/{task_id}/trades`  
**GET** `/api/backtest/tasks/{task_id}/filtered-report`  
**GET** `/api/backtest/tasks/{task_id}/yearly-analysis`  
**GET** `/api/backtest/tasks/{task_id}/best-options`

**约定**：路径、Query、响应结构**不变**；当任务 `strategy_id` 为 `ma60_slope_buy` 时，`trades` 中 `trigger_date` / `buy_date` / `extra` 字段语义遵循本功能 `plan.md` 与 `spec.md`。
