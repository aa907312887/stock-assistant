# Tasks: 数据源重构

**Input**: Design documents from `specs/005-数据源重构/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Organization**: Tasks are grouped by user story. US1（历史日/周/月线与财报同步）完成后，US2（同步任务监控）才能展示完整任务结果。

**Format**: `- [ ] [TaskID] [P?] [Story?] Description with file path`

---

## Phase 1: Setup（共享基础设施）

**Purpose**: 同步本次重构的文档、DDL 入口与基础配置，确保后续实现有统一目标

- [ ] T001 更新 `docs/数据库设计.md`，将旧 `stock_daily_quote` / `stock_valuation_daily` 方案替换为 `stock_daily_bar`、`stock_weekly_bar`、`stock_monthly_bar` 与 `sync_job_run` 的最终口径
- [ ] T002 在 `backend/scripts/reset_and_init_v3.sql` 中创建新的删旧表并重建脚本骨架，明确旧表删除顺序与新表创建顺序
- [ ] T003 在 `backend/app/config.py` 中补充本次同步所需的配置项约定（如交易所日历、回灌模式默认参数），并与 `specs/005-数据源重构/quickstart.md` 保持一致

---

## Phase 2: Foundational（阻塞性前置）

**Purpose**: 先完成所有用户故事共同依赖的数据库模型、客户端封装与调度骨架

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 [P] 在 `backend/app/models/stock_daily_bar.py` 中新增历史日线主表 ORM，字段与 `specs/005-数据源重构/data-model.md` 一致
- [ ] T005 [P] 在 `backend/app/models/stock_weekly_bar.py` 中新增历史周线 ORM，并配置唯一键与索引
- [ ] T006 [P] 在 `backend/app/models/stock_monthly_bar.py` 中新增历史月线 ORM，并配置唯一键与索引
- [ ] T007 [P] 在 `backend/app/models/sync_job_run.py` 中新增同步任务日志 ORM，包含状态、模块行数和 `extra_json`
- [ ] T008 在 `backend/app/models/__init__.py` 中导出 `StockDailyBar`、`StockWeeklyBar`、`StockMonthlyBar`、`SyncJobRun`
- [ ] T009 在 `backend/app/services/tushare_client.py` 中扩展 `daily_basic`、`weekly`、`monthly`、`trade_cal` 封装，并统一错误处理与重试策略
- [ ] T010 在 `backend/app/core/scheduler.py` 中重构调度入口，保留 APScheduler 17:00 调度骨架并预留交易日判断与编排层调用

**Checkpoint**: 新模型、Tushare 新接口封装和调度骨架就绪，US1 / US2 可开始实现

---

## Phase 3: User Story 1 - 获取股票最重要的行情数据（Priority: P0） 🎯 MVP

**Goal**: 基于 Tushare 获取并落库历史日线、周线、月线与财报历史，替换旧数据源和旧表结构，并保持现有选股链路可以读取新日线主表。

**Independent Test**: 手动触发一次增量同步或执行一次历史回灌后，`stock_daily_bar`、`stock_weekly_bar`、`stock_monthly_bar`、`stock_financial_report` 中有数据，且 `GET /api/stock/screening` 能从新日线主表返回结果。

### Implementation for US1

- [ ] T011 [US1] 在 `backend/scripts/reset_and_init_v3.sql` 中实现旧表删除、新表创建与 `sync_job_run` 建表 SQL，并补充初始化说明
- [ ] T012 [US1] 在 `backend/app/services/stock_sync_orchestrator.py` 中实现同步编排层，负责 `batch_id`、模式分发、模块调用与任务状态汇总
- [ ] T013 [P] [US1] 在 `backend/app/services/stock_daily_bar_sync_service.py` 中实现 `daily + daily_basic` 合并写入 `stock_daily_bar` 的逻辑
- [ ] T014 [P] [US1] 在 `backend/app/services/stock_weekly_bar_sync_service.py` 中实现历史周线同步并写入 `stock_weekly_bar`
- [ ] T015 [P] [US1] 在 `backend/app/services/stock_monthly_bar_sync_service.py` 中实现历史月线同步并写入 `stock_monthly_bar`
- [ ] T016 [P] [US1] 在 `backend/app/services/stock_financial_sync_service.py` 中实现财报历史同步并写入 `stock_financial_report`
- [ ] T017 [US1] 在 `backend/app/scripts/sync_stock.py` 中改造成支持 `incremental` / `backfill`、模块选择与日期区间参数的管理命令
- [ ] T018 [US1] 在 `backend/app/api/admin.py` 中重构 `POST /api/admin/stock-sync`，支持请求体参数、返回 `batch_id`，并异步调用编排层
- [ ] T019 [US1] 在 `backend/app/core/scheduler.py` 与 `backend/app/main.py` 中接入交易日判断、17:00 增量任务和非交易日 `skipped` 记录
- [ ] T020 [US1] 在 `backend/app/services/screening_service.py` 中将选股查询从旧 `stock_daily_quote` 切换到 `stock_daily_bar`，并支持 PE / PE TTM / PB / 股息率筛选
- [ ] T021 [US1] 在 `backend/app/schemas/stock.py` 与 `backend/app/api/stock.py` 中更新选股接口参数和响应结构，使其符合 `specs/005-数据源重构/contracts/stock-screening-api.md`
- [ ] T022 [US1] 在 `frontend/src/api/stock.ts` 与 `frontend/src/views/StockScreeningView.vue` 中接入新的选股筛选字段和返回字段，确保页面继续基于最新历史日线工作

**Checkpoint**: US1 完成后，系统已完成数据源切换、旧表替换、17:00 同步、手动回灌以及选股读链路切换

---

## Phase 4: User Story 2 - 同步数据任务监控（Priority: P1）

**Goal**: 将每次同步任务的状态、模块结果、错误摘要和影响范围落库并通过页面展示，支持问题追踪。

**Independent Test**: 成功触发一次任务和一次失败任务后，可通过任务列表和任务详情接口查询到 `batch_id`、状态、模块级条数与错误摘要，前端监控页面能够正确展示。

### Implementation for US2

- [ ] T023 [US2] 在 `backend/app/services/stock_sync_orchestrator.py` 中补全 `sync_job_run` 的创建、更新、结束状态与模块级 `extra_json` 写入
- [ ] T024 [US2] 在 `backend/app/core/scheduled_job_logging.py` 中补充与 `sync_job_run` 配套的模块日志关键字和错误上下文约定
- [ ] T025 [US2] 在 `backend/app/schemas/` 下新增同步任务相关 schema（如 `sync_job.py`），定义列表、详情与触发响应结构
- [ ] T026 [US2] 在 `backend/app/api/admin.py` 中新增 `GET /api/admin/sync-jobs` 与 `GET /api/admin/sync-jobs/{batch_id}`，并对齐 `specs/005-数据源重构/contracts/sync-job-api.md`
- [ ] T027 [P] [US2] 在 `frontend/src/api/stock.ts` 或新增 `frontend/src/api/syncJob.ts` 中封装任务监控接口
- [ ] T028 [P] [US2] 在 `frontend/src/views/SyncJobMonitorView.vue` 中实现同步任务监控页面，展示状态、批次号、模块条数和错误摘要
- [ ] T029 [US2] 在 `frontend/src/router/index.ts` 与相关布局文件中注册同步任务监控页面入口，并保证仅管理入口可访问

**Checkpoint**: US2 完成后，任务监控具备后端落库、列表查询、详情查询和页面展示能力

---

## Phase 5: Polish & Cross-Cutting

**Purpose**: 清理旧引用、同步文档并完成端到端验证

- [ ] T030 在 `backend/app/services/stock_sync_service.py`、`backend/app/models/stock_valuation_daily.py`、`backend/app/models/stock_daily_quote.py` 及相关引用中清理或标记废弃旧同步/旧表逻辑，避免继续被新链路使用
- [ ] T031 在 `specs/005-数据源重构/quickstart.md` 与 `docs/Tushare股票接口接入文档.md` 中补充本次新增接口、回灌方式和 17:00 交易日同步说明
- [ ] T032 按 `specs/005-数据源重构/quickstart.md` 执行一轮数据库重建、增量同步、历史回灌、选股接口验证和任务监控验证，并将结果回写到 `specs/005-数据源重构/quickstart.md` 或同目录说明文档

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 无依赖，可立即开始
- **Phase 2 (Foundational)**: 依赖 Phase 1 完成，阻塞所有用户故事
- **Phase 3 (US1)**: 依赖 Phase 2 完成
- **Phase 4 (US2)**: 依赖 Phase 2 完成，但要看到真实任务结果，建议在 US1 主链路打通后完成
- **Phase 5 (Polish)**: 依赖 US1、US2 完成

### User Story Dependencies

- **US1（历史行情与财报同步）**: 无其他用户故事依赖，是 MVP
- **US2（同步任务监控）**: 依赖 US1 能产生真实同步批次与模块结果，才能完整验证监控效果

### Parallel Opportunities

- T004、T005、T006、T007 可并行（不同 ORM 文件）
- T013、T014、T015、T016 可并行（不同同步服务文件）
- T027、T028 可并行（前端 API 与页面文件不同）

---

## Parallel Example: User Story 1

```bash
# 并行创建本期新模型
Task: "在 backend/app/models/stock_daily_bar.py 中新增历史日线主表 ORM"
Task: "在 backend/app/models/stock_weekly_bar.py 中新增历史周线 ORM"
Task: "在 backend/app/models/stock_monthly_bar.py 中新增历史月线 ORM"
Task: "在 backend/app/models/sync_job_run.py 中新增同步任务日志 ORM"

# 并行实现各同步子服务
Task: "在 backend/app/services/stock_daily_bar_sync_service.py 中实现历史日线同步"
Task: "在 backend/app/services/stock_weekly_bar_sync_service.py 中实现历史周线同步"
Task: "在 backend/app/services/stock_monthly_bar_sync_service.py 中实现历史月线同步"
Task: "在 backend/app/services/stock_financial_sync_service.py 中实现财报历史同步"
```

---

## Implementation Strategy

### MVP First（建议先完成 US1）

1. 完成 Phase 1：Setup
2. 完成 Phase 2：Foundational
3. 完成 Phase 3：US1
4. **STOP and VALIDATE**：确认旧表已可被新结构替代，且选股接口能读取新日线主表

### Incremental Delivery

1. 先完成数据库重建与同步主链路
2. 再完成选股接口与前端读链路切换
3. 最后补任务监控接口与页面
4. 每个阶段都可独立验证，不需要等全部完成后再联调

### Parallel Team Strategy

1. 一人先完成 Phase 1 + Phase 2
2. 之后可并行：
   - 开发 A：US1 的数据库与同步服务
   - 开发 B：US1 的选股接口与前端读链路
   - 开发 C：US2 的监控 API 与页面

---

## Notes

- 所有任务均包含明确文件路径，可直接开始实现
- `[P]` 表示不同文件、依赖较少、适合并行
- `[US1]` / `[US2]` 用于追踪任务归属
- Spec 未要求 TDD，因此未强制生成测试先行任务；验证工作统一放在 Quickstart 与收尾阶段
