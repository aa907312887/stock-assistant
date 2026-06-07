# Tasks：月 MACD 翻红

**Input**：设计文档位于 `specs/029-月MACD翻红/`（`spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/strategy-api.md`、`quickstart.md`）

**Tests**：`plan.md` 要求 `pytest` 覆盖买入月末判定与三类平仓；测试与策略模块同步交付。

**首期范围**：**历史模拟 + 历史回测**；**不**做策略选股页、**不**注册 APScheduler Job。

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1：Setup

- [x] T001 通读 `spec.md`、`plan.md`、`research.md`，确认 `strategy_id=yue_macd_fan_hong`、月末收盘买、±20% 止盈止损、后续月 MACD 红转绿月末卖及平仓优先级

---

## Phase 2：Foundational

- [x] T002 新建 `backend/app/services/strategy/strategies/yue_macd_fan_hong.py`：纯函数 + `run_yue_macd_fan_hong_backtest` + `YueMacdFanHongStrategy`（详细中文 docstring）
- [x] T003 在 `registry.py` 注册 `YueMacdFanHongStrategy`
- [x] T004 在 `strategy_descriptions.py` 新增 `yue_macd_fan_hong` 文案
- [x] T005 [P] 新建 `backend/tests/test_yue_macd_fan_hong.py`，覆盖 plan §7 用例；`pytest` 通过

---

## Phase 3：User Story 1 — 历史模拟/回测可选用（P1）🎯 MVP

- [x] T006 [US1] 确认 `simulation_engine` / `backtest_engine` 经 `get_strategy` 分派，无需硬编码
- [x] T007 [US1] 执行 `quickstart.md` §3 API 自检（单测 + 策略注册）

---

## Phase 4：User Story 2 — 策略说明可读（P2）

- [x] T008 [US2] 核对 `describe()` 与 `contracts/strategy-api.md` 一致

---

## Phase 5：User Story 3 — 数据不足时可靠跳过（P3）

- [x] T009 [US3] 核对缺月线/hist 跳过逻辑；测试覆盖仅一月数据

---

## Phase 6：Polish

- [x] T010 [P] 可选：`BacktestResultDetail.vue` 增加 `exit_reason` 映射
- [x] T011 更新 `spec.md` 状态为「已实现」

---

## Phase 7：Backlog（不阻塞）

- [ ] T012 策略选股页 + `execute()` 全市场扫描
- [ ] T013 APScheduler 17:25 Job
