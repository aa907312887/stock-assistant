# Tasks：红三兵（`strategy_id`: `di_wei_lian_yang`，规格目录 `021-低位连阳`）

**Input**：`specs/021-低位连阳/`（[`spec.md`](./spec.md)、[`plan.md`](./plan.md)）  
**Prerequisites**：已阅读 `spec.md` 与 `plan.md`；无单独 `data-model.md` / `contracts/`（复用既有回测与日线模型）。

**说明**：前置脚本 `check-prerequisites.sh` 在分支名为 `main` 时可能报错「非 feature 分支」，**可忽略**；本任务列表以目录 `specs/021-低位连阳` 为准。

**Tests**：`plan.md` 要求新增 `pytest` 表驱动单测，下列含测试任务。

**Organization**：按用户故事（P1→P3）分阶段，任务格式严格为 `- [ ] [TaskID] [P?] [Story?] 描述（含路径）`。

## Format: `[ID] [P?] [Story] Description`

- **[P]**：可与同阶段其他 **[P]** 任务并行（不同文件、无未完成依赖）。
- **[Story]**：`[US1]` `[US2]` `[US3]` 对应 `spec.md` 中用户需求 1～3。

---

## Phase 1：Setup（共享准备）

**Purpose**：对齐规格与既有实现，避免口径漂移。

- [ ] T001 通读 `specs/021-低位连阳/spec.md` 与 `specs/021-低位连阳/plan.md`，列出 FR-002～FR-007 与代码模块对应表（自用检查清单即可，可不提交仓库）
- [ ] T002 [P] 在 `backend/app/services/strategy/strategies/zao_chen_shi_zi_xing.py` 中标注或记录「前窗弱势 + T 日均线/历史高 + 卖出仿真」应对齐的行号区间，供 `di_wei_lian_yang.py` 拷贝时对照

---

## Phase 2：Foundational（阻塞所有用户故事）

**Purpose**：策略可被注册与发现；未完成前不得宣称任一回测故事验收通过。

**⚠️ CRITICAL**：未完成本阶段前，不应合并完整回测逻辑（否则无法通过 `GET /api/strategies` 联调）。

- [ ] T003 新建 `backend/app/services/strategy/strategies/di_wei_lian_yang.py`：`DiWeiLianYangStrategy` 骨架、`strategy_id="di_wei_lian_yang"`、`_Params` dataclass、`describe()` 返回合法 `StrategyDescriptor`（可先填占位短文案）、`backtest`/`execute` 临时返回空结果以便 import 通过
- [ ] T004 在 `backend/app/services/strategy/registry.py` 中 `import DiWeiLianYangStrategy` 并在 `list_strategies()` 中于「早晨十字星」邻近插入实例
- [ ] T005 在 `backend/app/services/strategy/strategy_descriptions.py` 中增加键 `di_wei_lian_yang`，文案与 `spec.md` 三路买入及卖出参数一致

**Checkpoint**：`GET /api/strategies` 响应中含 `di_wei_lian_yang` 与展示名「低位连阳」。

---

## Phase 3：User Story 1 - 回测可选用「低位连阳」并得到可解释结果（优先级：P1）🎯 MVP

**Goal**：`POST /api/backtest/run` 使用 `strategy_id=di_wei_lian_yang` 可跑通全链路；交易含 `trigger_date`、`extra.pattern_path`、买入价与路径规则一致；卖出与早晨十字星一致。

**Independent Test**：仅启用本策略跑固定区间，检查路径 A（MA5 收盘买）、路径 B（次日开盘买）、止损/移动止盈与 `zao_chen_shi_zi_xing.py` 行为一致。

- [ ] T006 [US1] 在 `backend/app/services/strategy/strategies/di_wei_lian_yang.py` 中实现 `common_low_position_ok(bars_list, i, p)`（与 `zao_chen_shi_zi_xing.py` 前窗 + T 日 MA + cum_hist 逻辑逐行对齐并加中文注释）
- [ ] T007 [US1] 在同文件实现 `is_doji_bar`（或等价命名）及路径判定：T−2 阴 → 路径 A；否则先 B2 后 B1；路径 A 调用 `is_hammer_bar`（从 `zao_chen_shi_zi_xing.py` import）
- [ ] T008 [US1] 在同文件实现 `run_di_wei_lian_yang_backtest`：数据加载 `select` 字段与扩展日期区间对齐早晨十字星；主循环 `i>=9`、触发日落在 `[start_date,end_date]`；路径 A 找首次 `close>MA5`，路径 B 使用 `i+1` 日 `open` 买入；单仓 `last_block` 语义
- [ ] T009 [US1] 在同文件实现 `_simulate_exit_same_as_morning_star`（或等价私有函数）：从 `zao_chen_shi_zi_xing.py` 买入后持仓循环**逐行对齐**止损 8% 与 15%+5% 移动止盈；组装 `BacktestTrade.extra`（含 `pattern_path`、`exit_reason`、诊断字段）
- [ ] T010 [US1] 将 `DiWeiLianYangStrategy.backtest` 与 `execute` 接入 `run_di_wei_lian_yang_backtest`，`execute` 筛选 `buy_date == as_of_date` 与 `ZaoChenShiZiXingStrategy.execute` 同模式
- [ ] T011 [P] [US1] 新建 `backend/tests/test_di_wei_lian_yang.py`：表驱动测试覆盖十字星判定、卖出止损价与移动止盈触发（全路径形态可与后续补充）

**Checkpoint**：回测可产出闭合/未平仓交易，`extra.pattern_path` 可取 `star_like` / `red_three_soldiers` / `two_yang_sandwich_yin`。

---

## Phase 4：User Story 2 - 与「早晨十字星」边界清晰、可对外说明（优先级：P2）

**Goal**：策略描述完整；前端有选股页与悬浮说明；回测明细 Tooltip 能区分本策略触发日与买入日差异。

**Independent Test**：打开选股页与回测详情，核对中文说明与 Tooltip 含路径 A/B 与卖出参数；`describe()` 文本可读。

- [ ] T012 [US2] 在 `backend/app/services/strategy/strategies/di_wei_lian_yang.py` 中完善类与模块 docstring（`.cursor/rules/strategy-class-documentation.mdc`），并更新 `describe()` 的 `short_description`/`description`/`assumptions`/`risks` 为定稿中文
- [ ] T013 [P] [US2] 新建 `frontend/src/views/DiWeiLianYangView.vue`（参照 `frontend/src/views/ZaoChenShiZiXingView.vue`：标题、悬浮 Tooltip 能力说明、`pattern_path` 与三日列展示、执行/列表行为）
- [ ] T014 [US2] 在 `frontend/src/router/index.ts` 注册子路由 `strategy/di-wei-lian-yang`，在 `frontend/src/views/Layout.vue` 侧栏增加「低位连阳」菜单项
- [ ] T015 [P] [US2] 更新 `frontend/src/components/BacktestResultDetail.vue` 中触发日/收益率相关 Tooltip 文案，纳入「低位连阳」及路径 A（MA5）与路径 B（次日开盘）说明

**Checkpoint**：浏览器可访问选股页且与规格口径一致；回测详情 Tooltip 不误导用户。

---

## Phase 5：User Story 3 - 数据不完整时行为可预期（优先级：P3）

**Goal**：缺字段、窗口不足、`high==low` 等情况下不误触发；缺 `cum_hist_high` 列时错误信息与早晨十字星同类。

**Independent Test**：单测或手工构造缺量数据，确认 `continue` 或不产出交易；数据库缺列时抛指引性 `RuntimeError`。

- [ ] T016 [US3] 在 `backend/app/services/strategy/strategies/di_wei_lian_yang.py` 中逐项核对：开高低收/均线/`cum_hist_high` 无效时跳过；`extended_start/end` 边界与早晨十字星一致；缺列 `RuntimeError` 文案与早晨十字星同运维前缀
- [ ] T017 [P] [US3] 在 `backend/tests/test_di_wei_lian_yang.py` 中补充数据缺失、`high==low` 十字星、区间不足 `i<9` 等用例

**Checkpoint**：无静默错误信号；与 `spec.md` 边界情况章节一致。

---

## Phase 6：Polish & 横切事项

**Purpose**：定时任务、规格状态、验证文档与回归。

- [ ] T018 在 `backend/app/core/scheduler.py` 中新增 `_job_strategy_di_wei_lian_yang_daily` 并在 `start_scheduler()` 以 `CronTrigger`（建议 **17:21** 上海时区，`replace_existing=True`）注册，内联调用 `execute_strategy(db, strategy_id="di_wei_lian_yang", as_of_date=today)`，异常处理对齐早晨十字星 Job
- [ ] T019 [P] 实现完成后将 `specs/021-低位连阳/spec.md` 顶部**状态**改为「已实现」
- [ ] T020 [P] 新建 `specs/021-低位连阳/quickstart.md`：列出 `GET /api/strategies`、`POST /api/backtest/run`、`POST /api/strategies/di_wei_lian_yang/execute`（路径以项目实际为准）及前端页面验证步骤
- [ ] T021 在仓库根或 `backend/` 下执行 `pytest backend/tests/services/strategy/test_di_wei_lian_yang.py` 全绿，并任选一日回测烟测 `strategy_id=di_wei_lian_yang`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** → **Phase 2** → **Phase 3（US1）** → **Phase 4（US2）** → **Phase 5（US3）** → **Phase 6**  
- **US2** 依赖 **US1** 的 `backtest`/`execute` 行为稳定后再打磨文案与前端展示（可先并行 T012 与 T008，但联调须在 T010 后）。

### User Story Dependencies

- **US1**：仅依赖 Phase 2。  
- **US2**：依赖 US1 可运行回测与 `describe()` 有实质内容（T012 可与 T011 合并为同一 MR 内连续提交）。  
- **US3**：依赖 US1 主体循环已落地，可在同一 MR 内与 US1 测试一并完成（T016～T017）。

### Parallel Opportunities

- **T002** 与 **T001** 可并行（不同关注点）。  
- **T011** 与 **T013**、**T015** 在 US1 核心合并前可提前起草，但 **T013/T014** 需 API 稳定后联调。  
- **T017** 与 **T016** 可并行（测试与代码审计）。  
- **T019** 与 **T020** 可并行。

---

## Parallel Example：User Story 1

```bash
# 实现完成前后端未就绪时，可先跑：
cd backend && pytest backend/tests/services/strategy/test_di_wei_lian_yang.py -q
```

---

## Implementation Strategy

### MVP（仅 User Story 1）

1. 完成 Phase 1～2。  
2. 完成 Phase 3（T006～T011）。  
3. **STOP**：`POST /api/backtest/run` + pytest 验证通过后再做选股页（US2）。

### 增量交付

1. MVP 通过后交付 US2（页面 + Tooltip + describe 定稿）。  
2. 补充 US3 边界与测试。  
3. Phase 6：定时任务 + quickstart + 规格状态。

---

## 任务统计

| 阶段 | 任务数 |
|------|--------|
| Phase 1 | 2 |
| Phase 2 | 3 |
| Phase 3（US1） | 6 |
| Phase 4（US2） | 4 |
| Phase 5（US3） | 2 |
| Phase 6 | 4 |
| **合计** | **21** |

**各用户故事任务数**：US1 为 6 条（T006～T011）；US2 为 4 条（T012～T015）；US3 为 2 条（T016～T017）。  
**含 [P] 可并行**：T002、T011、T013、T015、T017、T019、T020（共 7 处标记，视人手与依赖微调）。

**格式校验**：本文件全部任务行均以 `- [ ] Tnnn` 开头，含 **Task ID**、**文件路径**；用户故事阶段任务均含 **[USn]** 标签。
