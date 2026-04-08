# Tasks: 历史模拟优化

**Input**: 设计文档来自 `specs/018-历史模拟优化/`  
**Prerequisites**: plan.md、spec.md、data-model.md、contracts/simulation-analysis-api.md、research.md

**Organization**: 先数据库与共用筛选基础，再模拟引擎落库与任务汇总，再 HTTP 与前端；与回测共用的逻辑抽取完成后再改 `backtest.py`，避免双份条件长期分叉。

**Format**: `- [ ] [TaskID] [P?] [Story?] Description with file path`

---

## Phase 1: Setup（数据库与模型）

**Purpose**: `simulation_trade` 具备温度列，ORM 与库表一致。

- [x] T001 在 `backend/scripts/` 新增迁移 SQL（如 `add_simulation_trade_temperature.sql`）：为 `simulation_trade` 增加 `market_temp_score`（DECIMAL(5,2) 可空）、`market_temp_level`（VARCHAR(16) 可空），并增加索引 `idx_sim_trade_temp (task_id, market_temp_level)`；与 `data-model.md` 一致
- [x] T002 更新 `backend/app/models/simulation_trade.py`：映射上述两列；若项目要求同步 `docs/数据库设计.md`，在文档中补充两字段说明

---

## Phase 2: Foundational（共用筛选与指标）

**Purpose**: 回测与历史模拟共用同一套维度筛选与指标计算，路由层保持薄封装。

**Independent Test**: 对同一组内存构造的「假 ORM 行」或测试夹具，筛选与指标结果与当前 `backtest.api` 行为一致（可与重构前输出对比）。

- [x] T003 新建 `backend/app/services/trade_query_metrics.py`（或 plan 拟定同名）：从 `backend/app/api/backtest.py` 抽出 `_apply_trade_filters`、`_calculate_metrics_from_rows` 的逻辑，支持对 **BacktestTrade** 与 **SimulationTrade** 两类 Model 的 Query 应用相同条件（`trade_type`、`market_temp_levels`、`markets`、`exchanges`、`buy_year`）；导出 `apply_trade_dimension_filters`、`calculate_metrics_from_trade_rows`、`yearly_aggregate_from_rows`（分年聚合逻辑与现有 `yearly-analysis` 一致）
- [x] T004 修改 `backend/app/api/backtest.py`：改为调用 `trade_query_metrics` 中函数，删除或缩减内部重复实现，保持既有路由路径与响应不变（回归：现有回测接口行为不变）

**Checkpoint**: 回测相关接口仍通过手测或现有用例；新模块无循环依赖。

---

## Phase 3: User Story 1 - 模拟引擎补齐温度与任务分组（P1）

**Goal**: 新发起的模拟任务在落库明细中带买入日温度；任务完成时 `assumptions_json` 含温度/交易所/板块分组摘要（键名与回测任务详情对齐）。

**Independent Test**: 跑一次历史模拟，数据库中 `simulation_trade` 新行 `market_temp_level` 有值（在 `market_temperature_daily` 覆盖的买入日上）；`GET /simulation/tasks/{id}` 返回的 `assumptions` 中含分组统计结构（与回测同类字段一致）。

### Implementation for US1

- [x] T005 [US1] 修改 `backend/app/services/backtest/simulation_engine.py`：在 `enrich_trades_with_stock_dimension` **之前**调用 `enrich_trades_with_temperature`；写入 `SimulationTradeModel` 时填充 `market_temp_score`、`market_temp_level`；任务成功结束时调用 `backtest_report.calculate_temp_level_stats` / `calculate_exchange_stats` / `calculate_market_stats`（入参为已 enrich 的 `BacktestTrade` 列表），将结果合并入 `task.assumptions_json`（键名与 `backtest_engine` 写入的 `assumptions_base` 一致）

**Checkpoint**: US1 完成——新模拟任务明细与任务级 JSON 满足 spec FR-006、FR-007。

---

## Phase 4: User Story 2 - 模拟分析 API（P1）

**Goal**: 交易明细支持温度、买入年筛选；提供 `filtered-report` 与 `yearly-analysis`，契约见 `contracts/simulation-analysis-api.md`。

**Independent Test**: 按 `quickstart.md` 用 curl/浏览器调通四个接口；筛选后 `metrics` 与明细手算一致。

### Implementation for US2

- [x] T006 [US2] 更新 `backend/app/schemas/simulation.py`：`SimulationTradeItem` 增加 `market_temp_score`、`market_temp_level`；为 `filtered-report` / `yearly-analysis` 复用或别名导出 `schemas/backtest.py` 中已有 `BacktestFilteredReportResponse`、`BacktestYearlyAnalysisResponse`（或等价字段集）
- [x] T007 [US2] 修改 `backend/app/api/simulation.py`：`GET .../trades` 增加 Query `market_temp_levels`、`year`（及兼容旧参若有），使用 `apply_trade_dimension_filters` 作用于 `SimulationTradeModel`；`_row_to_trade_item` 返回温度字段
- [x] T008 [US2] 在 `backend/app/api/simulation.py` 新增 `GET /tasks/{task_id}/filtered-report`、`GET /tasks/{task_id}/yearly-analysis`，参数与回测同名接口一致；内部查询 `SimulationTradeModel` + `calculate_metrics_from_trade_rows` / 分年聚合；404 约定与现有一致

**Checkpoint**: US2 完成——后端与 `simulation-analysis-api.md` 一致。

---

## Phase 5: User Story 3 - 前端结果页与配置提示（P1/P2）

**Goal**: 结果页具备温度、交易所、板块、年份筛选，展示筛选后指标与分年表；配置区 Tooltip 说明与回测差异。

**Independent Test**: 完成一次模拟后，在详情页切换筛选，表格与汇总联动；文案可见。

### Implementation for US3

- [x] T009 [US3] 更新 `frontend/src/api/simulation.ts`：扩展 `SimulationTradeItem` 与 `getSimulationTrades` 参数；新增 `getSimulationFilteredReport`、`getSimulationYearlyAnalysis`（类型可与 `backtest` 复用或本地重复定义与后端一致）
- [x] T010 [US3] 更新 `frontend/src/components/SimulationResultDetail.vue`：筛选区增加大盘温度多选、买入年份；表格增加温度列；增加「筛选后指标」与「分年度分析」区块（交互与数据加载顺序对齐 `HistoryBacktestView` 或项目现有回测详情页模式）；从全量明细拉选项时与回测一致处理 `__EMPTY__` 空板块
- [x] T011 [P] [US3] 更新 `frontend/src/components/SimulationConfigPanel.vue`：在现有 Tooltip 上补充「历史模拟不进行资金仿真，统计全部符合条件的闭仓交易；与历史回测的仓位仿真可能笔数不同」（简短，符合产品能力提示规范）

**Checkpoint**: US3 完成——满足 spec FR-001、FR-002、FR-004 的前端部分。

---

## Phase 6: Polish & Cross-Cutting

**Purpose**: 可选回填脚本、轻量测试、规格状态同步。

- [x] T012（可选）在 `backend/scripts/` 提供旧 `simulation_trade` 行温度回填脚本或说明：按 `task_id` + `buy_date` 联表 `market_temperature_daily` 更新 NULL 行，非 P1 阻塞
- [x] T013 在 `backend/tests/` 为 `trade_query_metrics` 增加 1～2 条单元测试：筛选 + 指标与分年聚合边界（空集、仅 unclosed）
- [x] T014 按 `quickstart.md` 执行端到端验证；若有偏差，修正实现或更新 `quickstart.md`
- [x] T015 将 `specs/018-历史模拟优化/spec.md` 中**状态**更新为「已实现」或等价表述（验收通过后）

---

## Dependencies（执行顺序）

```text
Phase 1 (T001–T002) → Phase 2 (T003–T004) → Phase 3 (T005) → Phase 4 (T006–T008) → Phase 5 (T009–T011) → Phase 6 (T012–T015)
```

T003/T004 可与 T001/T002 并行启动，但 **T005 依赖 T001、T002、T003**；**T007–T008 依赖 T003、T006**；**T009 依赖 T008**。

---

## Parallel opportunities

- 前端 T009 可与后端 T006–T008 在契约冻结后并行（先对齐 TypeScript 类型与路径）。
- T012 可与 Phase 5 并行，由不同人处理。
