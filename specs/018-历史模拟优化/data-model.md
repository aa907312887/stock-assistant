# 数据模型：历史模拟优化

## 1. 变更概述

在保持 `simulation_task` 基本结构不变的前提下，扩展 `simulation_trade` 存储**买入日大盘温度**，以支持与 `backtest_trade` 一致的筛选与统计；任务级可选扩展 `assumptions_json` 内分组统计字段。

---

## 2. 表：`simulation_trade`（变更）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `market_temp_score` | `DECIMAL(5,2)` | 可空 | 买入日大盘温度分数，与 `market_temperature_daily` 对齐 |
| `market_temp_level` | `VARCHAR(16)` | 可空 | 买入日温度级别（与回测同一套枚举/文案） |

**索引建议**（与 `backtest_trade` 对齐，利于按任务筛选）：

- `INDEX idx_sim_trade_temp (task_id, market_temp_level)`

**迁移**：新建 SQL 脚本（或 Alembic）`ALTER TABLE simulation_trade ADD COLUMN ...`，对已有行两列均为 `NULL`。

---

## 3. 表：`simulation_task`（逻辑扩展，非必须改列）

| 位置 | 内容 |
|------|------|
| `assumptions_json` | 可选新增键：`temp_level_stats`、`exchange_stats`、`market_stats`（结构与回测任务完成时写入的 JSON 片段一致，便于前端复用）；以及既有 `conclusion`、`skip_reasons` 等保留 |

无新增必填列；若希望任务列表展示「筛选前全量分组」也可仅依赖 `assumptions_json`。

---

## 4. 实体关系（不变）

- `simulation_task.task_id` 1:N `simulation_trade.task_id`
- 温度维度**不**冗余存储日表主键，以 `buy_date` 关联逻辑在入库时已解析为分数与级别

---

## 5. 校验规则

- 写入 `simulation_trade` 时：若 `MarketTemperatureDaily` 中无对应 `buy_date`，则 `market_temp_score`、`market_temp_level` 均为 `NULL`；筛选时与回测对「缺失温度」的处理一致（不参与具体级别匹配，或归入产品约定的「未知」档）。
- `trade_type` 仍为 `closed` / `unclosed`；模拟侧不产生 `not_traded`。

---

## 6. 与 `backtest_trade` 的对齐字段

以下字段两表业务语义一致，便于共用筛选与指标函数：

- `buy_date`、`return_rate`、`trade_type`、`exchange`、`market`
- `market_temp_score`、`market_temp_level`

回测独有字段（如 `trigger_date`、`user_decision`）不在模拟表强制同步。
