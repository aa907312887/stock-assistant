# Tasks：恐慌回落选股

**Input**：设计文档来自 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/specs/012-恐慌回落选股/`  
**Prerequisites**：plan.md、spec.md；research.md、data-model.md、contracts/、quickstart.md 已就绪  
**Tests**：规格未要求 TDD；本列表**不包含**强制测试任务，验收以 `quickstart.md` 手动步骤为准。

**Organization**：按用户故事分阶段，便于独立实现与验收。

## Format：`[ID] [P?] [Story] Description`

- **[P]**：可并行（不同文件、无未完成依赖）
- **[Story]**：对应 `spec.md` 用户需求编号（US1…US4）
- 描述中须含**确切文件路径**

## Path Conventions

- 后端：`/Users/yangjiaxing/Coding/CursorProject/stock-assistant/backend/`
- 前端：`/Users/yangjiaxing/Coding/CursorProject/stock-assistant/frontend/`

---

## Phase 1：Setup（范围确认）

**Purpose**：冻结迭代边界，确认复用策略已具备，避免重复造轮子。

- [x] T001 对照 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/specs/012-恐慌回落选股/spec.md` 与 `plan.md`，确认本迭代不含定时选股、不新建业务表
- [x] T002 审阅 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/backend/app/services/strategy/registry.py` 与 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/backend/app/services/strategy/strategies/panic_pullback.py`，确认 `strategy_id=panic_pullback` 且 `execute(as_of_date)` 已可用于落库选股

---

## Phase 2：Foundational（阻塞所有故事）

**Purpose**：API 响应补齐 `exchange` / `market`，否则前端无法按规格展示与筛选。

**⚠️ 未完成本阶段前，不得认为 US1/US2 已验收通过**

- [x] T003 在 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/backend/app/schemas/strategy.py` 的 `StrategySelectionItem` 中增加可选字段 `exchange`、`market`（保留 `exchange_type` 以兼容旧页）
- [x] T004 在 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/backend/app/services/strategy/strategy_execute_service.py` 的 `_candidates_to_api_items` 中批量关联 `StockBasic`，为每条候选填充 `exchange` 与 `market`
- [x] T005 在 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/backend/app/services/strategy/strategy_execute_service.py` 的 `get_latest_strategy_result` 中组装 `items` 时分别写入 `exchange`、`market`（避免用 `exchange or market` 混填两维语义）

**Checkpoint**：`POST/GET /api/strategies/panic_pullback/execute|latest` 返回的 `items[]` 含独立 `exchange`、`market` 字段

---

## Phase 3：User Story 1 — 独立页面执行恐慌回落选股（优先级：P1）🎯 MVP 核心

**Goal**：用户可在恐慌回落页手动执行选股或读取最新落库结果，看到截止日、口径相关元数据及候选表（含代码、名称、触发日、交易所、板块）。

**Independent Test**：用 `quickstart.md` 中 curl 或登录后点击「手动执行」，确认列表与非空/空列表提示；`items` 含 `exchange`、`market`。

### Implementation for User Story 1

- [x] T006 [US1] 在 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/frontend/src/api/strategies.ts` 扩展 `StrategySelectionItem` 类型，增加 `exchange`、`market` 可选属性
- [x] T007 [US1] 新建 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/frontend/src/views/PanicPullbackView.vue`：集成 `executeStrategy('panic_pullback')` 与 `getLatestStrategyResult('panic_pullback')`，展示 `execution` 与 `el-table`（代码、名称、交易所、板块、触发日及 `summary` 中与恐慌回落相关的关键列，如跌幅/放量等）
- [x] T008 [US1] 在 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/frontend/src/router/index.ts` 注册子路由 `strategy/panic-pullback`，懒加载 `PanicPullbackView.vue`
- [x] T009 [US1] 在 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/frontend/src/views/PanicPullbackView.vue` 处理 409（`DATA_NOT_READY`）、404（`latest` 无结果）、500 错误提示，及全量候选为空时的说明文案（对齐 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/frontend/src/views/ChongGaoHuiLuoView.vue` 模式）

**Checkpoint**：通过浏览器访问 `#/strategy/panic-pullback` 可执行并看到表格数据（在路由已注册前提下）

---

## Phase 4：User Story 2 — 按交易所与板块收窄结果（优先级：P1）

**Goal**：在同一次执行结果上多选交易所、多选板块（含空板块 `__EMPTY__`）过滤展示；清空后恢复全量；筛选无命中时有明确提示。

**Independent Test**：在含多交易所、多板块及空 `market` 的样本结果上切换筛选，行数与手工核对一致；清空后行数等于全量。

### Implementation for User Story 2

- [x] T010 [US2] 在 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/frontend/src/views/PanicPullbackView.vue` 增加交易所、板块多选控件，使用 `computed` 从全量 `items` 派生 `filteredItems`（同维 OR、两维 AND；`__EMPTY__` 匹配 `market` 为空或空字符串）
- [x] T011 [US2] 在 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/frontend/src/views/PanicPullbackView.vue` 实现筛选结果为空时的「当前筛选条件下无结果」提示，并提供清空/重置筛选以恢复全量列表

**Checkpoint**：筛选与清空行为符合 `spec.md` 验收场景与 `contracts/strategy-panic-selection-api.md` 第 5 节

---

## Phase 5：User Story 3 — 从策略选股菜单进入（优先级：P1）

**Goal**：主导航「策略选股」下可见「恐慌回落法」并进入本页。

**Independent Test**：登录后从侧栏点击进入，刷新后同路径仍可达。

### Implementation for User Story 3

- [x] T012 [US3] 在 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/frontend/src/views/Layout.vue` 的「策略选股」子菜单中增加「恐慌回落战法」菜单项，`index` 指向 `/strategy/panic-pullback`（与 `PanicPullbackStrategy.describe().route_path` 一致）

**Checkpoint**：不手输 URL 亦可从菜单进入恐慌回落页

---

## Phase 6：User Story 4 — 「收盘价模拟」边界说明（优先级：P2）

**Goal**：用户从页面即可理解日线收盘口径、无分时、与回测一致；符合悬浮/轻量提示规范。

**Independent Test**：仅阅读标题旁提示或卡片即可回答买入卖出对应交易日与价格类型。

### Implementation for User Story 4

- [x] T013 [US4] 在 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/frontend/src/views/PanicPullbackView.vue` 增加口径说明：标题行末 `el-tooltip`（或等价）+ 必要时 `el-card` 摘要，内容覆盖触发日收盘买入、次日收盘卖出、无分时、费用口径与产品一致（遵守 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/.cursor/rules/frontend-product-capability-hints.mdc`）

**Checkpoint**：产品/验收方可对照 `spec.md` 用户需求 4 做走查

---

## Phase 7：Polish & Cross-Cutting

**Purpose**：可选增强与整体验收。

- [x] T014 [P] 在 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/backend/app/services/strategy/strategies/panic_pullback.py` 的 `_select_trigger_day` 中，对 `trade_type=closed` 的笔可选将 `return_rate`、`sell_date`、`sell_price` 并入 `StrategyCandidate.summary`，供前端展示「模拟收益」列（若本期不做该列，可仅保留字段供后续使用）
- [x] T015 按 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/specs/012-恐慌回落选股/quickstart.md` 执行一轮端到端手动验证，记录偏差并回写实现或文档（如需）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** → **Phase 2** → **Phase 3（US1）** → **Phase 4（US2）** → **Phase 5（US3）** → **Phase 6（US4）** → **Phase 7**
- **US3（菜单）** 仅依赖 **T008** 已注册路由（可与 T009 同阶段完成，但须在联调前保证路径可访问）

### User Story Dependencies

| 故事 | 依赖 |
|------|------|
| US1 | Phase 2 完成 |
| US2 | US1 中视图与 `items` 已存在（T007+） |
| US3 | T008 路由已注册 |
| US4 | T007 页面骨架存在即可并行文案，建议放在 US1 主流程之后 |

### Parallel Opportunities

- **T014** 可与 **Phase 4（US2）** 或 **Phase 5** 并行（修改 `panic_pullback.py`，与 `PanicPullbackView.vue` 无直接文件冲突）
- **T013（US4）** 与 **T010–T011（US2）** 若由不同人协作，需注意同一 `PanicPullbackView.vue` 的合并顺序，优先完成筛选再合入口径文案，或先拉分支再合并

### Within-File Order（`PanicPullbackView.vue`）

建议顺序：**T007 骨架 → T009 错误处理 → T010–T011 筛选 → T013 口径提示**，减少冲突。

---

## Parallel Example：Phase 2 之后

```text
开发者 A：T006–T009（US1 前端 + 路由）
开发者 B：T014（后端 summary 可选字段，独立文件）
```

合并前确保 **T003–T005** 已合并主干，以便前端联调。

---

## Parallel Example：User Story 2

```text
T010：筛选逻辑与控件
T011：空筛选提示与重置（可与 T010 同一提交，同一文件连续编辑）
```

---

## Implementation Strategy

### MVP（建议最小可演示）

1. 完成 Phase 1、Phase 2（T001–T005）
2. 完成 Phase 3 US1（T006–T009）
3. 完成 Phase 5 US3（T012），保证菜单可达
4. **停顿验收**：执行选股 + 列表字段 + 菜单入口

### 增量交付

1. 接上 Phase 4 US2（筛选）
2. 接上 Phase 6 US4（口径提示）
3. Phase 7：T014 按需；**T015 必做**作为发布前检查

### 并行团队策略

- 后端完成 T003–T005 后，前端可开始 T006；路由 T008 尽早合并以便联调。
- **避免**在未合并 T003–T005 前依赖线上 `items.exchange` 字段。

---

## Notes

- 所有任务均使用 `- [x] Txxx`  checklist 格式，并含明确路径。
- `[P]` 仅用于文件级可并行任务（如 T014）。
- 实现阶段若变更 API 形状，须同步更新 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/specs/012-恐慌回落选股/contracts/strategy-panic-selection-api.md` 与 OpenAPI（若团队单独维护）。
