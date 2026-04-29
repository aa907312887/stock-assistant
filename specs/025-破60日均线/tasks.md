---

description: "025-破60日均线 实施任务清单"
---

# Tasks：破 60 日均线买入法（历史回测）

**Input**: `/specs/025-破60日均线/` 下 `plan.md`、`spec.md`、`data-model.md`、`contracts/strategy-backtest.md`、`research.md`、`quickstart.md`  
**前置**: `plan.md`、`spec.md`  
**测试**: `plan.md` 要求 `pytest` 表驱动单测；以下含**测试类**任务。

**组织方式**: 按 `spec.md` 用户故事 **US1（P1）/ US2（P1）/ US3（P2）** 分阶段，便于分阶段验收。

## Phase 1：Setup（实现前对齐）

**Purpose**：与现网 `ma60_slope_buy` 对齐可复用块，无新表、无新路由。

- [ ] T001 通读 `specs/025-破60日均线/plan.md`、`research.md`，并对照 `backend/app/services/strategy/strategies/ma60_slope_buy.py` 标出可复用的数据查询范围、`simulate_exit_close_only` 循环顺序及 `last_block`/`unclosed` 结构，作为实现检清单

---

## Phase 2：Foundational（阻塞项）

**Purpose**：确认无迁移；数据依赖与现网一致。

- [ ] T002 确认本功能**不**新增 MySQL 脚本；`stock_daily_bar` 已含 `ma60`/`open`/`close`（与 `ma60_slope_buy` 相同前提），在 `plan.md` 或本任务备注中记一条「已核对」

**Checkpoint**：可开始 US1 编码。

---

## Phase 3：User Story 1 — 发起本策略历史回测（Priority: P1）🎯 MVP

**Goal**：`strategy_id=ma60_five_day_break` 出现在 `GET /api/strategies`，`POST /api/backtest/run` 可创建任务并跑通。

**Independent Test**：`listStrategies()` 含新项；`POST /api/backtest/run` 带 `strategy_id=ma60_five_day_break` 返回 202 且任务完成无异常（见 `quickstart.md`）。

### Implementation

- [ ] T003 [US1] 新建 `backend/app/services/strategy/strategies/ma60_five_day_break.py`：实现 `_Params`（`take_profit_pct=0.08`、`stop_loss_pct=0.08`）、从 `ma60_slope_buy` 复制并改为双 8% 的**收盘价**退出函数、**五日在下 + 突破 + 次日开盘买** 信号检测、`run_ma60_five_day_break_backtest` 全市场扫描（`extended_start/end`、剔 ST、区间过滤、`last_block` 与 `unclosed` 与 `ma60_slope_buy` 对齐）、`BacktestResult` 产出
- [ ] T004 [US1] 在同文件实现 `Ma60FiveDayBreakStrategy`：`strategy_id = "ma60_five_day_break"`、`describe()` 填充名称/短描述/假设与风险、`backtest()` 委托 `run_ma60_five_day_break_backtest`；策略类**完整中文 docstring**（按项目策略注释规范，含目标、规则分步、阈值、边界、示例）
- [ ] T005 [US1] 在 `backend/app/services/strategy/registry.py` 增加 `from app.services.strategy.strategies.ma60_five_day_break import Ma60FiveDayBreakStrategy` 与 `list_strategies()` 中**紧邻** `Ma60SlopeBuyStrategy` 注册 `Ma60FiveDayBreakStrategy()` 实例
- [ ] T006 [P] [US1] 在 `backend/app/services/strategy/strategy_descriptions.py` 增加键 `ma60_five_day_break` 的说明文本，与 `spec.md` FR-001～FR-006 一致
- [ ] T007 [US1] 本地按 `specs/025-破60日均线/quickstart.md` 验证 `GET /api/strategies` 与 `POST /api/backtest/run`；有问题则修正直至 202/任务可完成

**Checkpoint**：仅 US1 已可演示「能选、能回测」MVP。

---

## Phase 4：User Story 2 — 规则可复核与明细（Priority: P1）

**Goal**：单元测试覆盖核心口径；`extra` 可支撑明细核对与复现。

**Independent Test**：`pytest tests/test_ma60_five_day_break.py` 通过；同区间两次回测结果一致（逻辑上由确定分支保证）。

### Implementation

- [ ] T008 [P] [US2] 新建 `backend/tests/test_ma60_five_day_break.py`：表驱动/构造**最小** `bars` 对象列表，覆盖（1）五日在下+突破+次日开买+随后收盘 **+8%** 止盈、（2）**先**触及 **−8%** 止损、（3）前 5 日有一条不满足在下方则**无买**、（4）`open` 无效则**无买**、（5）重复扫描确定性（可选：同一输入两次结果一致）
- [ ] T009 [US2] 在 `backend/app/services/strategy/strategies/ma60_five_day_break.py` 的成交 `extra` 中写入 `pattern_path`、与 +8%/-8% 一致的 `exit_reason` 字符串（与 `plan.md` 建议一致，避免与 15% 策略混淆），并含信号日/突破日便于核对
- [ ] T010 [US2] 在 `backend/` 下执行 `pytest tests/test_ma60_five_day_break.py -q` 全绿；失败则修实现直至通过

**Checkpoint**：US1+US2 满足规格「可复核、可复现」。

---

## Phase 5：User Story 3 — 选择时的边界认知（Priority: P2）

**Goal**：`describe()` 中明确「需足量 K/MA60、无则少信号」；无成交时与现网**同风格**空结果（引擎已有则仅验收）。

**Independent Test**：`describe.assumptions` 可读到边界；零成交回测不 500、不显示虚假盈利。

### Implementation

- [ ] T011 [US3] 强化 `backend/app/services/strategy/strategies/ma60_five_day_break.py` 中 `StrategyDescriptor` 的 `assumptions`/`risks`/`short_description`，点明**不考虑停牌、以库中连续 K 为序**、与 [research.md](./research.md) 一致
- [ ] T012 [P] [US3] 确认 `frontend/src/components/BacktestConfigPanel.vue` 仅通过 `listStrategies()` 填充下拉，**无**新路由即可展示新策略；若其它页（如 `HistoryBacktestView.vue`）有硬编码策略名列表，补 `ma60_five_day_break` 或改为 API 拉取（二选一，以不破坏既有为准）

**Checkpoint**：US1～US3 可独立验收完毕。

---

## Phase 6：Polish & Cross-Cutting

**Purpose**：规格状态、静态检查、契约句读。

- [ ] T013 将 `specs/025-破60日均线/spec.md` 头**状态**更新为与实现阶段一致（如「已实现」或「待联调」）
- [ ] T014 核对 `specs/010-智能回测/contracts/backtest-api.md`：若需补充「可选 `strategy_id` 枚举含 `ma60_five_day_break`」**一句**则追加；否则在任务备注中写「无需改契约」
- [ ] T015 [P] 对 `backend/app/services/strategy/strategies/ma60_five_day_break.py` 运行 `ruff check` 并修至无新增严重问题
- [ ] T016 更新 `specs/025-破60日均线/checklists/requirements.md` 中「可进入实现」**备注**为已完成/指向本 `tasks.md`

---

## Dependencies & Execution Order

### Phase 依赖

- **Phase 1** → 无前置。
- **Phase 2** → 依 Phase 1 阅读结论；**阻塞** US1。
- **Phase 3（US1）** → 依 Phase 2；**MVP 可止于本阶段**。
- **Phase 4（US2）** → 依 T003 核心信号与 `run_*` 可写测（T008 可在 T003 后并行编写）。
- **Phase 5（US3）** → 依 T004 `describe` 初稿，可与 Phase 4 部分并行（T012 可与 T011 并行）。
- **Phase 6** → 依 **Phase 3～5** 交付内容。

### 用户故事依赖

- **US1**：仅依赖 Phase 2。  
- **US2**：依赖 US1 核心实现（T003+）。  
- **US3**：主要依赖 T004 描述与现网回测空结果行为。

### 并行机会

- **T006** 可与 **T005** 并行（不同文件）。  
- **T008** 在 **T003** 抽出纯函数后，可与 **T006/T007** 并行。  
- **T012** 与 **T011** 可并行。  
- **T015** 与 **T014** 可并行。

### 并行示例（US1）

```text
# 在 T003 提交信号与回测主逻辑后：
T006  strategy_descriptions 文案
T005  registry 注册（与 T006 可并行，注意 import 不循环）
```

---

## Implementation Strategy

### MVP

1. 完成 **Phase 1 + 2 + 3** → 可选策略、可发回测。  
2. **停**在验收点，按 `quickstart` 手测。  

### 增量

3. **Phase 4** 测试与 `extra` → 可复核。  
4. **Phase 5** 体验与边界说明。  
5. **Phase 6** 收尾。  

### 任务与故事映射

| 故事 | 任务 |
|------|------|
| US1 | T003–T007 |
| US2 | T008–T010 |
| US3 | T011–T012 |

**总任务数**：**16**（T001–T016）。

## Notes

- 本功能**无**定时任务；不登记 `scheduler`。  
- `execute()` / 选股联调**不在** P1 任务；若产品要求与 `ZaoChenShiZiXing` 同入口，在 **T017（可选，未列）** 拆任务。  
- `strategy_id` **须**为 `ma60_five_day_break`（与 `specs/025-破60日均线/contracts/strategy-backtest.md` 一致）。
