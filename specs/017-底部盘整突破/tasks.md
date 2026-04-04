# Tasks: 底部盘整突破

**Input**: 设计文档来自 `/specs/017-底部盘整突破/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/strategy-api.md, research.md

**Tests**: 本功能未显式要求测试任务，按规格不生成测试任务。

**Organization**: 任务按用户故事组织，每个故事可独立实现和测试。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行执行（不同文件，无依赖）
- **[Story]**: 所属用户故事（US1, US2, US3）
- 描述中包含精确文件路径

## Path Conventions

- **Web app**: `backend/app/`, `frontend/src/`
- 项目根目录：`/Users/yangjiaxing/Coding/CursorProject/stock-assistant`

---

## Phase 1: Setup（共享基础设施）

**Purpose**: 确认复用结构与策略接口

- [x] T001 确认 `stock_daily_bar.cum_hist_high` 字段已存在且有数据（复用 013-历史高低价）
- [x] T002 确认 `backtest_trade.extra` JSON 字段可用（复用 010-智能回测）
- [x] T003 确认策略接口 `StockStrategy` 可复用（`backend/app/services/strategy/strategy_base.py`）

**Checkpoint**: 基础设施确认完成，可开始策略实现

---

## Phase 2: Foundational（阻塞性前置任务）

**Purpose**: 核心策略实现，所有用户故事依赖此前置

**⚠️ CRITICAL**: 此阶段完成前，用户故事无法开始

### 后端策略核心实现

- [x] T004 [US1] 创建策略实现文件 `backend/app/services/strategy/strategies/bottom_consolidation_breakout.py`
  - 定义 `_Params` 数据类（consolidation_days=15, consolidation_range=0.03, low_position_ratio=0.5 等）
  - 定义 `_ConsolidationState` 数据类（close_prices 列表、start_date、status）
  - 定义 `_BreakoutSignal` 数据类（stock_code, trigger_date, base_price, days 等）
- [x] T005 [US1] 实现 `BottomConsolidationBreakoutStrategy` 类框架
  - 定义 `strategy_id = "bottom_consolidation_breakout"`
  - 定义 `version = "v1.0.0"`
  - 实现 `describe()` 方法返回 `StrategyDescriptor`
- [x] T006 [US1] 实现盘整形态识别核心算法 `_find_consolidation_breakout()`
  - 低位约束检查：`close <= cum_hist_high * 0.5`
  - 动态平均值计算：每试探性加入新价格后计算平均值
  - 最大偏离度检查：所有价格相对平均值的偏离度 ≤ 3%
  - 突破判定：最大偏离度 > 3% 且收盘价 > 新平均值 × 1.03
  - 失效判定：最大偏离度 > 3% 且非向上突破
- [x] T007 [US1] 实现 `execute()` 方法（策略选股执行）
  - 查询当日所有股票日线数据
  - 按股票逐个调用盘整识别算法
  - 返回 `StrategyExecutionResult`（items + signals）
- [x] T008 [US2] 实现回测交易模拟 `_simulate_trade()`
  - T+1 开盘价买入
  - 逐日检查卖出条件（止损/止盈）
  - 条件单模拟：用日线最低价判断触碰触发价
  - 止损价 = 基准价 × 0.97
  - 止盈触发价 = 最高收盘价 × 0.95（收益 >= 15% 后启用）
- [x] T009 [US2] 实现 `backtest()` 方法（历史回测）
  - 批量查询时间范围内日线数据
  - 按股票分组逐股识别信号
  - 对每个信号模拟交易
  - 返回 `BacktestResult`（trades 列表）

### 策略注册与定时任务

- [x] T010 [US1] 在策略注册表中注册新策略 `backend/app/services/strategy/registry.py`
  - 导入 `BottomConsolidationBreakoutStrategy`
  - 在 `list_strategies()` 中添加实例
- [x] T011 [US1] 添加定时任务 `backend/app/core/scheduler.py`
  - 新增 `_JOB_STRATEGY_BCB` 常量
  - 新增 `_job_strategy_bottom_consolidation_breakout_daily()` 函数
  - 在 `start_scheduler()` 中注册 CronTrigger（17:20）

**Checkpoint**: 策略核心实现完成，可独立通过 API 测试

---

## Phase 3: User Story 1 - 执行底部盘整突破选股（优先级：P1）🎯 MVP

**Goal**: 用户能在策略选股模块中执行"底部盘整突破"选股，获得候选股票列表

**Independent Test**: 调用 `POST /api/strategies/bottom_consolidation_breakout/execute` 返回候选列表

### 实现任务

- [x] T012 [P] [US1] 验证 API 端点自动可用（策略注册后自动出现在 `GET /api/strategies` 列表）
- [x] T013 [US1] 验证 `GET /api/strategies/bottom_consolidation_breakout` 返回策略详情
- [x] T014 [US1] 验证 `POST /api/strategies/bottom_consolidation_breakout/execute` 执行选股
- [x] T015 [US1] 确认候选列表包含必要字段（stock_code, stock_name, trigger_date, base_price, consolidation_days）

**Checkpoint**: 用户故事 1 完成，选股功能可独立测试

---

## Phase 4: User Story 2 - 历史回测（优先级：P1）

**Goal**: 用户能在智能回测模块中选择"底部盘整突破"策略进行历史回测

**Independent Test**: 在回测页面选择底部盘整突破策略，设定时间范围，执行回测并获得交易明细

### 实现任务

- [x] T016 [US2] 验证策略出现在回测策略下拉选项中（复用现有回测框架）
- [x] T017 [US2] 创建回测任务 `POST /api/backtest/run` 指定 `strategy_id="bottom_consolidation_breakout"`
- [x] T018 [US2] 验证交易明细包含策略特有字段（extra.base_price, extra.consolidation_days, extra.exit_reason）
- [x] T019 [US2] 验证卖出原因正确显示（"止损（跌破支撑位）" 或 "止盈（最高价回落5%）"）

**Checkpoint**: 用户故事 2 完成，回测功能可独立测试

---

## Phase 5: User Story 3 - 菜单入口与策略页面（优先级：P2）

**Goal**: 用户能通过菜单进入底部盘整突破策略页面

**Independent Test**: 从任意页面点击"策略选股 → 底部盘整突破"进入策略页面

### 前端实现

- [x] T020 [P] [US3] 新增策略页面组件 `frontend/src/views/BottomConsolidationBreakoutView.vue`
  - 策略说明卡片（描述、假设、风险）
  - 执行按钮
  - 候选股票列表表格（stock_code, stock_name, base_price, consolidation_days, trigger_date）
- [x] T021 [US3] 添加前端路由 `frontend/src/router/index.ts`
  - 路径：`strategy/bottom-consolidation-breakout`
  - 名称：`strategy-bottom-consolidation-breakout`
  - 组件：`BottomConsolidationBreakoutView`
- [x] T022 [US3] 添加侧边栏菜单 `frontend/src/views/Layout.vue`
  - 在"策略选股"一级菜单下新增"底部盘整突破"二级菜单
  - 菜单项指向 `/strategy/bottom-consolidation-breakout`

**Checkpoint**: 用户故事 3 完成，菜单入口与页面可独立测试

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 收尾与验证

- [x] T023 验证定时任务在 17:20 自动执行选股落库
- [x] T024 [P] 更新策略说明文档 `backend/app/services/strategy/strategy_descriptions.py`（如需要）
- [x] T025 执行 `quickstart.md` 验证场景（如有）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，立即开始
- **Foundational (Phase 2)**: 依赖 Setup 完成 - **阻塞所有用户故事**
- **User Stories (Phase 3-5)**: 都依赖 Foundational 完成
  - US1 和 US2 可并行（后端策略已实现）
  - US3 依赖 US1（前端页面需要后端 API）
- **Polish (Phase 6)**: 依赖所有用户故事完成

### User Story Dependencies

- **User Story 1 (P1)**: 依赖 Foundational - 与 US2 可并行
- **User Story 2 (P1)**: 依赖 Foundational - 与 US1 可并行
- **User Story 3 (P2)**: 依赖 US1 API 可用

### Within Each User Story

- 后端策略实现先于前端页面
- 验证任务在实现任务完成后执行

### Parallel Opportunities

- T012, T013 可并行执行（不同 API 端点验证）
- T016, T017, T018 可并行执行（回测流程不同环节）
- T020 可与后端任务并行（前端组件开发）

---

## Parallel Example: Foundational Phase

```bash
# 核心算法与交易模拟可并行开发（不同函数）：
Task: "实现盘整形态识别核心算法 _find_consolidation_breakout()"
Task: "实现回测交易模拟 _simulate_trade()"

# 策略注册与定时任务可并行：
Task: "在策略注册表中注册新策略"
Task: "添加定时任务"
```

---

## Implementation Strategy

### MVP First (User Story 1 + 2)

1. Complete Phase 1: Setup（确认基础设施）
2. Complete Phase 2: Foundational（策略核心实现）
3. Complete Phase 3: User Story 1（选股功能）
4. Complete Phase 4: User Story 2（回测功能）
5. **STOP and VALIDATE**: 测试选股与回测功能
6. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → 后端策略可用
2. Add User Story 1 + 2 → 选股与回测功能完整
3. Add User Story 3 → 前端页面入口完善
4. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = 不同文件，无依赖
- [Story] label 映射任务到用户故事，便于追踪
- 每个用户故事应独立完成和测试
- 任务完成后提交
- 可在任何检查点停顿验证故事独立性
- 避免：模糊任务、同文件冲突、跨故事依赖破坏独立性
