# Tasks：技术指标扩展

**Input**: `/specs/006-技术指标扩展/` 下 `plan.md`、`spec.md`、`data-model.md`、`contracts/`、`research.md`、`quickstart.md`  
**Prerequisites**: `plan.md`、`spec.md` 已就绪

**Tests**: 规格未强制 TDD；仅对纯函数层增加最小黄金样本测试（与 `plan.md` P0 一致）。

**Organization**: 按用户故事 **US1（P1）**、**US2（P2）** 分组，便于分阶段交付。

## Format: `[ID] [P?] [Story] Description`

- **[P]**：可并行（不同文件、无未完成依赖）
- **[US1]** / **[US2]**：对应 `spec.md` 中用户需求 1 / 2

---

## Phase 1: Setup（环境与依赖确认）

**Purpose**：确认实现依赖与字段清单，无新建仓库结构。

- [x] T001 确认 `backend/requirements.txt` 已包含 `pandas`（与 `specs/006-技术指标扩展/plan.md` 向量计算一致），无需则补齐版本约束

---

## Phase 2: Foundational（数据库与模型，阻塞所有用户故事）

**Purpose**：三张 K 线主表具备指标列，ORM 可读写。

**⚠️ 完成前不得开始指标计算与串联逻辑**

- [x] T002 新增 SQL 迁移脚本（建议 `backend/scripts/add_stock_indicator_columns.sql`）：为 `stock_daily_bar`、`stock_weekly_bar`、`stock_monthly_bar` 各增加 `ma5`、`ma10`、`ma20`、`ma60`、`macd_dif`、`macd_dea`、`macd_hist`（类型与 `specs/006-技术指标扩展/data-model.md` 一致）
- [x] T003 [P] 扩展 `backend/app/models/stock_daily_bar.py`：上述 7 列 `Mapped` 字段，`nullable=True`
- [x] T004 [P] 扩展 `backend/app/models/stock_weekly_bar.py`：上述 7 列 `Mapped` 字段，`nullable=True`
- [x] T005 [P] 扩展 `backend/app/models/stock_monthly_bar.py`：上述 7 列 `Mapped` 字段，`nullable=True`
- [x] T006 若 `backend/app/models/__init__.py` 需显式导出，同步更新导出列表（本期无需改 `__init__`，模型已在此前导出）

**Checkpoint**：迁移可在目标库执行；三模型字段与 `data-model.md` 一致

---

## Phase 3: User Story 1 - 各周期 K 线落库均线与 MACD（Priority: P1）🎯 MVP

**Goal**：按统一口径计算 SMA 与 MACD，写入日/周/月 bar 表；各周期仅基于该周期 `close` 序列。

**Independent Test**：测试库样本数据跑填充后，`SELECT` 抽检与参考计算一致（容许误差）；短历史标的对应列为 NULL。

### Implementation for User Story 1

- [x] T007 [US1] 新增 `backend/app/services/technical_indicator.py`：实现 SMA（5/10/20/60）、EMA、MACD（12/26/9）及 `macd_hist = 2*(dif-dea)`，口径锁定 `specs/006-技术指标扩展/data-model.md` 与 `research.md`
- [x] T008 [P] [US1] 新增 `backend/tests/test_technical_indicator.py`：黄金样本与边界（EMA 初值策略与 `research.md` 一致，避免与 pandas 默认 silently 漂移）
- [x] T009 [US1] 新增 `backend/app/services/stock_indicator_fill_service.py`：按 `timeframe`（`daily`/`weekly`/`monthly`）、按 `stock_code` 拉取有序 K 线，滑动窗口（建议 ≥120 根或按周期调整）重算并批量 **UPDATE** 对应表；`close` 为 NULL 行不伪造指标
- [x] T010 [US1] 修改 `backend/app/services/sync_task_runner.py`：在 `_run_module_by_type` 中 `daily`/`weekly`/`monthly` **成功返回后**调用 `stock_indicator_fill_service` 中对应周期填充（见 `specs/006-技术指标扩展/plan.md` 流程图）
- [x] T011 [US1] 修改 `backend/app/services/stock_sync_orchestrator.py`：在 `daily`/`weekly`/`monthly` 模块**成功完成后**调用同一套周期填充（与 `POST /api/admin/stock-sync` 手动全量路径一致，避免仅 auto 链有指标）

**Checkpoint**：定时 auto 链与手动 orchestrator 路径均能在行情成功后写入指标；三表互不混算序列

---

## Phase 4: User Story 2 - 增量与回填可运维（Priority: P2）

**Goal**：CLI 与 Admin HTTP 支持一次性补全/区间回填；失败可感知，成功部分不无故回滚。

**Independent Test**：`--limit` 小样本回填成功；故意制造单标的失败时日志/摘要可区分。

### Implementation for User Story 2

- [x] T012 [US2] 新增 `backend/app/scripts/fill_stock_indicators.py`（或项目约定之 `python -m app.scripts.fill_stock_indicators`）：支持 `incremental`/`backfill`、`timeframe`、日期区间、`limit`，复用 `stock_indicator_fill_service`
- [x] T013 [US2] 在 `backend/app/api/admin.py` 实现 `POST /api/admin/stock-indicators`：请求/响应与 `specs/006-技术指标扩展/contracts/admin-stock-indicators-api.md` 一致，鉴权与现有 admin 股票同步接口同级（`backend/app/main.py` 已挂载 `/api` 前缀则无需改入口）
- [x] T014 [US2] 指标填充失败时：结构化 `logging`；可选将摘要写入 `sync_job_run.extra_json`（或等价字段），便于区分「行情成功、指标失败」（见 `spec.md` 用户需求 2 验收场景 2）— **本期以日志为主**（`logger.exception`）

**Checkpoint**：运维可仅用 CLI 或 HTTP 完成历史补全；失败可追踪

---

## Phase 5: Polish & Cross-Cutting

**Purpose**：文档与规格一致，可按 `quickstart` 验收。

- [x] T015 [P] 更新 `docs/数据库设计.md`：`stock_daily_bar` / `stock_weekly_bar` / `stock_monthly_bar` 新增指标字段说明
- [x] T016 [P] 更新 `docs/定时任务说明.md`：日线/周线/月线任务在行情写入后附带指标计算；CLI 与 `POST /api/admin/stock-indicators` 手动补算说明
- [x] T017 按 `specs/006-技术指标扩展/quickstart.md` 执行一遍验证，修正文档中的命令/路径漂移

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** → **Phase 2** → **Phase 3 (US1)** → **Phase 4 (US2)** → **Phase 5**
- **US2** 依赖 **US1** 的 `stock_indicator_fill_service` 与 CLI/HTTP 复用逻辑

### User Story Dependencies

- **US1**：依赖 Phase 2 完成
- **US2**：依赖 US1 可调用填充服务

### Parallel Opportunities

- **Phase 2**：T003、T004、T005 可并行（不同 model 文件）
- **Phase 3**：T007 与 T008 可并行（先 T007 更易写 T008）；T003–T005 已并行
- **Phase 5**：T015、T016 可并行

### Parallel Example: Foundational

```text
T003 backend/app/models/stock_daily_bar.py
T004 backend/app/models/stock_weekly_bar.py
T005 backend/app/models/stock_monthly_bar.py
```

---

## Implementation Strategy

### MVP（仅 User Story 1）

1. Phase 1 + Phase 2  
2. Phase 3（T007–T011）  
3. **停止并验收**：样本抽检满足 `spec.md` SC-001 思路  

### Incremental Delivery

1. MVP 完成后 → Phase 4（运维入口）  
2. 最后 Phase 5 文档与 quickstart 闭环  

---

## Notes

- 本期**不包含**选股/筛选接口与前端（见 `spec.md`「本期不包含」）。
- 任务 ID 连续；完成后将 `[ ]` 改为 `[x]`。
