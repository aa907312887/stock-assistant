# 接口契约：早晨十字星（简化版）策略（增量）

**日期**：2026-05-03  
**路由前缀**：`/api`（与 `app/main.py` 挂载一致）

本功能**不新增独立业务路由**；通过注册新策略实例，下列既有接口的**可用取值与响应列表**增加一项。

---

## 1. 策略列表（增量）

**`GET /api/strategies`**

### 响应 `items[]` 新增元素示例

```json
{
  "strategy_id": "zao_chen_shi_zi_xing_jian_hua",
  "name": "早晨十字星（简化版）",
  "version": "v1.0.0",
  "short_description": "形态同早晨十字星；收盘≤历史高80%；T+1开盘买入；止盈8%止损6%。",
  "route_path": "/strategy/zao-chen-shi-zi-xing-jian-hua"
}
```

| 字段 | 说明 |
|------|------|
| `strategy_id` | 固定 `zao_chen_shi_zi_xing_jian_hua` |
| `route_path` | 前端策略说明页路由，与 `Layout.vue` 菜单一致 |

### 错误

无变更（200）。

---

## 2. 策略详情

**`GET /api/strategies/{strategy_id}`**

当 `strategy_id=zao_chen_shi_zi_xing_jian_hua` 时，返回完整 `description`、`assumptions`、`risks`（由策略类 `describe()` 提供）。

### 错误

| 状态码 | 场景 |
|--------|------|
| 404 | `strategy_id` 未注册 |

---

## 3. 策略执行（选股）

**`POST /api/strategies/{strategy_id}/execute`**

**`GET /api/strategies/{strategy_id}/latest`**

请求/响应模型与现有策略相同。`strategy_id` 为本策略时：

- 在 `as_of_date`（或请求体指定日期）执行与回测一致的形态 + **80%** 历史高位过滤；
- 返回当日满足条件的标的列表；业务语义为 **触发日 T = as_of_date（或扫描范围内当日为 T）**，买入执行日为 **T+1 开盘**（展示层说明）。

---

## 4. 回测

**`POST /api/backtest/run`**

请求体示例：

```json
{
  "strategy_id": "zao_chen_shi_zi_xing_jian_hua",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

### 错误

| 状态码 | code | 场景 |
|--------|------|------|
| 404 | `STRATEGY_NOT_FOUND` | 策略未注册 |

其余同 `specs/010-智能回测/contracts/backtest-api.md`。

---

## 5. 交易明细分页

**`GET /api/backtest/tasks/{task_id}/trades`**

单条记录中：`trigger_date` 为第三根阳线日 **T**；`buy_date` 多为 **T 的下一交易日**（或停牌顺延），与「早晨十字星」主策略「T 与 buy_date 关系」不同，前端 Tooltip 文案需在实现阶段区分（见前端任务）。

---

## 6. 错误类消息（数据未就绪）

与「早晨十字星」类似：若数据库缺 `cum_hist_high` 等，策略抛出的 `RuntimeError` 提示执行 SQL / 重算脚本；**HTTP 层映射**以现有回测/执行服务为准（通常在日志中体现，不一定暴露给前端）。
