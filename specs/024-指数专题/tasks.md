---

description: "024-指数专题 实施任务清单"
---

# Tasks：指数专题

**Input**: `/specs/024-指数专题/` 下的 `plan.md`、`spec.md`、`data-model.md`、`contracts/index-api.md`  
**前置**: `plan.md`、`spec.md`  
**测试**: 规格未强制 TDD；以下仅在关键算法处列可选单测任务。

**组织方式**: 按「用户需求」US1～US4（与 `spec.md` 一致）拆分，便于分阶段验收。

## Phase 1：Setup（环境与约定）

**Purpose**: 固定实现边界，避免歧义。

- [x] T001 对照 `specs/024-指数专题/plan.md` 与 `contracts/index-api.md`，在后端路由设计中统一使用路由前缀 `/api/index` 与文档中的路径命名。

---

## Phase 2：Foundational（阻塞所有用户故事）

**Purpose**：数据库对象、模型、Tushare 封装与同步骨架、路由挂载。**完成前不得开始「可演示业务」之外的联调。**

**Checkpoint**：执行 DDL 后能创建表；模型可 import；`/api/index` 路由已挂载（可先返回占位）。

- [x] T002 编写 MySQL DDL `backend/scripts/add_index_tables.sql`，覆盖 `specs/024-指数专题/data-model.md` 中的 `index_basic`、`index_daily_bar`、`index_weekly_bar`、`index_monthly_bar`、`index_weight`（可选 `index_pe_percentile_snapshot` 可延后同文件注释块）。
- [x] T003 [P] 新增模型 `backend/app/models/index_basic.py`
- [x] T004 [P] 新增模型 `backend/app/models/index_daily_bar.py`
- [x] T005 [P] 新增模型 `backend/app/models/index_weekly_bar.py`
- [x] T006 [P] 新增模型 `backend/app/models/index_monthly_bar.py`
- [x] T007 [P] 新增模型 `backend/app/models/index_weight.py`
- [x] T008 在 `backend/app/models/__init__.py` 导出上述模型并保持一致命名。
- [x] T009 扩展 `backend/app/services/tushare_client.py`：封装 `index_basic`、`index_weekly`、`index_monthly`、`index_weight`（及错误重试与限量分段策略），与现有 `get_index_daily_range` 风格一致。
- [x] T010 新建 `backend/app/services/index_sync_service.py`（或 `index_sync/` 包）：实现 `index_basic` 全量/增量拉取与入库、`index_daily` 按 `ts_code` 分段 upsert（遵守单次行数上限）。
- [x] T011 新建 `backend/app/api/index.py`（Router 前缀 `/index`），注册占位 health 路由；在 `backend/app/main.py` 中 `include_router(..., prefix="/api")`。

---

## Phase 3：User Story 1 — 指数行情数据就绪（日/周/月 K）（Priority: P1）

**Goal**：指数 K 线与日频指标入库可查询；为列表、图表、模拟与回测提供数据源。

**Independent Test**：任选已同步的 `ts_code`，数据库中可按日/周/月查询 OHLCV；日线具备与个股对齐的衍生字段（均线/MACD 等与 `plan` 一致）。

### Implementation（US1）

- [x] T012 [US1] 在 `backend/app/services/index_sync_service.py` 中补齐 **周线、月线** 增量同步与回填分段逻辑。
- [x] T013 [US1] 实现日线指标填充：复用或抽取 `backend/app/services/` 下与 `stock_daily_bar` 相同的均线/MACD 计算逻辑，写入 `index_daily_bar`（含 `prev_close`、`pct_change` 等与 `plan` 对齐字段）。
- [x] T014 [US1] 为周/月线实现与个股一致的周期末端字段与指标更新流程（参照现有 `StockWeeklyBar`/`StockMonthlyBar` 管线命名与 job 触发习惯）。

**Checkpoint**：US1 完成后，仅用 DB/API 调试工具即可验证某指数的日/周/月序列非空。

---

## Phase 4：User Story 2 — 菜单「指数基金」与详情（Priority: P1）

**Goal**：`/api/index/screening`、`latest-date`、`composition`（含成分 + **指数 PE 百分位**）；前端专题页 + 抽屉详情 + 悬浮说明（`FR-007`/`FR-009`/`FR-010`）。

**Independent Test**：登录后打开「指数基金」页分页浏览；点开详情可见成分表、推理 PE 百分位及 meta；列表主表无成分嵌套。

### Implementation（US2）

- [x] T015 [US2] 新建 `backend/app/schemas/index.py`：`ScreeningResponse`、`CompositionResponse`（含 `index_pe_percentile`、`pe_percentile_meta`、`items[].pe_percentile`）与 `contracts/index-api.md` 对齐。
- [x] T016 [US2] 实现 `backend/app/services/index_screening_service.py`：分页列表、可选筛选、`data_date`/`latest-date`（对标 `screening_service.py` 习惯）。
- [x] T017 [US2] 实现 `backend/app/services/index_pe_percentile_service.py`：`spec.md`/`plan.md` 规定的加权重归一口径，关联 `stock_daily_bar.pe_percentile`。
- [x] T018 [US2] 在 `backend/app/api/index.py` 实现 `GET /screening`、`GET /screening/latest-date`、`GET /{ts_code}/composition`（鉴权 `get_current_user`，错误格式与全局一致）。
- [x] T019 [P] [US2] 新建 `frontend/src/api/index.ts` 封装上述接口。
- [x] T020 [US2] 新建 `frontend/src/views/IndexScreeningView.vue`：对标 `StockScreeningView.vue` 的表格/分页/周期切换；标题区 `el-tooltip` 能力说明（点位、仿真边界、PE 推理说明）；行操作打开抽屉展示成分与 PE。
- [x] T021 [US2] 在 `frontend/src/router/index.ts` 注册路由（如 `/index-fund`）；在 `frontend/src/views/Layout.vue` 增加二级菜单「指数基金」。

**Checkpoint**：US2 可单独演示完整专题浏览与详情（不依赖模拟交易）。

---

## Phase 5：User Story 3 — 历史模拟交易支持指数标的（Priority: P1）

**Goal**：会话内可买卖指数 `ts_code`；**T+1**；**不对指数调用个股涨跌停校验**；图表与持仓引用 `index_*_bar`。

**Independent Test**：创建会话 → 买入 `399300.SZ` → 下一交易日可卖 → 不受涨跌停价拦截。

### Implementation（US3）

- [x] T022 [US3] 重构 `backend/app/services/paper_trading_service.py`：抽象「日线来源」——个股 `StockDailyBar` vs 指数 `IndexDailyBar`；`buy`/`sell` 在指数为真时跳过 `_validate_price`；保留资金与 T+1。
- [x] T023 [US3] 更新 `paper_trading_service` 中图表、报价、持仓市值等所有读取 `StockDailyBar` 的路径，增加指数分支（含周/月切换若现有 UI 支持）。
- [x] T024 [US3] 扩展 `resolve`/搜索逻辑：支持 `index_basic` 名称与代码解析（与现有 `StockBasic` 查询并列或降级），返回前端可区分类型字段（若已有 schema 则扩展）。
- [x] T025 [US3] 更新 `frontend/src/views/PaperTradingSessionView.vue`（及相关子组件）：搜索与展示指数标的、仿真规则提示文案与个股区分。

**Checkpoint**：US3 完成后，在不启用回测的情况下可完整验证指数模拟交易闭环。

---

## Phase 6：User Story 4 — 历史回测支持指数标的（Priority: P1）

**Goal**：回测任务可选择指数标的；行情来自 `index_daily_bar`；个股专属策略字段缺失时明确报错或禁用。

**Independent Test**：选用支持指数数据的策略或最小回测路径，提交 `ts_code` 为指数的任务并生成摘要。

### Implementation（US4）

- [x] T026 [US4] 在 `backend/app/services/backtest/`（重点 `backtest_engine.py`、`portfolio_simulation.py`、`simulation_engine.py`）增加标的类型判定：若为指数则从 `index_daily_bar`（及所需区间）装载 Bar 序列。（实现：`backtest_context` + `ma_golden_cross` 限定标的分支读 `index_daily_bar`；其它策略仍为全市场个股逻辑。）
- [x] T027 [US4] 更新 `backend/app/api/backtest.py`（及回测任务 schema）：允许提交指数 `ts_code`，校验指数在 `index_basic` 且日期范围内有行情。（`RunBacktestRequest.symbols`；校验与 `data-range` 合并日历已落地。）
- [x] T028 [US4] 对依赖 `StockBasic`/财务/个股独有字段的策略：在策略执行前校验并返回可读错误；前端回测页增加指数选择时的提示（与 `spec` 一致）。（非均线金叉策略在填写 `symbols` 时返回 `SYMBOLS_NOT_SUPPORTED`；回测配置面板增加标的输入与 Tooltip。）

**Checkpoint**：US4 完成后，指数回测与个股回测可在同一入口提交（按规格约束策略可用性）。

---

## Phase 7：Polish & Cross-Cutting

**Purpose**：定时同步、CLI、文档与规格状态收尾。

- [x] T029 在 `backend/app/core/scheduler.py` 注册指数增量同步任务（建议交易日 17:05，与 `plan.md` 一致），失败日志与重试策略对齐现有股票任务。
- [x] T030 新建 `backend/app/scripts/sync_index.py`（或等价模块）：支持 `--mode incremental|backfill`、`--modules`、`--date` 区间，供运维手动补数。
- [x] T031 [P] 新增 `backend/tests/test_index_pe_percentile.py`：覆盖加权重归一、全缺失、单成分等边界（对应 `spec` SC-006 与 `plan` 公式）。
- [x] T032 将本功能交付范围与假设同步到 `specs/024-指数专题/spec.md`（状态、若有实现偏差则更新假设）；必要时补充 `docs/` 或 `plan.md` 中的运维说明。

---

## Dependencies & Execution Order

### Phase 依赖

- **Phase 1** → 无前置。
- **Phase 2** → 依赖 Phase 1；**阻塞** US1～US4。
- **Phase 3（US1）** → 依赖 Phase 2。
- **Phase 4（US2）** → 依赖 Phase 2；**数据内容依赖 US1 的同步结果**（可先 mock 少量数据联调前端）。
- **Phase 5（US3）** → 依赖 Phase 2；**强依赖 US1**（指数日线可用）。
- **Phase 6（US4）** → 依赖 Phase 2；**强依赖 US1**。
- **Phase 7** → 依赖核心功能可用（建议 US1～US2 完成后先做定时与脚本）。

### 用户故事依赖简图

```text
Phase2 ──► US1（数据）
              │
              ├──► US2（专题 UI/API）
              │
              ├──► US3（模拟交易）
              │
              └──► US4（回测）
```

### Parallel Opportunities

- **Phase 2**：T003～T007 模型文件可并行。
- **Phase 4**：T019 与 T016～T018 在后端契约稳定后可并行。
- **Phase 7**：T031 可与 T029、T030 并行。

---

## Parallel Example：Phase 2 模型

```bash
# 同时创建各模型文件（改完统一执行 T008 export）：
backend/app/models/index_basic.py
backend/app/models/index_daily_bar.py
backend/app/models/index_weekly_bar.py
backend/app/models/index_monthly_bar.py
backend/app/models/index_weight.py
```

---

## Implementation Strategy

### MVP（最小可演示）

1. 完成 **Phase 2** + **Phase 3（US1）** 日线同步与少量标的验证数据。  
2. 完成 **Phase 4（US2）** 列表 + 详情（含 PE 推理）。  
→ 即可演示「指数专题」主体价值。

### 增量交付

3. **US3** 指数模拟交易 → **US4** 指数回测。  
4. **Phase 7** 定时任务、脚本与测试加固。

---

## Task Summary

| 指标 | 数量 |
|------|------|
| 总任务数 | 32 |
| Phase 2 | 10 |
| US1 | 3 |
| US2 | 7 |
| US3 | 4 |
| US4 | 3 |
| Polish | 4 |
| 可并行任务（标记 [P]） | 6 |

**独立验收**：各 US 的 Independent Test 见各 Phase 标题下。

---

## Notes

- 任务描述中的路径均为仓库内相对路径根 `stock-assistant/`。
- 若 `check-prerequisites.sh` 要求功能分支而当前为 `main`，不影响本任务清单有效性；以 `specs/024-指数专题/` 为准。
