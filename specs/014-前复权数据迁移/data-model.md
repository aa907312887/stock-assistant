# Phase 1 数据模型说明：前复权数据迁移

本文档描述**受影响的表**、清空约束、字段语义变更及表间关系；**不删除表结构**，仅行级清空或语义重定义。

---

## 1. 语义约定

| 表 | 变更说明 |
|----|----------|
| `stock_adj_factor` | 存储 Tushare [`adj_factor`](https://tushare.pro/document/2?doc_id=28) 返回的 **`adj_factor`**（按 `stock_code`+`trade_date` 唯一）；为日线前复权合成的权威因子序列，可按需用于本地重算或校验。 |
| `stock_daily_bar` | `open`/`high`/`low`/`close`/`prev_close` 及由价格推导的涨跌幅类字段，语义统一为 **未复权 `daily` 与 `stock_adj_factor` 按锚定公式合成的前复权价**；`daily_basic` 来源的换手率、市值、PE 等**非 OHLC** 字段仍为当日全市场指标，与复权无冲突。 |
| `stock_weekly_bar` / `stock_monthly_bar` | OHLC 为 **`stk_week_month_adj` 的 `*_qfq`**；`vol`/`amount` 等同接口原文。 |
| `stock_basic` | 规格要求**全表行删除后重拉** `stock_basic`（`stock_basic` 接口）；历史累计极值在 **`stock_daily_bar.cum_hist_*`**，清空日线后须跑历史极值全量任务。 |

---

## 2. 核心业务表（须清空行数据）

以下表在迁移窗口中执行 **`DELETE` 或 `TRUNCATE`**（无 FK 指向本表时优先 `TRUNCATE` 提速），**不** `DROP TABLE`。

| 实体 | 表名 | 主键/唯一键 | 说明 |
|------|------|----------------|------|
| 股票主档 | `stock_basic` | `id`，`code` UNIQUE | 清空后由 `stock_basic` 同步重灌 |
| 日线 | `stock_daily_bar` | `id`，`(stock_code, trade_date)` UNIQUE | 含指标列 ma/macd，清空后回灌 + `fill_indicators_*` |
| 日复权因子 | `stock_adj_factor` | `id`，`(stock_code, trade_date)` UNIQUE | 与日线一并清空；回灌时随日线同步写入 |
| 周线 | `stock_weekly_bar` | `id`，`(stock_code, trade_week_end)` UNIQUE | 同上 |
| 月线 | `stock_monthly_bar` | `id`，`(stock_code, trade_month_end)` UNIQUE | 同上 |
| 大盘温度 | `market_temperature_daily` | 见模型 | 清空后按指数日线重算 |
| 大盘温度 | `market_temperature_factor_daily` | 见模型 | 因子明细，随温度重算 |
| 指数行情副本 | `market_index_daily_quote` | 见模型 | 温度计算输入，清空后重拉 |
| 文案/规则（若存依赖旧行情的展示） | `market_temperature_copywriting`、`market_temperature_level_rule` | 视产品：规则类可保留；若与历史序列强绑定则按实施清单 |

**说明**：`market_temperature_*` 的具体字段以 `backend/app/models/` 为准；若某表仅为配置且与复权无关，可在实施清单中标注**保留**并写明理由。

---

## 3. 派生与任务类表（须清空或标记失效）

| 类型 | 表名 | 处理策略 |
|------|------|----------|
| 策略输出 | `strategy_selection_item`、`strategy_signal_event`、`strategy_execution_snapshot` | **建议清空**：选股结果依赖日/周/月前复权行情；迁移后由定时任务或手动重跑策略重算 |
| 同步审计 | `sync_job_run`、`sync_task` | **建议清空或归档**：避免旧 `batch_id` 与新数据混淆；若需审计可先将历史导出备份再 `TRUNCATE` |
| 回测 | `backtest_task`、`backtest_trade` | **默认不在本轮自动清空**（规格：分钟线/回测未默认纳入）；若业务要求与行情强一致，在 `plan` 执行清单中单列「可选：清空回测结果」 |

---

## 4. 日线表累计极值字段（013）

| 字段 | 类型（参考） | 说明 |
|------|----------------|------|
| `cum_hist_high` / `cum_hist_low` | `Numeric(12,4)` | 基于**前复权日线**按日递推的扩展最高/最低；**日常**随日线 upsert 写回；**全量纠偏**用 `python -m app.scripts.recompute_hist_extrema_full`。 |

清空日线后须执行上述全量 CLI（或等价全量）再依赖日线同步递推。

---

## 5. 索引与约束

迁移**不改变**现有 UNIQUE 与索引定义；重灌后由既有同步逻辑保证 `(stock_code, trade_date)` 等唯一性。

---

## 6. 可选元数据（实施阶段）

若需明确「本库已切换前复权」，可在 `plan` 阶段决定是否新增：

- 配置表键值，或  
- `stock_daily_bar.data_source` 仍用 `tushare`，在 `extra_json`（若将来扩展）中记录 `price_adjust=qfq`  

**默认**：不写新列也可，以代码与文档约定 **`daily`+`adj_factor` 合成前复权** 及周月 `stk_week_month_adj`/`qfq` 为准。
