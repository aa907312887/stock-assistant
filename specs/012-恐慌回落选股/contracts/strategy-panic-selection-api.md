# 接口契约：策略选股 API 扩展（恐慌回落页依赖）

**基础路径前缀**：`/api`（与现有 FastAPI 挂载一致）  
**鉴权**：与现有需登录接口一致（JWT / 会话，以项目当前 `strategies` 路由配置为准）。

## 1. 复用接口一览

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/strategies` | 列表中含 `panic_pullback`，`route_path` 供前端路由对齐 |
| GET | `/strategies/{strategy_id}` | `strategy_id=panic_pullback` 拉取说明、假设、风险 |
| POST | `/strategies/{strategy_id}/execute` | 手动执行选股并落库 |
| GET | `/strategies/{strategy_id}/latest` | 只读最新已落库结果 |

**定时执行**：与「冲高回落战法」相同，由 `backend/app/core/scheduler.py` 在**交易日 17:20（Asia/Shanghai）**调用与 `POST .../execute` 相同的 `execute_strategy(..., strategy_id=panic_pullback, as_of_date=today)`，不经过 HTTP。

## 2. 请求约定

### POST `/strategies/panic_pullback/execute`

**Content-Type**：`application/json`

**Body**（`ExecuteStrategyRequest`，可选）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `as_of_date` | `string`（ISO 日期 `YYYY-MM-DD`） | 否 | 不传则使用数据库**日线**最大 `trade_date` |

### GET `/strategies/panic_pullback/latest`

**Query**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `as_of_date` | `string` | 否 | 指定则返回该截止日对应快照；不传则按 `as_of_date` 降序取最新一条 |

## 3. 响应结构（在现有基础上扩展）

### 3.1 `ExecutionSnapshot`（`execution`）

与现有字段一致，至少包含：

- `execution_id`, `strategy_id`, `strategy_version`, `market`, `as_of_date`, `timeframe`, `assumptions`

### 3.2 `StrategySelectionItem`（`items[]` 元素）

在现有字段基础上**必须**增加：

| 字段 | 类型 | 说明 |
|------|------|------|
| `exchange` | `string \| null` | 交易所：`SSE` / `SZSE` / `BSE`，来自 `stock_basic.exchange` |
| `market` | `string \| null` | 板块：主板/创业板/科创板/北交所等，来自 `stock_basic.market` |

保留字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `stock_code` | `string` | 证券代码 |
| `stock_name` | `string \| null` | 名称 |
| `exchange_type` | `string \| null` | **兼容字段**；新前端筛选以 `exchange`+`market` 为准 |
| `trigger_date` | `string`（日期） | 触发日 |
| `summary` | `object` | 策略指标；可含 `return_rate`、`sell_date` 等（若策略写入） |

### 3.3 `signals[]`

结构不变：`stock_code`, `event_date`, `event_type`, `payload`。

## 4. 错误约定

与现有 `strategies` 路由一致，**HTTP 状态码 + `detail` 对象**：

| HTTP | `detail.code` | 场景 |
|------|----------------|------|
| 404 | `NOT_FOUND` | 策略不存在；或 `latest` 无落库结果 |
| 409 | `DATA_NOT_READY` | 日线无可用截止日（如库为空） |
| 500 | `INTERNAL_ERROR` | 未捕获异常 |

**Body 形状**（示例）：

```json
{
  "detail": {
    "code": "DATA_NOT_READY",
    "message": "日线数据为空，无法执行策略"
  }
}
```

前端应优先展示 `detail.message`。

## 5. 前端筛选（无新 HTTP 接口）

- 筛选逻辑：浏览器端对**本次响应的 `items` 全量**应用条件。
- **交易所**：多选值集合 \(E\)；若为空则不过滤；否则保留 `item.exchange ∈ E`。
- **板块**：多选值集合 \(M\)；若为空则不过滤；否则若包含约定字面量 **`__EMPTY__`**，则保留 `market` 为空或缺失的条目 **或** `market ∈ M \ { __EMPTY__ }`。
- **组合**：同时选交易所与板块时，两条规则 **AND**。

（与回测 API 对 `markets` 的 `__EMPTY__` 语义对齐。）

## 6. 兼容性说明

- 扩展 `StrategySelectionItem` 后，旧页面（冲高回落）应仍能解析响应（新增字段忽略即可）。
- OpenAPI 随 `backend` Pydantic 模型自动生成更新，无需单独维护 YAML 亦可；若团队维护独立 openapi 文件，需同步增加 `exchange`、`market`。
