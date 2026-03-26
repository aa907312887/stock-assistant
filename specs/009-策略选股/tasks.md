# Tasks: 策略选股（冲高回落战法）

**Input**: Design documents from `specs/009-策略选股/`  
**Prerequisites**: `plan.md`（必需）, `spec.md`（必需）, `research.md`, `data-model.md`, `contracts/strategy-selection.openapi.yaml`, `quickstart.md`

**Tests**: 本期规格未要求 TDD/测试优先，因此不强制生成测试任务；如后续需要，可在实现阶段补充接口/服务层测试。

**Organization**: 任务按用户需求（US1～US4）组织，确保每个用户需求可独立验收与交付。

## Phase 1: Setup（共享基础）

- [x] T001 新增策略相关注释规范文件 `.cursor/rules/strategy-class-documentation.mdc`
- [x] T002 创建策略选股数据库建表脚本 `backend/scripts/add_strategy_selection_tables.sql`（包含 execution_snapshot/selection_item/signal_event）
- [x] T003 [P] 更新后端模型导出 `backend/app/models/__init__.py`（引入新增策略相关模型）

---

## Phase 2: Foundational（阻塞性基础能力）

- [x] T004 实现策略执行快照模型 `backend/app/models/strategy_execution_snapshot.py`
- [x] T005 [P] 实现策略候选明细模型 `backend/app/models/strategy_selection_item.py`
- [x] T006 [P] 实现策略信号事件模型 `backend/app/models/strategy_signal_event.py`
- [x] T007 [P] 实现策略接口与注册表 `backend/app/services/strategy/strategy_base.py`、`backend/app/services/strategy/registry.py`
- [x] T008 实现冲高回落战法策略类 `backend/app/services/strategy/strategies/chong_gao_hui_luo.py`（按注释规范写清口径与边界）
- [x] T009 实现策略执行服务 `backend/app/services/strategy/strategy_execute_service.py`（写入快照/候选/事件；支持 as_of_date 默认最新交易日）
- [x] T010 [P] 定义后端请求/响应 schema `backend/app/schemas/strategy.py`（对齐 `contracts/strategy-selection.openapi.yaml`）
- [x] T011 实现后端路由 `backend/app/api/strategies.py`（GET /strategies、GET /strategies/{id}、POST /strategies/{id}/execute）
- [x] T012 在 `backend/app/main.py` 注册策略路由（`app.include_router(..., prefix="/api")`）
- [x] T013 在 `backend/app/core/scheduler.py` 增加定时任务 `_job_strategy_chong_gao_hui_luo_daily` 并在 `start_scheduler()` 注册（交易日 17:20；跳过非交易日/数据未就绪）
- [ ] T014 [P] 在 `backend/app/api/admin.py` 或新增 admin 路由中提供手动触发接口（如需管理员鉴权），并说明与页面按钮接口的权限差异（若不需要管理员则跳过）

**Checkpoint**：后端可通过 `curl` 完成列表/详情/执行，且能看到三张表写入记录；定时任务在日志中可见执行/跳过信息。

---

## Phase 3: User Story 1（P1）- 选择并执行内置策略（MVP）

**Goal**：用户进入冲高回落战法页面，点击按钮即可筛出“今日符合冲高回落”的股票。

**Independent Test**：
- `POST /api/strategies/chong_gao_hui_luo/execute` 返回 execution + items + signals
- DB 中产生 1 条 execution_snapshot、N 条 selection_item、M 条 signal_event

- [x] T015 [US1] 前端新增策略 API 封装 `frontend/src/api/strategies.ts`（list/get/execute）
- [x] T016 [US1] 新增冲高回落战法页面 `frontend/src/views/ChongGaoHuiLuoView.vue`（说明 + 执行按钮 + 结果表）
- [x] T017 [US1] 在路由中注册页面 `frontend/src/router/index.ts`（/strategy/chong-gao-hui-luo）
- [x] T018 [US1] 在侧边栏菜单中增加入口 `frontend/src/views/Layout.vue`（一级“策略选股”/二级“冲高回落战法”）

---

## Phase 4: User Story 2（P1）- 通过菜单进入策略页面

**Goal**：用户通过菜单可到达策略页面，入口清晰。

**Independent Test**：
- 登录后侧边栏出现“策略选股”
- 点击“冲高回落战法”进入页面且路由高亮正确

- [ ] T019 [US2] 调整菜单默认展开项 `frontend/src/views/Layout.vue`（新增子菜单 index，确保刷新后展开/高亮正常）
- [ ] T020 [US2] 页面文案与口径提示完善 `frontend/src/views/ChongGaoHuiLuoView.vue`（无分时数据说明、阈值说明）

---

## Phase 5: User Story 3（P1）- 自动与手动执行冲高回落筛选

**Goal**：每天定时任务自动生成“今日结果”；页面按钮支持随时手动刷新。

**Independent Test**：
- 手动触发：按钮调用 execute 接口成功
- 自动触发：到点后日志出现执行记录，且 DB 写入新的 execution_snapshot

- [ ] T021 [US3] 完善定时任务跳过逻辑 `backend/app/core/scheduler.py`（非交易日/数据未就绪/重复执行当天结果的处理策略）
- [ ] T022 [US3] 页面展示“本次结果生成时间/截止日期/策略版本” `frontend/src/views/ChongGaoHuiLuoView.vue`

---

## Phase 6: User Story 4（P2）- 为未来回测保留可追溯的策略执行记录

**Goal**：任何一次执行都能回顾“操作现场”（版本、口径、触发/买入/卖出等事件与摘要）。

**Independent Test**：
- execution_snapshot.assumptions_json 与 signals.payload 能复述关键口径（大涨/回落/低开等）
- 同一 as_of_date 重复执行：要么复用同一 execution（幂等），要么生成新 execution 并能对比（策略需明确策略）

- [ ] T023 [US4] 在执行服务中补全 assumptions_json 与 params_json `backend/app/services/strategy/strategy_execute_service.py`
- [ ] T024 [US4] 定义并落库信号事件 payload 结构（trigger/entry/exit/filter）`backend/app/services/strategy/strategies/chong_gao_hui_luo.py`
- [ ] T025 [US4] 页面增加“查看执行详情/复制执行信息”能力 `frontend/src/views/ChongGaoHuiLuoView.vue`

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T026 [P] 同步更新接口契约（如实现细节有调整）`specs/009-策略选股/contracts/strategy-selection.openapi.yaml`
- [ ] T027 [P] 更新快速开始验证步骤与常见问题 `specs/009-策略选股/quickstart.md`
- [ ] T028 Run `specs/009-策略选股/quickstart.md` 全链路自测并记录结果（在 quickstart.md 末尾补一段验证记录）

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1 → Phase 2 → Phase 3（MVP）是最小闭环
- Phase 4/5 可在 Phase 3 后并行推进
- Phase 6 依赖 Phase 2 中“落库与事件结构”已完成

### User Story Dependencies

- **US1（P1）**：依赖 Phase 2 后端基础与策略实现
- **US2（P1）**：依赖 US1 路由/页面存在，但可与 US1 前端实现交叉推进
- **US3（P1）**：依赖 Phase 2 的定时任务与 execute 接口
- **US4（P2）**：依赖 Phase 2 的快照/事件/候选落库；可在后端稳定后推进

### Parallel Opportunities

- [P] 任务可并行：模型文件、schema 文件、前端 API 封装与页面开发（在接口约定稳定后）

