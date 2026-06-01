# Tasks：早晨十字星（简化版）

**Input**：设计文档位于 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/specs/026-早晨十字星简化版/`（`spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/strategy-api.md`、`quickstart.md`）

**Tests**：规格未强制 TDD；未列入自动化测试任务（如需补充 pytest，可在 Phase 6 后追加）。

**用户补充**：须将新策略纳入**智能回测（历史回测）**可选列表并成功跑通——本项目通过 **策略注册表 + `StockStrategy.backtest()`** 接入 `POST /api/backtest/run`，无单独「回测白名单」配置（与「均线金叉」限定 `symbols` 不同）。

**Organization**：按用户故事（spec.md）分阶段；任务含明确文件路径。

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1：Setup（同步上下文）

**Purpose**：开发前对齐口径与标识，避免实现漂移。

- [x] T001 通读 `specs/026-早晨十字星简化版/spec.md`、`plan.md`、`research.md`，确认 `strategy_id=zao_chen_shi_zi_xing_jian_hua`、80% 历史高位线、T+1 开盘价买入、止盈 8%/止损 6% 及停牌顺延规则

---

## Phase 2：Foundational（阻塞所有用户故事的后端基础）

**Purpose**：完成内置策略实现与注册后，`GET /api/strategies` 与 **`POST /api/backtest/run`（历史回测）** 才能解析到新策略；此为 MVP 必经路径。

**⚠️ CRITICAL**：未完成本阶段前，不应开始前端页面与定时任务联调。

- [x] T002 新建并实现 `backend/app/services/strategy/strategies/zao_chen_shi_zi_xing_jian_hua.py`：含 `_Params`（如 `max_close_to_cum_hist_high_ratio=0.8`、止损 6%、止盈 8%）、`run_morning_star_jian_hua_backtest`（形态与跌势判定对齐 `zao_chen_shi_zi_xing.py` 当前实现；价位线 0.8；买入为 T+1 `open` 及停牌顺延；持仓仿真为先止损 `stop_loss_6pct` 后止盈 `take_profit_8pct`）、类 `ZaoChenShiZiXingJianHuaStrategy` 实现 `describe()` / `backtest()` / `execute()`（`execute` 仅保留 `buy_date == as_of_date` 的候选，口径与 `ZaoChenShiZiXingStrategy.execute` 类推），类顶 **简体中文 docstring** 符合 `.cursor/rules/strategy-class-documentation.mdc`
- [x] T003 在 `backend/app/services/strategy/registry.py` 中 `import ZaoChenShiZiXingJianHuaStrategy` 并在 `list_strategies()` 中于 `ZaoChenShiZiXingStrategy()` **紧邻之后**插入 `ZaoChenShiZiXingJianHuaStrategy()` 实例
- [x] T004 在 `backend/app/services/strategy/strategy_descriptions.py` 的 `STRATEGY_DESCRIPTIONS` 字典中新增键 `zao_chen_shi_zi_xing_jian_hua`，撰写与其它策略同风格的**简明买入/卖出要点**（供历史模拟等读取 `strategy_description` 时不为空）

**Checkpoint**：后端启动后 `GET /api/strategies` 出现「早晨十字星（简化版）」；`backend/app/services/backtest/backtest_engine.py` 与 `backend/app/services/backtest/simulation_engine.py` **无需改路由即可** `get_strategy(...).backtest()` —— 若审阅发现异常分支再补任务。

---

## Phase 3：User Story 1 — 回测/选股可选用且历史回测可用（优先级：P1）🎯 MVP

**Goal**：用户在智能回测中选择本策略并提交任务后，能生成交易明细；策略与「早晨十字星」主策略在触发日、买入价、卖出原因上可区分。

**Independent Test**：按 `specs/026-早晨十字星简化版/quickstart.md` 调用 `POST /api/backtest/run`（`strategy_id=zao_chen_shi_zi_xing_jian_hua`）；检查返回任务完成后 trade 中 `trigger_date`、`buy_date`、`extra.exit_reason` 符合规格。

- [x] T005 [US1] 审阅 `backend/app/services/backtest/backtest_engine.py`：确认回测线程仅依赖 `get_strategy(body.strategy_id)`，**无**需新增 `strategy_id` 分支即可运行新策略；若有与 `STRATEGY_DESCRIPTIONS` 相关的空描述问题，确认已由 T004 解决
- [x] T006 [US1] 使用本地服务执行 `specs/026-早晨十字星简化版/quickstart.md` 中 **§2.1、§2.2**（`GET /api/strategies`、`POST /api/backtest/run`），确认历史回测任务成功落库且明细字段可追溯（部署后按 quickstart 手测）

**Checkpoint**：**历史回测（增加新方法）**目标达成 — 前端 `BacktestConfigPanel.vue` 自 `/api/strategies` 动态拉取列表时会包含新策略，无需单独硬编码 strategy_id（除非项目另有静态枚举需同步，发现则补充一行任务）。

---

## Phase 4：User Story 2 — 与主策略可区分、产品可说明（优先级：P2）

**Goal**：独立策略说明页、路由与侧栏入口；悬浮说明本页能力与边界（与 `spec.md` 一致）。

**Independent Test**：浏览器访问新路由，可见文案与 Tooltip；与「早晨十字星」页对比标题与规则描述不同。

- [x] T007 [US2] 新建 `frontend/src/views/ZaoChenShiZiXingJianHuaView.vue`（可参考 `frontend/src/views/ZaoChenShiZiXingView.vue`）：展示策略名称、`GET /api/strategies/{id}` 详情、手动执行选股、`el-tooltip` 或等价悬浮说明（形态同主策略、80% 线、T+1 开盘、8%/6% 止盈止损）
- [x] T008 [US2] 在 `frontend/src/router/index.ts` 增加子路由 `path: 'strategy/zao-chen-shi-zi-xing-jian-hua'`，`component` 指向 `ZaoChenShiZiXingJianHuaView.vue`，`name` 不与现有冲突
- [x] T009 [US2] 在 `frontend/src/views/Layout.vue` 策略选股菜单中，紧挨「早晨十字星」增加菜单项「早晨十字星（简化版）」，导航至上述路由

**Checkpoint**：用户可从侧栏进入说明页并完成手动选股；与 US1 回测能力独立验收。

---

## Phase 5：User Story 3 — 数据不足时可靠跳过（优先级：P3）

**Goal**：缺 K 线、缺均线、无效 `cum_hist_high` 时不误触发；错误提示可运维定位。

**Independent Test**：代码审查 + 可选构造缺字段样本单测（非强制）。

- [x] T010 [US3] 在 `backend/app/services/strategy/strategies/zao_chen_shi_zi_xing_jian_hua.py` 中逐项核对：`open/high/low/close`、`ma5/ma10/ma20`、`cum_hist_high` 无效时跳过；数据库缺列时 `RuntimeError` 文案包含「早晨十字星（简化版）」或 `strategy_id` 便于日志检索（对齐主策略错误前缀风格）

---

## Phase 6：Polish & Cross-Cutting Concerns

**Purpose**：定时选股、回测明细展示一致性、规格收尾。

- [x] T011 在 `backend/app/core/scheduler.py` 新增 `_job_strategy_zao_chen_shi_zi_xing_jian_hua_daily`（交易日 **17:23** `Asia/Shanghai`，内部调用 `execute_strategy(db, strategy_id="zao_chen_shi_zi_xing_jian_hua", as_of_date=today)`），并在 `start_scheduler()` 内与其它策略 Job 一并注册；异常与日志对齐早晨十字星 Job
- [x] T012 [P] 审阅 `frontend/src/components/BacktestResultDetail.vue`：若触发日/止损 Tooltip 为泛化文案，补充或并列「早晨十字星（简化版）」下 **T 与买入日相差一日、8% 止盈与 6% 止损** 的简短说明（避免与主策略移动止盈文案混淆）；若已有足够泛化说明则仅注释提交「已核对无需改」
- [x] T013 完整执行 `specs/026-早晨十字星简化版/quickstart.md` 自检清单（含 §3 定时任务可选观察）；实现全部完成后将 `specs/026-早晨十字星简化版/spec.md` 顶部 **状态** 更新为「已实现」（若团队流程要求）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**：无依赖，可立即开始  
- **Phase 2**：依赖 Phase 1 口径对齐；**阻塞** Phase 3～6  
- **Phase 3（US1）**：依赖 Phase 2；交付 **历史回测 MVP**  
- **Phase 4（US2）**：依赖 Phase 2（页面需策略已注册）；可与 Phase 3 并行由不同人开发，但建议 Phase 3 smoke 通过后再联调  
- **Phase 5（US3）**：依赖 Phase 2 代码文件存在；可与 Phase 4 并行  
- **Phase 6**：依赖 Phase 2；建议 Phase 3 完成后再合定时任务与明细文案

### User Story Dependencies

- **US1**：仅依赖 Phase 2  
- **US2**：依赖 Phase 2（展示层）；与 US1 弱耦合  
- **US3**：依赖 Phase 2 实现文件  

### Parallel Opportunities

- **T012** 可与 **T011** 并行（前端组件 vs 调度器文件）  
- **Phase 4** 与 **Phase 5** 可由两人并行（Vue vs 后端边界审查）

---

## Parallel Example：Phase 6

```text
# 可同时进行：
T011 修改 backend/app/core/scheduler.py
T012 修改 frontend/src/components/BacktestResultDetail.vue
```

---

## Implementation Strategy

### MVP First（仅 User Story 1）

1. 完成 Phase 1 + Phase 2（T001～T004）  
2. 完成 Phase 3（T005～T006），确认 **`POST /api/backtest/run` 历史回测**可用  
3. **暂停验收**：按 quickstart 核对明细字段  

### Incremental Delivery

4. Phase 4：选股页与导航  
5. Phase 5：数据边界加固  
6. Phase 6：定时任务 + 明细 Tooltip + 规格状态  

---

## Notes

- 任务描述中的路径均为仓库内相对路径（自项目根目录）  
- `strategy_id` 以 `spec.md` 为准；若实现阶段微调命名，须同步更新 `tasks.md`、`contracts/strategy-api.md` 与注册表  
- 当前 Git 分支为 `main` 时，`check-prerequisites.sh` 可能对分支名报错，不影响本 `tasks.md` 使用；执行 Spec 脚本时可设置 `SPECIFY_FEATURE=026-早晨十字星简化版`
