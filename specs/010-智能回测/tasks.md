# Tasks: 智能回测

**Input**: 设计文档来自 `specs/010-智能回测/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/backtest-api.md, research.md

**Organization**: 按用户场景分阶段，每个阶段可独立测试。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无依赖）
- **[Story]**: 所属用户场景（US1~US5）

---

## Phase 1: Setup（数据库与项目基础）

**Purpose**: 建表、ORM 模型、策略接口扩展——后续所有任务的前提。

- [X] T001 创建建表 SQL 脚本 `backend/scripts/add_backtest_tables.sql`，包含 `backtest_task` 和 `backtest_trade` 两张表（含 `market_temp_score`/`market_temp_level` 字段），按 `data-model.md` 中的 DDL
- [X] T002 [P] 创建 `backend/app/models/backtest_task.py`，SQLAlchemy 2.0 声明式模型（Mapped/mapped_column），字段对齐 `data-model.md` 中 `backtest_task` 表定义
- [X] T003 [P] 创建 `backend/app/models/backtest_trade.py`，SQLAlchemy 2.0 声明式模型，字段对齐 `data-model.md` 中 `backtest_trade` 表定义（含 `market_temp_score`、`market_temp_level`、`extra_json`）
- [X] T004 修改 `backend/app/models/__init__.py`，导入并注册 `BacktestTask`、`BacktestTrade` 到 `__all__`
- [X] T005 修改 `backend/app/services/strategy/strategy_base.py`，新增 `BacktestTrade`、`BacktestResult` 数据类，并在 `StockStrategy` Protocol 中新增 `backtest(*, start_date, end_date) -> BacktestResult` 方法签名

**Checkpoint**: 执行建表 SQL 后数据库中出现两张新表；新模型可导入无报错；策略接口扩展不影响现有 `execute()` 调用。

---

## Phase 2: Foundational（回测引擎与通用服务）

**Purpose**: 回测引擎核心逻辑、报告计算、Pydantic schema——所有用户场景的后端基础。

**⚠️ CRITICAL**: 用户场景阶段的任务依赖本阶段完成。

- [X] T006 创建 `backend/app/services/backtest/__init__.py`（包 docstring）
- [X] T007 [P] 创建 `backend/app/services/backtest/backtest_report.py`，实现 `calculate_report(trades)` 绩效指标计算（总交易/胜率/收益率/最大盈亏）与 `calculate_temp_level_stats(trades)` 按大盘温度级别分组统计，以及 `generate_conclusion(total_return, start_date, end_date)` 盈亏结论生成
- [X] T008 创建 `backend/app/services/backtest/backtest_engine.py`，实现 `run_backtest(db, task_id, strategy_id, start_date, end_date)` 主流程：调用策略 `backtest()` → `enrich_trades_with_temperature()` 补充大盘温度 → 持久化交易明细 → 计算报告 → 更新任务状态与指标；包含异常处理（失败时更新 task status=failed）
- [X] T009 [P] 创建 `backend/app/schemas/backtest.py`，定义所有 Pydantic 请求/响应模型：`RunBacktestRequest`、`RunBacktestResponse`、`BacktestTaskItem`、`BacktestTaskListResponse`、`BacktestTaskDetailResponse`（含 `report` 与 `temp_level_stats`）、`BacktestTradeItem`、`BacktestTradeListResponse`、`DataRangeResponse`，按 `contracts/backtest-api.md` 中的 JSON 结构

**Checkpoint**: `backtest_report.py` 可对模拟数据正确计算指标与温度分组统计；`backtest_engine.py` 逻辑链完整（可暂不实际调用策略，先验证流程框架）。

---

## Phase 3: US1 - 发起历史回测（Priority: P1）🎯 MVP

**Goal**: 用户选择策略与时间范围，系统后台异步执行回测，结果写入数据库。

**Independent Test**: `POST /api/backtest/run` 返回 202；等待数秒后查 `backtest_task` 表 status 变为 completed/incomplete；`backtest_trade` 表有交易记录。

- [X] T010 [US1] 修改 `backend/app/services/strategy/strategies/chong_gao_hui_luo.py`，实现 `backtest(*, start_date, end_date) -> BacktestResult` 方法：批量查询日期范围内全 A 股日线数据，逐日扫描触发条件（复用已有 `_select_stage1` 的判定逻辑），模拟 T+1 买入 / T+2 卖出，处理停牌/数据缺失跳过与 end_date 未平仓，返回 `BacktestResult`（含 `BacktestTrade` 列表与 `skipped_count`）
- [X] T011 [US1] 创建 `backend/app/api/backtest.py`，实现 `POST /api/backtest/run` 端点：参数校验（策略存在性、日期合法性、日期范围校验 via `stock_daily_bar` MIN/MAX）→ 创建 `backtest_task` 记录（status=running）→ 启动 `threading.Thread(daemon=True)` 调用 `run_backtest` → 返回 202；同时实现 `GET /api/backtest/data-range` 端点（查询 `stock_daily_bar` 的 MIN/MAX trade_date）
- [X] T012 [US1] 修改 `backend/app/main.py`，将 `backtest.router` 注册到 FastAPI app（prefix="/api"）

**Checkpoint**: 通过 curl 调用 `POST /api/backtest/run` 成功创建任务并后台执行；数据库中 `backtest_task` 状态正确变更；`backtest_trade` 有数据；`GET /api/backtest/data-range` 返回正确日期范围。

---

## Phase 4: US2 - 查看回测绩效报告（Priority: P1）

**Goal**: 用户查看回测完成后的绩效报告（总指标 + 盈亏结论 + 大盘温度分组统计）。

**Independent Test**: `GET /api/backtest/tasks/{task_id}` 返回包含 `report`（含 `temp_level_stats`）的完整响应；指标可通过交易明细逐笔验算。

- [X] T013 [US2] 在 `backend/app/api/backtest.py` 中实现 `GET /api/backtest/tasks/{task_id}` 端点：查询 `backtest_task` 记录，组装绩效报告响应（含 `total_trades`/`win_rate`/`total_return` 等指标 + `conclusion` + `temp_level_stats` + `assumptions`），按 `contracts/backtest-api.md` 中任务详情响应格式返回；补充策略名称（通过 `get_strategy().describe().name`）

**Checkpoint**: 通过 curl 调用 `GET /api/backtest/tasks/{task_id}` 返回完整报告，含温度分组统计数据。

---

## Phase 5: US3 - 查看回测交易明细（Priority: P1）

**Goal**: 用户逐笔查看回测中的每一笔模拟交易（含大盘温度字段），支持分页与类型筛选。

**Independent Test**: `GET /api/backtest/tasks/{task_id}/trades?page=1&page_size=10` 返回分页交易列表，每笔包含 `market_temp_level`/`market_temp_score`。

- [X] T014 [US3] 在 `backend/app/api/backtest.py` 中实现 `GET /api/backtest/tasks/{task_id}/trades` 端点：分页查询 `backtest_trade`，支持 `trade_type` 筛选（closed/unclosed），按 `contracts/backtest-api.md` 格式返回

**Checkpoint**: 通过 curl 调用交易明细接口，验证分页、筛选、温度字段均正确返回。

---

## Phase 6: US4 - 通过菜单进入回测模块（Priority: P2）

**Goal**: 用户通过侧边栏"智能回测 → 历史回测"菜单进入回测页面。

**Independent Test**: 登录后在侧边栏看到新菜单，点击可进入 `/backtest/history` 页面，刷新后仍可达。

- [X] T015 [P] [US4] 修改 `frontend/src/views/Layout.vue`，在侧边栏新增一级菜单"智能回测"（el-sub-menu），二级菜单"历史回测"（el-menu-item，index="/backtest/history"）；将 `backtest` 加入 `default-openeds`
- [X] T016 [P] [US4] 修改 `frontend/src/router/index.ts`，在 Layout 子路由中新增 `{ path: 'backtest/history', component: () => import('@/views/HistoryBacktestView.vue') }`
- [X] T017 [US4] 创建 `frontend/src/views/HistoryBacktestView.vue`，作为页面外壳，引入配置面板、任务列表、结果详情三个子组件区域（初始可用占位内容）

**Checkpoint**: 启动前端后，侧边栏出现"智能回测 → 历史回测"菜单项，点击可进入页面，URL 为 `/backtest/history`。

---

## Phase 7: US5 - 查看历史回测记录 + 前端完整页面（Priority: P2）

**Goal**: 前端完整回测页面——配置面板、任务列表（含轮询）、结果详情（绩效报告 + 温度分组统计 + 交易明细）。

**Independent Test**: 在前端页面中完成完整闭环：选策略 → 发起回测 → 列表刷新 → 点击查看 → 看到报告与明细。

- [X] T018 [P] [US5] 在 `backend/app/api/backtest.py` 中实现 `GET /api/backtest/tasks` 端点：分页查询 `backtest_task`（支持 `strategy_id` 筛选），按创建时间倒序返回，补充策略名称
- [X] T019 [P] [US5] 创建 `frontend/src/api/backtest.ts`，封装 5 个 API 调用函数：`runBacktest()`、`getBacktestTasks()`、`getBacktestTaskDetail()`、`getBacktestTrades()`、`getDataRange()`，复用现有 Axios 实例
- [X] T020 [US5] 创建 `frontend/src/components/BacktestConfigPanel.vue`：策略选择下拉（调用 `GET /api/strategies` 获取策略列表）、日期范围选择器（el-date-picker，范围约束由 `GET /api/backtest/data-range` 驱动）、"开始回测"按钮（调用 `POST /api/backtest/run`），含参数校验与 loading 状态
- [X] T021 [US5] 创建 `frontend/src/components/BacktestTaskList.vue`：调用 `GET /api/backtest/tasks` 展示回测记录列表（el-table）含策略名称/时间范围/状态/胜率/总收益/操作列；状态列用标签色区分（运行中=蓝/已完成=绿/未完成=橙/失败=红）；存在 running 任务时 5 秒轮询自动刷新；点击"查看"触发事件传递 task_id
- [X] T022 [US5] 创建 `frontend/src/components/BacktestResultDetail.vue`：接收 task_id prop → 调用 `GET /api/backtest/tasks/{task_id}` 展示绩效概览卡片（盈亏结论高亮、核心指标网格）+ 大盘温度分组统计表格（el-table：温度级别/交易数/胜率/平均收益）+ 调用 `GET /api/backtest/tasks/{task_id}/trades` 展示分页交易明细表格（含 `market_temp_level` 列）；空报告时显示"该时间范围内无符合策略条件的交易"
- [X] T023 [US5] 修改 `frontend/src/views/HistoryBacktestView.vue`，将占位内容替换为完整组件编排：顶部 `BacktestConfigPanel`（发起回测成功后刷新列表）→ 中部 `BacktestTaskList`（点击查看后展示详情）→ 底部 `BacktestResultDetail`（根据选中的 task_id 加载）

**Checkpoint**: 前端完成完整用户闭环：配置并发起回测 → 列表自动刷新 → 点击查看结果 → 查看绩效报告（含温度分组统计）与交易明细（分页、含温度列）。

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 完善、优化、验收。

- [X] T024 [P] 边界情况处理：零交易空报告展示、极短时间范围提示"样本量过少"、数据缺失跳过计数显示
- [X] T025 [P] 回测结果页增加悬浮提示（Tooltip），说明"本页能做什么"、"指标含义"、"口径说明"（按项目 `frontend-product-capability-hints` 规则）
- [X] T026 更新 `specs/010-智能回测/spec.md` 状态为"已实现"，同步 spec 与实际实现的任何差异
- [X] T027 按 `quickstart.md` 执行完整验证流程，确认所有验证清单项通过

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 无依赖，立即开始
- **Phase 2 (Foundational)**: 依赖 Phase 1 完成
- **Phase 3 (US1)**: 依赖 Phase 2 完成
- **Phase 4 (US2)**: 依赖 Phase 3 完成（需要已执行的回测数据）
- **Phase 5 (US3)**: 依赖 Phase 3 完成（需要已执行的回测数据）；与 Phase 4 可并行
- **Phase 6 (US4)**: 依赖 Phase 1 完成（仅需前端骨架）；与 Phase 2~5 可并行
- **Phase 7 (US5)**: 依赖 Phase 3~5 后端 API 完成 + Phase 6 页面骨架
- **Phase 8 (Polish)**: 依赖所有用户场景阶段完成

### User Story Dependencies

- **US1 (发起回测)**: 依赖 Foundational — 无跨场景依赖
- **US2 (绩效报告)**: 依赖 US1 产出的回测数据
- **US3 (交易明细)**: 依赖 US1 产出的回测数据；与 US2 可并行
- **US4 (菜单入口)**: 无后端依赖，可独立完成
- **US5 (回测记录+完整前端)**: 依赖 US1~US3 的 API + US4 的页面骨架

### Within Each User Story

- Models → Services → API endpoints → Frontend components
- 标记 [P] 的任务可并行（不同文件无依赖）

### Parallel Opportunities

- T002 + T003 可并行（两个独立 ORM 模型）
- T007 + T009 可并行（报告计算 vs Pydantic schema）
- T015 + T016 可并行（Layout.vue vs router）
- T018 + T019 可并行（后端列表 API vs 前端 API 模块）
- Phase 4 + Phase 5 可并行（报告 API vs 交易明细 API）
- Phase 6 可与 Phase 2~5 并行（纯前端骨架）

---

## Parallel Example: Phase 1

```bash
# 三个独立模型文件可并行：
Task T002: "创建 BacktestTask ORM 模型 in backend/app/models/backtest_task.py"
Task T003: "创建 BacktestTrade ORM 模型 in backend/app/models/backtest_trade.py"
Task T005: "扩展策略接口 in backend/app/services/strategy/strategy_base.py"
```

## Parallel Example: Phase 7

```bash
# 后端 API 和前端 API 模块可并行：
Task T018: "实现 GET /api/backtest/tasks 端点 in backend/app/api/backtest.py"
Task T019: "创建前端 API 封装 in frontend/src/api/backtest.ts"
```

---

## Implementation Strategy

### MVP First（US1 Only）

1. 完成 Phase 1: Setup（建表 + 模型）
2. 完成 Phase 2: Foundational（引擎 + 报告 + schema）
3. 完成 Phase 3: US1（冲高回落 backtest + API + 线程）
4. **STOP and VALIDATE**: 通过 curl 验证完整回测流程（发起→执行→数据落库）
5. 此时后端核心已可用

### Incremental Delivery

1. Setup + Foundational → 基础就绪
2. US1 → 回测可执行（curl 验证）→ MVP!
3. US2 + US3 → 报告与明细 API 就绪（curl 验证）
4. US4 → 前端页面骨架可导航
5. US5 → 前端完整闭环
6. Polish → 边界处理 + 提示 + 验收

---

## Notes

- [P] 任务 = 不同文件、无依赖，可并行执行
- [Story] 标签映射到 spec.md 中的用户需求编号
- 每个阶段有 Checkpoint，完成后可独立验证
- 策略接口扩展（T005）向后兼容，不影响现有 `execute()` 调用
- 冲高回落的 `backtest()` 实现（T010）是整个功能最复杂的单个任务，应优先完成
