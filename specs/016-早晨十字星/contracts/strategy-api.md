# 接口契约：早晨十字星与策略列表（增量）

**日期**：2026-03-29  
**路由前缀**：`/api`（与 `app/main.py` 挂载一致）

本功能**不新增 HTTP 路径**；通过注册新策略实例，下列既有接口的**响应内容**增加一项。

---

## 1. 策略列表（增量）

**`GET /api/strategies`**

### 响应 `items[]` 新增元素示例

```json
{
  "strategy_id": "zao_chen_shi_zi_xing",
  "name": "早晨十字星",
  "version": "v1.1.0",
  "short_description": "跌势末期三根K线（大阴—锤头—阳线）+历史高位过滤（不强制放量）；买入卖出同曙光初现。",
  "route_path": "/strategy/zao-chen-shi-zi-xing"
}
```

| 字段 | 说明 |
|------|------|
| `strategy_id` | 固定 `zao_chen_shi_zi_xing`，用于回测与执行接口 |
| `route_path` | 若未实现独立说明页，仍可先占位；前端菜单可选 |

### 错误

无变更（200）。

---

## 2. 策略详情

**`GET /api/strategies/{strategy_id}`**

当 `strategy_id=zao_chen_shi_zi_xing` 时，返回完整 `description`、`assumptions`、`risks`（由策略类 `describe()` 提供），结构同现有策略。

### 错误

| 状态码 | 场景 |
|--------|------|
| 404 | `strategy_id` 未注册 |

---

## 3. 策略执行（选股）

**`POST /api/strategies/{strategy_id}/execute`**

**`GET /api/strategies/{strategy_id}/latest`**

请求/响应模型不变；`strategy_id` 传入 `zao_chen_shi_zi_xing` 时，行为为：在 `as_of_date`（或请求体指定日期）执行与回测一致的判定，返回当日**买入**候选（若有）。

---

## 4. 回测

**`POST /api/backtest/run`**

请求体中：

```json
{
  "strategy_id": "zao_chen_shi_zi_xing",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

### 错误

| 状态码 | code | 场景 |
|--------|------|------|
| 404 | `STRATEGY_NOT_FOUND` | 策略未注册（不应在注册完成后出现） |

其余同 `specs/010-智能回测/contracts/backtest-api.md`。

---

## 5. 交易明细分页

**`GET /api/backtest/tasks/{task_id}/trades`**

单条记录中若策略为早晨十字星，`trigger_date` 为第三根阳线日；与 `specs/010` 契约中「触发日」说明一致，无需新字段。
