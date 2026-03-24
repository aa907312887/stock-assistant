# Tasks：个人持仓（个人服务）

**Input**: `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/specs/007-个人持仓/` 下 `plan.md`、`spec.md`、`data-model.md`、`contracts/personal-portfolio-api.md`、`ui-ux.md`、`research.md`、`quickstart.md`

**Prerequisites**: 已阅读 `plan.md`；用户故事优先级见 `spec.md`（US1 P1 … US5 P5）。

**Tests**: 规格未强制 TDD，本列表**不包含**独立测试任务；可在实现后按需补 `pytest`。

## Format: `[ID] [P?] [Story] Description`

- **[P]**：可并行（不同文件、无未完成依赖）
- **[Story]**：仅用户故事阶段任务使用 `[US1]`…`[US5]`

---

## Phase 1: Setup（共享准备）

**Purpose**：落地前目录与约定，避免遗漏上传路径等。

- [x] T001 在仓库中确认 `backend/uploads/portfolio/` 目录策略：新增 `backend/uploads/portfolio/.gitkeep`（或等价说明），并在 `backend/.gitignore` 中忽略 `uploads/portfolio/**` 下实际文件、保留目录占位（路径以 `plan.md` 为准）

---

## Phase 2: Foundational（阻塞所有用户故事）

**Purpose**：数据库表、ORM 模型、核心服务与路由挂载；**完成前不得开始各 Story 的端到端联调**。

**⚠️ CRITICAL**：本阶段完成后，US1～US5 才能按序或分模块实现。

- [x] T002 编写并保存建表 SQL：`backend/scripts/add_portfolio_tables.sql`，字段与索引对齐 `specs/007-个人持仓/data-model.md`（`portfolio_trade`、`portfolio_operation`、`portfolio_trade_image`）
- [x] T003 [P] 新增 SQLAlchemy 模型 `PortfolioTrade`：`backend/app/models/portfolio_trade.py`
- [x] T004 [P] 新增 SQLAlchemy 模型 `PortfolioOperation`：`backend/app/models/portfolio_operation.py`
- [x] T005 [P] 新增 SQLAlchemy 模型 `PortfolioTradeImage`：`backend/app/models/portfolio_trade_image.py`
- [x] T006 在 `backend/app/models/__init__.py` 导出上述模型并保证可被 Alembic/元数据加载（若项目无迁移工具则执行 SQL 脚本建表）
- [x] T007 新增 Pydantic 模式：`backend/app/schemas/portfolio.py`（请求/响应与 `contracts/personal-portfolio-api.md` 对齐）
- [x] T008 实现核心业务逻辑 `backend/app/services/portfolio_service.py`：同用户同股仅一笔 `open`、加权成本、`add`/`reduce`/`close` 数量校验、清仓时 `status=closed` 与 `realized_pnl` 写入
- [x] T009 实现 `backend/app/services/portfolio_price_service.py`（或并入 `portfolio_service.py` 的独立函数）：按 `stock_code` 查询 `stock_daily_bar` 最新 `trade_date` 的 `close` 供参考市值
- [x] T010 新增路由模块 `backend/app/api/portfolio.py`（可先挂健康检查占位），并在 `backend/app/main.py` 以 `prefix="/api"` 注册；所有写操作预留 `Depends(get_current_user)`（`backend/app/api/deps.py`）

**Checkpoint**：数据库可写入、`portfolio` 路由可访问、模型与 `user_id` 隔离策略明确。

---

## Phase 3: User Story 1 — 「个人服务」入口与当前持仓维护（Priority: P1）🎯 MVP

**Goal**：侧栏「个人服务」→「个人持仓」；**建仓、加仓、减仓**；**当前持仓列表**（可先无参考价）；**删除未完结交易**；同股未清仓仅一行。

**Independent Test**：登录 → 进入菜单 → 建仓 → 列表一行 → 加仓后仍一行且数量变 → 删除后空列表（见 `spec.md` 验收场景）。

- [x] T011 [US1] 在 `backend/app/api/portfolio.py` 实现 `GET /api/portfolio/open-trades`（返回字段可先不含 `ref_*`，或占位 `null`）、`POST /api/portfolio/trades/open`、`POST /api/portfolio/trades/{trade_id}/operations`（`op_type` 为 `add`/`reduce`）、`DELETE /api/portfolio/trades/{trade_id}`（仅 `open`）；`stock_code` 校验引用 `stock_basic`
- [x] T012 [US1] 新增前端 API 封装 `frontend/src/api/portfolio.ts`（Bearer token 与现有 `frontend/src/api/auth.ts` 一致）
- [x] T013 [US1] 更新 `frontend/src/router/index.ts`：在需登录布局下增加子路由（如 `path: 'personal-holdings'`，`name: 'personal-holdings'`）
- [x] T014 [US1] 更新 `frontend/src/views/Layout.vue`：新增 `el-sub-menu`「个人服务」与 `el-menu-item`「个人持仓」指向上述路由
- [x] T015 [US1] 新建 `frontend/src/views/PersonalHoldingsView.vue`：至少包含「当前持仓」区块 — `el-table`、建仓/加仓/减仓弹窗、`DELETE` 确认；样式与 `frontend/src/views/StockScreeningView.vue` 卡片头风格协调

**Checkpoint**：不依赖已完结、图片与胜率即可演示「一笔交易 + 操作记录」闭环（后端+前端）。

---

## Phase 4: User Story 2 — 已完结交易录入与复盘（Priority: P2）

**Goal**：**清仓**结束交易；**已完结列表与详情**；**复盘文字**与**本地上传图片**；图片受鉴权下载。

**Independent Test**：清仓 → 已完结出现一条 → 填复盘、上传图 → 刷新仍在；另一用户不可见（见 `spec.md`）。

- [x] T016 [US2] 在 `backend/app/api/portfolio.py` 实现 `POST /api/portfolio/trades/{trade_id}/close`、`GET /api/portfolio/closed-trades`、`GET /api/portfolio/trades/{trade_id}`（含 `operations` 列表）
- [x] T017 [US2] 在 `backend/app/api/portfolio.py` 实现 `PATCH /api/portfolio/trades/{trade_id}/review`、`POST /api/portfolio/trades/{trade_id}/images`（multipart）、`DELETE /api/portfolio/images/{image_id}`、`GET /api/portfolio/images/{image_id}/file`；文件落盘 `backend/uploads/portfolio/{user_id}/{trade_id}/`，校验 MIME 与大小（见 `research.md`）
- [x] T018 [US2] 扩展 `frontend/src/api/portfolio.ts` 与 `frontend/src/views/PersonalHoldingsView.vue`：「已完结」Tab/列表、`el-drawer` 详情、`el-timeline` 展示操作、复盘 textarea、`el-upload` 图片与预览（交互见 `specs/007-个人持仓/ui-ux.md`）

**Checkpoint**：完整复盘路径可用。

---

## Phase 5: User Story 3 — 持仓参考市值与盈亏概览（Priority: P3）

**Goal**：当前持仓行展示**参考收盘价、参考市值、参考盈亏**；无行情时显示「—」且不造假。

**Independent Test**：有日线时数字与手工核对；删日线或代码无 bar 时无参考价（见 `spec.md`）。

- [x] T019 [US3] 在 `GET /api/portfolio/open-trades` 中合并 `portfolio_price_service` 结果，填充 `ref_close`、`ref_market_value`、`ref_pnl`、`has_ref_price` 等（字段名与 `contracts/personal-portfolio-api.md` 一致）
- [x] T020 [US3] 在 `frontend/src/views/PersonalHoldingsView.vue` 当前持仓表增加参考价/盈亏列；无数据时 `—` + `el-tooltip` 说明（可选）

**Checkpoint**：参考市值与规格 FR-007 一致。

---

## Phase 6: User Story 4 — 易用性与说明（Priority: P4）

**Goal**：页头**能力说明**（一笔交易/操作记录/双胜率含义）；错误提示可读；不占用首屏大块说明。

**Independent Test**：新用户通过悬浮/Popover 能理解范围（见 `spec.md`）。

- [x] T021 [US4] 在 `frontend/src/views/PersonalHoldingsView.vue` 页头增加 `el-popover` 或 `el-tooltip`（与 `frontend/src/views/StockScreeningView.vue` 能力说明模式一致），文案覆盖 `spec.md` 用户需求 4

**Checkpoint**：符合 `specs/007-个人持仓/ui-ux.md` 与项目前端能力提示规则。

---

## Phase 7: User Story 5 — 股票胜率与操作胜率（Priority: P5）

**Goal**：**统计接口**与**统计 Tab UI**；股票胜率按整笔 `realized_pnl`；操作胜率按 `operation_rating`，分母口径可见。

**Independent Test**：样本数据下与手工统计一致（见 `spec.md` SC-006）。

- [x] T022 [US5] 在 `backend/app/api/portfolio.py` 实现 `GET /api/portfolio/stats`；在 `portfolio_service.py`（或同类）聚合 `closed` 盈亏笔数与操作级 `good`/`bad`/`unrated`
- [x] T023 [US5] 在 `frontend/src/views/PersonalHoldingsView.vue` 增加「统计」Tab：两卡片分区展示股票胜率与操作胜率及分母说明文案
- [x] T024 [US5] 在 `backend/app/api/portfolio.py` 实现 `PATCH /api/portfolio/operations/{operation_id}/rating`；在持仓/详情时间线中提供操作自评控件并调用接口（可与 `PersonalHoldingsView.vue` 或子组件 `OperationTimeline.vue` 同文件实现）

**Checkpoint**：两类胜率区分清晰、与规格 FR-009 一致。

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**：跨故事收尾与验证。

- [x] T025 [P] 通读 `contracts/personal-portfolio-api.md`，补全遗漏错误码或响应字段与实现一致
- [x] T026 后端关键操作打日志（建仓/清仓/上传失败）至现有 `backend/logs/app.log` 约定
- [x] T027 按 `specs/007-个人持仓/quickstart.md` 执行一轮手工验收并记录问题

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** → **Phase 2** → **Phase 3～7（按 US 优先级）** → **Phase 8**
- **Phase 2 未完成前**：不要承诺 US1～US5 完成

### User Story Dependencies

- **US1**：仅依赖 Phase 2。
- **US2**：依赖 US1 的交易与操作模型已可用（需 Phase 2 + US1 基础接口）。
- **US3**：依赖 US1 的 `open-trades` 与 Phase 2 价格服务。
- **US4**：可与 US5 前端并行，但通常在 `PersonalHoldingsView.vue` 上迭代，建议 US1 页面骨架后再做。
- **US5**：依赖 US2 的操作记录与清仓数据；统计可在 US2 完成后实现。

### Parallel Opportunities

- T003、T004、T005 可并行。
- T025、T026 可与 T027 前后错开；T025、T026 可并行。

### Parallel Example: Foundational Models

```text
- T003 backend/app/models/portfolio_trade.py
- T004 backend/app/models/portfolio_operation.py
- T005 backend/app/models/portfolio_trade_image.py
```

---

## Implementation Strategy

### MVP First（仅 US1）

1. 完成 Phase 1 + Phase 2  
2. 完成 Phase 3（US1）  
3. 手工验证建仓/加仓/减仓/删除  
4. 再按 P2→P5 增量交付  

### Incremental Delivery

1. US1 → 可用「记账 + 操作记录」  
2. US2 → 清仓与复盘闭环  
3. US3 → 参考市值增强  
4. US4 → 说明与体验  
5. US5 → 双胜率  

---

## Notes

- 实现时以 `FEATURE_DIR` 下契约为准；若接口路径与本文略有出入，以 **`contracts/personal-portfolio-api.md`** 为单一事实来源并同步修改 `tasks.md`。  
- 分支名为 `main` 时，Specify 脚本可能无法自动解析功能目录；开发时以 **`specs/007-个人持仓/`** 为准。
