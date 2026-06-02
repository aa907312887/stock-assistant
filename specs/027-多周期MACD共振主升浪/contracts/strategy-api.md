# 接口契约：多周期 MACD 共振主升浪（增量）

**日期**：2026-06-02  
**路由前缀**：`/api`（与 `app/main.py` 挂载一致）

本功能**不新增独立业务路由**；通过注册新策略实例，下列既有接口的**可用取值与响应列表**增加一项。

**首期范围**：仅保证 **回测** 路径可用；**策略执行（选股）** 可返回空结果或 501 风格业务提示（以实现为准），**不**要求 `route_path` 与前端选股页。

---

## 1. 策略列表（增量）

**`GET /api/strategies`**

### 响应 `items[]` 新增元素示例

```json
{
  "strategy_id": "duo_zhou_qi_macd_gong_zhen",
  "name": "多周期 MACD 共振主升浪",
  "version": "v1.0.0",
  "short_description": "日周月MACD红柱共振；6日递增红柱；D6收盘买入；+10%后3%移动止盈；7%/红转绿/三连跌止损。",
  "route_path": null
}
```

| 字段 | 说明 |
|------|------|
| `strategy_id` | 固定 `duo_zhou_qi_macd_gong_zhen` |
| `route_path` | 首期可为 `null` 或省略；Phase 2 再补 `/strategy/duo-zhou-qi-macd-gong-zhen` |

### 错误

无变更（200）。

---

## 2. 策略详情

**`GET /api/strategies/{strategy_id}`**

当 `strategy_id=duo_zhou_qi_macd_gong_zhen` 时，返回 `describe()` 提供的 `description`、`assumptions`、`risks`。

### 错误

| 状态码 | 场景 |
|--------|------|
| 404 | `strategy_id` 未注册 |

---

## 3. 策略执行（选股）— 首期可选

**`POST /api/strategies/{strategy_id}/execute`**  
**`GET /api/strategies/{strategy_id}/latest`**

首期实现建议：

- 返回 **200** + 空 `candidates` / 0 条信号，并在 `message` 或日志中说明「本期仅支持历史回测」；或  
- 与回测共用扫描函数，在 `as_of_date` 输出**当日可作为 D6 的标的**（不含持仓仿真）。

契约上**不强制**首期实现完整选股落库。

---

## 4. 回测

**`POST /api/backtest/run`**

### 请求体示例

```json
{
  "strategy_id": "duo_zhou_qi_macd_gong_zhen",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "position_amount": 100000,
  "reserve_amount": 100000
}
```

### 成功响应

与 `specs/010-智能回测/contracts` 一致：返回 `task_id`；轮询任务状态后获取 `trades[]`。

### 交易明细增量约定

| 字段 | 说明 |
|------|------|
| `strategy_id` | `duo_zhou_qi_macd_gong_zhen` |
| `trigger_date` | 等于 `buy_date`（D6） |
| `buy_price` / `sell_price` | 均为对应日 **收盘价** |
| `extra.exit_reason` | 见 `data-model.md` |

### 错误

| 状态码 | code | 场景 |
|--------|------|------|
| 400 | 参数校验失败 | 日期非法、`start_date > end_date` |
| 404 | `STRATEGY_NOT_FOUND` | `strategy_id` 未注册 |
| 401 | 未认证 | 无 Bearer Token |

---

## 5. 回测结果详情（前端）

**`GET /api/backtest/tasks/{task_id}`**（及项目现有明细接口）

无需改路由；`BacktestResultDetail` 可对 `exit_reason` 增加 Tooltip 文案映射（实现阶段可选）：

| `exit_reason` | 展示文案（建议） |
|---------------|------------------|
| `stop_loss_7pct` | 亏损达 7%（收盘止损） |
| `sell_macd_red_to_green` | 日线 MACD 红转绿（**不论盈亏**，收盘卖出） |
| `sell_three_down_days` | 连续 3 日收跌（**不论盈亏**，收盘卖出） |
| `trailing_take_profit_3pct` | 移动止盈（+10% 后回撤 3% 收盘） |
