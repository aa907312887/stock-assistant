# Tasks：手动模拟交易

**Input**：设计文档位于 `specs/031-手动模拟交易/`（`spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/api.md`、`quickstart.md`）

**Tests**：`plan.md` / `quickstart.md` 要求 `backend/tests/test_manual_trading.py` 覆盖比例跟盘、门禁与用户隔离；与核心服务同步交付。

**Organization**：按用户故事分阶段；后端基础层完成后，前端按 US1→US4 递增交付可验收增量。

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1：Setup

**Purpose**：确认范围与契约，避免与 020 混淆。

- [x] T001 通读 `specs/031-手动模拟交易/spec.md`、`plan.md`、`contracts/api.md`、`data-model.md`，确认：比例跟盘公式、awaiting_reval 状态机、JWT+user_id 隔离、路由 `/backtest/manual-trading`、菜单置于「复利模拟」之后

---

## Phase 2：Foundational（阻塞所有用户故事）

**Purpose**：数据库、模型、服务、API 骨架一次性就绪。

**⚠️ CRITICAL**：Phase 2 完成前不开始前端用户故事。

- [x] T002 新建 `backend/scripts/add_manual_trading_tables.sql`（`manual_trading_session`、`manual_trading_operation` 及索引，含 `last_advance_step` 字段）
- [x] T003 [P] 新建 `backend/app/models/manual_trading.py`（`ManualTradingSession`、`ManualTradingOperation`）
- [x] T004 [P] 新建 `backend/app/schemas/manual_trading.py`（与 `contracts/api.md` 请求/响应一致）
- [x] T005 在 `backend/app/models/__init__.py` 导出上述模型（若项目采用集中导出）
- [x] T006 新建 `backend/app/services/manual_trading_service.py`：实现 `create_session`、`list_sessions`、`get_session`、`delete_session`、`buy`、`advance`、`reval`、`end`、`list_operations`；Decimal 比例跟盘；`_assert_owner` / `_assert_active` / awaiting_reval 门禁
- [x] T007 新建 `backend/app/api/manual_trading.py`：9 个端点，全部 `Depends(get_current_user)`
- [x] T008 在 `backend/app/main.py` 注册 `manual_trading_router`（prefix `/api`）

**Checkpoint**：本地执行 `mysql ... < backend/scripts/add_manual_trading_tables.sql` 后，可用 curl + JWT 创建会话并返回 201。

---

## Phase 3：User Story 1 — 创建会话并设定标的与起始时间（P1）🎯 MVP

**Goal**：登录用户可新建手动模拟会话（标的名称 + 起始日期），列表可见且落盘。

**Independent Test**：新建「纳斯达克100」、起始 `2001-01-01`；GET 列表含该会话；刷新后仍在。

- [x] T009 [P] [US1] 新建 `frontend/src/api/manualTrading.ts`（types + `createSession`、`listSessions`、`getSession`、`deleteSession`）
- [x] T010 [US1] 新建 `frontend/src/views/ManualTradingListView.vue`：会话表格、新建对话框（标的名称、起始日期）、删除确认、进入详情
- [x] T011 [US1] 在 `frontend/src/router/index.ts` 注册路由 `backtest/manual-trading` → `ManualTradingListView.vue`
- [x] T012 [US1] 在 `frontend/src/views/Layout.vue` 智能回测子菜单「复利模拟」后追加「手动模拟交易」→ `/backtest/manual-trading`

**Checkpoint**：仅 US1 时用户可创建/列表/删除会话，尚无可买入详情页亦可先用 API 验证落盘。

---

## Phase 4：User Story 2 — 在当前模拟日买入（P1）

**Goal**：进行中会话在当前模拟日录入买入金额与成交价，持仓与流水更新。

**Independent Test**：买入 10 万 @2000 → `position_value=100000`，流水 1 条 buy；同日第二笔买入累加。

- [x] T013 [US2] 在 `frontend/src/router/index.ts` 注册 `backtest/manual-trading/:sessionId` → `ManualTradingSessionView.vue`
- [x] T014 [US2] 新建 `frontend/src/views/ManualTradingSessionView.vue` 骨架：加载 `getSession`、展示汇总卡片（模拟日、持仓、累计买入、参考价）
- [x] T015 [US2] 在 `ManualTradingSessionView.vue` 实现买入表单（金额、成交价）与 `POST .../buy`；`awaiting_reval=true` 时禁用

**Checkpoint**：US1+US2 可完成「建会话 → 买入 → 看持仓与流水（若已接 operations 区可先留空）」。

---

## Phase 5：User Story 3 — 快捷推进时间并录入收盘价（P1）

**Goal**：+1 天/周/月/年后须录收盘价，持仓按 \(V'=V×P_{new}/P_{old}\) 更新。

**Independent Test**：10 万 @2000 → 推进一年 → 录 1800 → 持仓 9 万，本段盈亏 −1 万。

- [x] T016 [US3] 在 `ManualTradingSessionView.vue` 实现推进按钮（day/week/month/year）调用 `POST .../advance`
- [x] T017 [US3] 在 `ManualTradingSessionView.vue` 实现待录价区（`awaiting_reval` 时展示）与 `POST .../reval`；录价完成前禁用买入/推进/结束
- [x] T018 [P] [US3] 新建 `backend/tests/test_manual_trading.py`：比例跟盘 10 万×(1800/2000)=9 万、awaiting_reval 门禁、推进后未录价不可 buy

**Checkpoint**：US1～US3 覆盖规格核心路径「买入 → 推进一年 → 录价 → 看盈亏」。

---

## Phase 6：User Story 4 — 结束交易并查看复盘（P1）

**Goal**：结束会话后只读复盘：全部操作、单次盈亏、间隔、总盈亏、总交易时间。

**Independent Test**：有买入后结束 → 状态 ended；operations 含 buy/reval/end；总盈亏 = 持仓 − 累计买入。

- [x] T019 [US4] 在 `frontend/src/api/manualTrading.ts` 补充 `buy`、`advance`、`reval`、`end`、`listOperations`
- [x] T020 [US4] 在 `ManualTradingSessionView.vue` 实现「结束交易」与 `GET .../operations` 复盘表（含 `days_since_prev`、`segment_pnl`、汇总总盈亏/总交易时间）
- [x] T021 [US4] 在 `ManualTradingSessionView.vue` 实现已结束会话只读态（隐藏买入/推进/录价/结束）

**Checkpoint**：US1～US4 形成完整闭环，可演示结束复盘。

---

## Phase 7：User Story 5 — 持久化与续作（P1）

**Goal**：进行中会话离开页面或重新登录后可续作，数据与离开时一致。

**Independent Test**：买入并推进后退出登录再进入同 sessionId，字段与流水一致。

- [x] T022 [US5] 在 `ManualTradingListView.vue` 区分进行中/已结束状态，进行中点击进入可续作
- [x] T023 [US5] 按 `specs/031-手动模拟交易/quickstart.md` §4 验证刷新与重新登录后续作（手动或补充测试）

**Checkpoint**：满足 SC-003 落盘续作。

---

## Phase 8：User Story 6 — 理解本页边界（P2）

**Goal**：悬浮能力说明，区分与「历史模拟交易」的差异。

**Independent Test**：列表页与详情页标题旁「?」可读，含手动价格、比例跟盘、落盘、非投资建议。

- [x] T024 [P] [US6] 在 `frontend/src/views/ManualTradingListView.vue` 添加 `el-tooltip` 能力说明
- [x] T025 [P] [US6] 在 `frontend/src/views/ManualTradingSessionView.vue` 添加 `el-tooltip` 能力说明

---

## Phase 9：Polish & Cross-Cutting

- [x] T026 [P] 在 `backend/tests/test_manual_trading.py` 补充：无买入不可 end、用户 A 不可访问用户 B 会话
- [x] T027 执行 `pytest backend/tests/test_manual_trading.py -v` 与 `quickstart.md` 全流程，确认 SC-001～SC-004
- [x] T028 实现完成后更新 `specs/031-手动模拟交易/spec.md` 状态为「已实现」

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1 Setup
    ↓
Phase 2 Foundational（阻塞）
    ↓
Phase 3 US1 → Phase 4 US2 → Phase 5 US3 → Phase 6 US4
    ↓
Phase 7 US5（依赖 US1～US4 页面）
    ↓
Phase 8 US6（可与 US5 并行）
    ↓
Phase 9 Polish
```

### User Story Dependencies

| 故事 | 依赖 | 说明 |
|------|------|------|
| US1 | Phase 2 | 后端 sessions API 已就绪 |
| US2 | US1 | 需 sessionId 与详情路由 |
| US3 | US2 | 需已有买入与 reference_price |
| US4 | US3 | 复盘含 reval 流水 |
| US5 | US4 | 完整会话生命周期 |
| US6 | US1 | 列表页即可加 Tooltip；详情页在 US2 后 |

### Parallel Opportunities

**Phase 2**（可并行）：

```text
T003 models/manual_trading.py
T004 schemas/manual_trading.py
```

**Phase 3**（T009 与后端无依赖，可与 T010 并行若两人分工）：

```text
T009 api/manualTrading.ts
```

**Phase 5**：

```text
T018 test_manual_trading.py  （与 T016/T017 不同文件，可并行编写）
```

**Phase 8**：

```text
T024 ManualTradingListView.vue tooltip
T025 ManualTradingSessionView.vue tooltip
```

---

## Implementation Strategy

### MVP First（推荐）

1. Phase 1 + Phase 2（后端全通）
2. Phase 3 US1（能建会话、看列表）
3. Phase 4 US2 + Phase 5 US3（买入 + 推进录价）→ **可演示核心价值**
4. Phase 6 US4（结束复盘）
5. Phase 7～9 收尾

### 任务统计

| 阶段 | 任务数 |
|------|--------|
| Setup | 1 |
| Foundational | 7 |
| US1 | 4 |
| US2 | 3 |
| US3 | 3 |
| US4 | 3 |
| US5 | 2 |
| US6 | 2 |
| Polish | 3 |
| **合计** | **28** |

**MVP 范围（最小可演示）**：T001～T018（Setup + Foundational + US1～US3），共 18 项。

---

## Notes

- 本功能**不涉及**定时任务与 APScheduler。
- 与 `paper_trading_*` **禁止**共用表或服务；`session_id` 前缀 `mt-`。
- 所有 API 须 JWT；与 020 无 user_id 的实现保持独立。
- 提交前运行 `cd backend && pytest tests/test_manual_trading.py` 与 `ruff check`（若改动后端）。
