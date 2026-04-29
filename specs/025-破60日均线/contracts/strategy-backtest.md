# 契约说明：破 60 日均线策略与历史回测 API

**关联规格**：[spec.md](../spec.md)  
**说明**：本功能**不新增** HTTP 路径；通过**注册新策略**使既有接口「自动」支持。下列契约与 `specs/010-智能回测/contracts/backtest-api.md` **叠加**使用：仅增加**新** `strategy_id` 的合法取值与策略元数据内容。

---

## 1. 策略列表 `GET /api/strategies`

**行为**：注册完成后，响应 `items` 中增加一条（顺序以 `registry` 为准，实现时插在「60 日均线买入法（斜率）」附近或列表尾部均可，**须**在 `plan`/`tasks` 中写死一次避免漂移）。

**新增项字段约定**（结构同现有项）：

| 字段 | 值（约定） |
|------|------------|
| `strategy_id` | `ma60_five_day_break` |
| `name` | `破60日均线买入法`（或与 `describe().name` 一致） |
| `short_description` / `description` | 与规格一致：前 5 日收盘 < 当日 MA60、信号日收盘 > MA60、**次日开盘**买入、**±8%** 收盘价止损/止盈 |

**错误码**：无新增；未登录沿用全局 401。

---

## 2. 发起回测 `POST /api/backtest/run`

**请求体**（在既有 schema 上）：

| 字段 | 本策略约束 |
|------|------------|
| `strategy_id` | 必为 **`ma60_five_day_break`** |
| `start_date` / `end_date` / `position_amount` / `reserve_amount` | 与全局回测相同 |
| `symbols` | **可选**；若项目对非 `ma_golden_cross` 传 `symbols` 仍返回 `SYMBOLS_NOT_SUPPORTED`，则本策略**不传** `symbols`；若后期扩展白名单，再单独立项 |

**响应**：仍为 **202** + `task_id`；**不**新设状态码。

**业务错误**（与现有一致时）：`STRATEGY_NOT_FOUND`（`strategy_id` 拼写错误）、日期非法、`DATE_OUT_OF_RANGE` 等。

---

## 3. 回测任务查询与明细

与现有回测**相同**的 `GET` 任务列表、任务详情、交易列表路径与分页；本策略产出的 `backtest_trade` 行须满足 [data-model.md](../data-model.md) 中**触发日/买卖日/价格**语义。

---

## 4. 非范围

- **无**新 Admin 管理端接口、**无**新定时任务专用 HTTP；若后续为选股接入 `POST /api/strategies/{id}/execute`，在 **Phase 2** 任务中再对 `id=ma60_five_day_break` 补测。
