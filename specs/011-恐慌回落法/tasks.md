# Tasks: 恐慌回落法（历史回测）

**Input**: Design documents from `/specs/011-恐慌回落法/`  
**Prerequisites**: `plan.md`, `spec.md`（可选：`data-model.md`, `contracts/`, `research.md`, `quickstart.md`）  
**Tests**: 本任务清单未强制加入测试任务（规格未要求 TDD）；如需可在实现阶段补充。

## Phase 1: Setup（共享基础）

- [ ] T001 梳理并确认复用“智能回测”现有接口与数据表（参考 `specs/010-智能回测/plan.md` 与 `specs/010-智能回测/contracts/backtest-api.md`）
- [x] T002 [P] 补充/更新策略枚举或策略注册表，新增策略键 `panic_pullback`（文件路径以现有策略工厂/注册表为准）

---

## Phase 2: Foundational（阻塞前置）

- [ ] T003 定义并落地“恐慌回落法”策略参数结构（对齐 `specs/011-恐慌回落法/spec.md` 与 `data-model.md`）
- [ ] T004 [P] 确认日线 OHLCV 数据读取入口（行情表/服务）能按股票 + 日期范围批量获取数据（文件路径以现有行情 Service 为准）
- [ ] T005 确认回测引擎能够把 `strategy_params` 透传到策略实现，并在任务详情中可追溯（如已有则只需补齐该策略参数落库/展示）

**Checkpoint**：基础能力满足“可调用策略 + 可取日线数据 + 可保存参数”

---

## Phase 3: User Story 1 - 生成逐笔交易（Priority: P1）🎯 MVP

**Goal**：实现“恐慌回落法”的信号扫描与交易生成（FR-001、FR-002）。

**Independent Test**：对任意单股票 + 区间运行回测，能输出触发日交易列表；每笔交易买入价=触发日收盘，卖出价=次日收盘。

- [x] T006 [US1] 新增策略实现文件：实现恐慌回落法信号判定与交易生成（文件路径：`backend/app/services/strategy/strategies/` 下新增或按现有约定放置）
- [x] T007 [US1] 在策略工厂/注册表中注册 `panic_pullback` → 指向新策略实现（文件路径以现有策略注册位置为准）
- [x] T008 [US1] 回测引擎接入该策略：按股票池与区间逐日扫描，命中信号生成 Trade（买入=触发日收盘，卖出=次日收盘），并落库到交易明细表（文件路径以现有回测引擎为准）
- [x] T009 [US1] 落地“数据不足/不可成交”口径：当无法取到触发日或次日收盘价时，标记为不可成交并在结果中计数（文件路径以现有引擎/报告模块为准）

**Checkpoint**：P1 完成后，可在任务详情中看到该策略的逐笔交易明细

---

## Phase 4: User Story 2 - 输出汇总指标（Priority: P2）

**Goal**：输出回测汇总指标（FR-003），并在任务详情接口/页面可见。

**Independent Test**：同一任务能返回至少：交易次数、胜率、平均/中位数收益率、最大单笔亏损、最大连续亏损次数、不可成交占比。

- [ ] T010 [US2] 在回测报告/指标计算模块中补齐所需指标计算（若已存在则校验口径并补缺项）（文件路径以现有 backtest_report/metrics 模块为准）
- [x] T011 [US2] 确保任务详情接口返回上述指标（文件路径：`backend/app/api/` 下回测相关接口文件）
- [x] T012 [US2] （如有前端页面）在回测详情区域展示新增/缺失指标（文件路径：`frontend/src/` 下回测页面组件）

---

## Phase 5: User Story 3 - 参数化与对比（Priority: P3）

**Goal**：支持参数化运行与可复现（FR-004），并能对比不同参数的结果（最小先支持“同策略不同参数分别跑任务”）。

**Independent Test**：同一股票池与区间，改变 `volume_k` 或阈值后重新跑任务，任务详情能显示参数且结果可复现。

- [ ] T013 [US3] 在回测运行请求中支持传入 `strategy_params`（对齐 `contracts/backtest-panic-pullback.md`），并写入任务记录（文件路径：回测运行 API + task 模型/表）
- [ ] T014 [US3] 在任务详情中展示该次回测的策略参数（文件路径：后端返回结构 + 前端展示）
- [ ] T015 [US3] （可选增强）增加“参数对比”视图或导出：同区间不同任务的指标并排展示（文件路径：前端回测页面）

---

## Phase N: Polish & Cross-Cutting

- [ ] T016 [P] 用 `specs/011-恐慌回落法/quickstart.md` 走通一次端到端流程并修正文档口径（文件路径：`specs/011-恐慌回落法/quickstart.md`）
- [ ] T017 [P] 补充最小日志：记录每次回测任务的策略参数、交易数、不可成交数（文件路径以现有日志位置为准）

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1（MVP）→ US2 → US3 → Polish
- **MVP 建议范围**：做到 US1（T006~T009）即可完成“历史验证”的核心闭环；US2/US3 属于可用性与可比性增强。

