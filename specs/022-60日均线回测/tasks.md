# Tasks：60 日均线买入法（历史回测）

**Input**: `specs/022-60日均线回测/` 下 `plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/`、`quickstart.md`  
**Prerequisites**: `plan.md`、`spec.md` 已就绪  

**Tests**: `plan.md` 要求新增 `pytest` 用例；测试任务归入 **US2**（规则可复核），实现以 **`backend/app/services/strategy/strategies/ma60_slope_buy.py`** 为准。

**Organization**: 按用户故事（`spec.md` 优先级）分阶段；**MVP = Phase 1～3（US1）**。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可与同阶段其他 **[P]** 任务并行（不同文件、且仅依赖已完成的前序阶段）
- **[Story]**: `US1` / `US2` / `US3` 对应 `spec.md` 用户需求 1～3

---

## Phase 1: Setup（共享准备）

**Purpose**: 对齐规格与数据前置，无代码分支。

- [x] T001 阅读 `specs/022-60日均线回测/spec.md`、`specs/022-60日均线回测/plan.md`、`specs/022-60日均线回测/contracts/api.md`，确认 `strategy_id` 固定为 `ma60_slope_buy` 及买入链下标口径（`k≥3`、严格不等号）
- [x] T002 按 `specs/022-60日均线回测/quickstart.md` 核对本地/目标库 `stock_daily_bar` 是否具备 `ma60`、`close` 字段且有值（无则先跑日线同步或迁移，避免实现阶段误报「无信号」）

---

## Phase 2: Foundational（阻塞所有用户故事）

**Purpose**: 完成策略内核文件；**未完成前不得开始 US1 注册与前端**。

**⚠️ CRITICAL**: 本阶段完成前不得合并「仅改 registry 无策略类」的半成品。

- [x] T003 新建并实现 `backend/app/services/strategy/strategies/ma60_slope_buy.py`（细则见 `specs/022-60日均线回测/plan.md`「主循环与索引」「卖出仿真」「execute 语义」）：`_Params`、`run_ma60_slope_buy_backtest`、`Ma60SlopeBuyStrategy`（`describe`/`execute`/`backtest`）、ST 剔除、日期窗、三斜率严格不等、`last_block`、收盘价先止损后止盈、`trigger_date`/`extra` 口径及完整中文类 docstring（`.cursor/rules/strategy-class-documentation.mdc`）

**Checkpoint**: 模块可被 `pytest` 与注册表 import，且无语法错误。

---

## Phase 3: User Story 1 - 在系统中发起「60 日均线买入法」历史回测（优先级：P1）🎯 MVP

**Goal**: 历史回测页策略下拉里出现本策略，且 `POST /api/backtest/run` 可跑通并落库。

**Independent Test**: `GET /api/strategies` 含 `ma60_slope_buy`；发起一次回测任务至完成，任务明细中有策略描述快照。

### Implementation for User Story 1

- [x] T004 [P] [US1] 在 `backend/app/services/strategy/registry.py` 中 `import Ma60SlopeBuyStrategy` 并加入 `list_strategies()` 列表（建议紧邻 `MAGoldenCrossStrategy()`）
- [x] T005 [P] [US1] 在 `backend/app/services/strategy/strategy_descriptions.py` 中增加键 `ma60_slope_buy`，文案与 `specs/022-60日均线回测/spec.md` 中买入链、收盘价监测、±15%/-8%、同日止损优先一致
- [ ] T006 [US1] 本地验证：浏览器「智能回测 → 历史回测」选择 **60 日均线买入法** 或使用 `POST /api/backtest/run`（`strategy_id=ma60_slope_buy`）跑完任务，`backtest_task.strategy_description` 非空（与 `specs/022-60日均线回测/quickstart.md` 一致）

**Checkpoint**: US1 单独验收通过即可演示 MVP。

---

## Phase 4: User Story 2 - 核对策略规则与逐笔成交是否一致（优先级：P1）

**Goal**: 表驱动单测覆盖斜率链、斜率 0、止损优先于止盈、买入价为确认日收盘价。

**Independent Test**: `cd backend && pytest tests/test_ma60_slope_buy.py -q` 全绿。

### Tests for User Story 2

- [x] T007 [P] [US2] 新建 `backend/tests/test_ma60_slope_buy.py`：表驱动覆盖三斜率买入链与买入价、斜率 0 不触发、持仓日收盘价先止损后止盈、`unclosed` 及可选 `execute(as_of_date)` 候选（构造 `StockDailyBar` 或等价序列）

- [x] T008 [US2] 在仓库根执行 `cd backend && pytest tests/test_ma60_slope_buy.py -q` 并修复失败用例直至通过（依赖 T003、T007）

**Checkpoint**: 与 `spec.md` FR-002～FR-006 可对齐复核。

---

## Phase 5: User Story 3 - 了解本策略适用范围（优先级：P2）

**Goal**: 策略选股侧可发现、标题旁悬浮说明本策略依赖 MA60 与无信号边界。

**Independent Test**: 访问 `/strategy/ma60-slope-buy`，可见 **?** Tooltip 与执行选股结果表（或空表提示）。

### Implementation for User Story 3

- [x] T009 [P] [US3] 新建 `frontend/src/views/Ma60SlopeBuyView.vue`（参考 `frontend/src/views/MaGoldenCrossView.vue`）：标题 **60 日均线买入法**、`el-tooltip` 简述买入三步链与 ±15%/-8% 卖出及「不构成投资建议」、日期选择、`executeStrategy` 调用 `ma60_slope_buy`、表格展示代码/名称/触发日等

- [x] T010 [US3] 在 `frontend/src/router/index.ts` 增加子路由 `path: 'strategy/ma60-slope-buy'`，`component` 懒加载 `Ma60SlopeBuyView.vue`

- [x] T011 [P] [US3] 在 `frontend/src/views/Layout.vue` 的「策略选股」菜单中增加 **60 日均线买入法** 菜单项，`index` 指向 `/strategy/ma60-slope-buy`

**Checkpoint**: US3 不依赖 US2 测试是否合并即可发版，但依赖 **T003～T005**（API 可用）。

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 规格同步、静态检查、文档收尾。

- [x] T012 [P] 若实现与 `specs/022-60日均线回测/spec.md` 有偏差则更新 `specs/022-60日均线回测/spec.md`（及必要时 `plan.md` 小节）以保持 Spec 驱动一致

- [x] T013 对改动文件执行静态检查（`ruff check` 或 IDE 等价诊断；本环境已用 `read_lints` 覆盖）并消除新增告警

- [ ] T014 按 `specs/022-60日均线回测/quickstart.md` 全节走通并更新该文件中的命令示例（若端口/鉴权与项目实际不一致）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** → **Phase 2**：T003 前完成 T001、T002（可弱依赖，建议先读完档）
- **Phase 2** → **Phase 3～5**：T003 完成后才能 T004～T011
- **Phase 3（US1）** → **Phase 4（US2）**：测试依赖已实现策略；T004、T005 可与 T007 并行（皆依赖 T003）
- **Phase 3（US1）** → **Phase 5（US3）**：前端选股依赖注册与 `describe`
- **Phase 6**：依赖 US1～US3 代码已定稿或准备发版前执行

### User Story Dependencies

| Story | 依赖 | 说明 |
|-------|------|------|
| US1 | T003 | 注册与描述依赖策略类存在 |
| US2 | T003 | 单测 import 策略模块 |
| US3 | T003、T004、T005 | 执行与展示依赖后端注册 |

### Parallel Opportunities

- **T004 [US1]、T005 [US1]、T007 [US2]**：在 T003 完成后可由不同人并行改 `registry.py`、`strategy_descriptions.py`、`test_ma60_slope_buy.py`
- **T009 [US3]、T011 [US3]**：在 T010 所需组件文件已存在前提下，`Ma60SlopeBuyView.vue` 与 `Layout.vue` 可并行编辑；**路由文件** `router/index.ts` 建议在视图文件落盘后提交（避免 import 不存在组件）

---

## Parallel Example: After T003

```bash
# 可并行启动（不同文件）：
# - 修改 backend/app/services/strategy/registry.py
# - 修改 backend/app/services/strategy/strategy_descriptions.py
# - 新建 backend/tests/test_ma60_slope_buy.py
```

---

## Implementation Strategy

### MVP First（仅 US1）

1. 完成 Phase 1、Phase 2（T001～T003）  
2. 完成 Phase 3（T004～T006）  
3. **STOP**：演示历史回测可选本策略并成功落库  

### Incremental Delivery

1. 加上 Phase 4（T007～T008）→ 规则可回归测试  
2. 加上 Phase 5（T009～T011）→ 选股页与可发现性  
3. Phase 6 发布前清理  

### 任务统计

| 阶段 | 任务数 |
|------|--------|
| Phase 1 | 2 |
| Phase 2 | 1 |
| Phase 3 (US1) | 3 |
| Phase 4 (US2) | 2 |
| Phase 5 (US3) | 3 |
| Phase 6 | 3 |
| **合计** | **14** |

| 用户故事 | 任务数 | 任务 ID |
|----------|--------|---------|
| US1 | 3 | T004～T006 |
| US2 | 2 | T007～T008 |
| US3 | 3 | T009～T011 |

---

## Notes

- 所有任务描述均含**明确文件路径**；实现细节以 `specs/022-60日均线回测/plan.md` 为准。  
- 未要求「先写测再实现」；US2 测试可在 T003 完成后与注册并行推进。  
- 提交与推送遵守仓库 Git 规则；助手未经用户同意不执行 `git commit` / `git push`。
