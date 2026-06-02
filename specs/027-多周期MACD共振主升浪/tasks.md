# Tasks：多周期 MACD 共振主升浪

**Input**：设计文档位于 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/specs/027-多周期MACD共振主升浪/`（`spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/strategy-api.md`、`quickstart.md`）

**Tests**：`plan.md` 要求 `pytest` 覆盖买入窗口与四类平仓；测试任务纳入 Phase 2，与策略模块同步交付。

**用户补充**：须将新策略纳入**历史回测**可选列表并成功跑通——通过 **策略注册表 + `StockStrategy.backtest()`** 接入 `POST /api/backtest/run`，**无**单独回测白名单配置。

**首期范围**（见 `plan.md`）：**仅历史回测 MVP**；**不**做策略选股页、**不**注册 APScheduler Job（列为 Backlog）。

**Organization**：按用户故事（spec.md）分阶段；任务含明确文件路径。

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1：Setup（同步上下文）

**Purpose**：开发前对齐口径与标识，避免实现漂移。

- [x] T001 通读 `specs/027-多周期MACD共振主升浪/spec.md`、`plan.md`、`research.md`，确认 `strategy_id=duo_zhou_qi_macd_gong_zhen`、D6 收盘买入、涨幅/止损/移动止盈阈值（10%/7%/3%）、平仓优先级及周/月对齐规则（`trade_week_end` / `trade_month_end` ≤ T_buy 最近一根）

---

## Phase 2：Foundational（阻塞所有用户故事的后端基础）

**Purpose**：完成内置策略实现、注册与单测后，`GET /api/strategies` 与 `POST /api/backtest/run` 才能解析到新策略；此为 MVP 必经路径。

**⚠️ CRITICAL**：未完成本阶段前，不应开始 Polish 中的可选前端项。

- [x] T002 新建 `backend/app/services/strategy/strategies/duo_zhou_qi_macd_gong_zhen.py`：实现 `_Params`（`gain_filter_pct=0.10`、`arm_profit_pct=0.10`、`trailing_drawdown_pct=0.03`、`stop_loss_pct=0.07`）、纯函数 `six_increasing_red_ends_at`、`gain_filter_ok`、`multi_tf_macd_red`（`bisect` 取周/月最近 bar）、`simulate_exit_after_buy`（**仅 −7% 为止损**；**红转绿/三连跌为无条件卖出，不检查盈亏**，盈利未满 10% 亦卖；再判移动止盈；峰值仅武装后最高收盘价；`exit_reason` 用 `sell_macd_red_to_green` / `sell_three_down_days`）、`run_duo_zhou_qi_macd_gong_zhen_backtest`（批量加载日/周/月 `macd_hist`、剔除 ST、单标的未平仓不重复开仓、`trigger_date=buy_date=D6`、买入价=收盘价、`extra` 按 `data-model.md`）；类 `DuoZhouQiMacdGongZhenStrategy` 实现 `describe()` / `backtest()` / `execute()`（首期 `execute` 返回空候选并说明仅支持回测）；类顶**简体中文 docstring**符合 `.cursor/rules/strategy-class-documentation.mdc`
- [x] T003 在 `backend/app/services/strategy/registry.py` 中 `import DuoZhouQiMacdGongZhenStrategy` 并在 `list_strategies()` 末尾（或与其它 MACD/均线类策略相邻位置）追加实例
- [x] T004 在 `backend/app/services/strategy/strategy_descriptions.py` 的 `STRATEGY_DESCRIPTIONS` 中新增键 `duo_zhou_qi_macd_gong_zhen`，撰写日周月共振、六日递增红柱、D6 收盘买、四类平仓要点（供模拟/列表 `strategy_description` 非空）
- [x] T005 [P] 新建 `backend/tests/test_duo_zhou_qi_macd_gong_zhen.py`，覆盖 `plan.md` §6 用例（含 **`test_exit_macd_red_to_green_while_profitable_under_10pct`**：盈利未满 10% 仍须卖）；`pytest` 全部通过

**Checkpoint**：`pytest backend/tests/test_duo_zhou_qi_macd_gong_zhen.py -q` 通过；后端启动后 `GET /api/strategies` 出现「多周期 MACD 共振主升浪」。

---

## Phase 3：User Story 1 — 历史回测可选用且结果可复核（优先级：P1）🎯 MVP

**Goal**：用户在智能回测中选择本策略并提交任务后，能生成买卖明细；买入为 D6 收盘价，离场原因可区分四类规则。

**Independent Test**：按 `specs/027-多周期MACD共振主升浪/quickstart.md` §3 调用 `POST /api/backtest/run`；核对 `trigger_date==buy_date`、买入价为收盘价、`extra.exit_reason` 合法。

- [x] T006 [US1] 审阅 `backend/app/services/backtest/backtest_engine.py`：确认回测仅依赖 `get_strategy(body.strategy_id)`，**无需**新增 `strategy_id` 分支；确认 `simulation_engine.py` 若拉取本策略亦同路径
- [x] T007 [US1] 执行 `specs/027-多周期MACD共振主升浪/quickstart.md` **§3.1、§3.2**（`GET /api/strategies`、`POST /api/backtest/run`），确认任务落库；若有 `closed` 交易，抽查 `trigger_date`、`buy_price`、`extra.d1_date` 与 `exit_reason` 符合规格（注册与 `describe()` 已本地验证；完整回测需 MySQL + Token 手测）

**Checkpoint**：**历史回测 MVP** 达成 — 前端 `BacktestConfigPanel.vue` 自 `/api/strategies` 动态拉取列表时自动包含本策略（无需硬编码 `strategy_id`）。

---

## Phase 4：User Story 2 — 策略说明可区分其它 MACD 策略（优先级：P2）

**Goal**：用户通过 `GET /api/strategies/{id}` 或列表 `short_description` 理解多周期共振、D6 收盘买、移动止盈与三类止损，不与「仅日线 MACD」或「T+1 开盘买」策略混淆。

**Independent Test**：阅读 `describe()` 返回的 `description` / `assumptions`，对照 spec 要点清单逐项勾选。

- [x] T008 [US2] 在 `backend/app/services/strategy/strategies/duo_zhou_qi_macd_gong_zhen.py` 的 `describe()` 中核对：`short_description` 与 `contracts/strategy-api.md` 一致；正文明确**周/月 MACD 红柱**、**六日递增红柱**、**D6 收盘买入**（非次日开盘）、**+10% 后 3% 移动止盈**；`route_path` 首期为 `None` 或省略
- [x] T009 [US2] 调用 `GET /api/strategies/duo_zhou_qi_macd_gong_zhen`，人工确认响应 JSON 满足 US2 验收场景（可与仅日线策略说明对比差异）

---

## Phase 5：User Story 3 — 数据不足时可靠跳过（优先级： P3）

**Goal**：缺日/周/月 MACD、不足六日递增红柱、无效 OHLC 时不误报买入；全市场扫描不 500。

**Independent Test**：`pytest` 覆盖缺失周线、D0 非绿、仅 5 根红柱；代码审查主循环 `skipped_count` 与 `continue` 分支。

- [x] T010 [US3] 在 `backend/app/services/strategy/strategies/duo_zhou_qi_macd_gong_zhen.py` 逐项核对：`macd_hist`/`open`/`close` 无效跳过；周/月 bar 不存在或 `hist` 不可比跳过；`i<6` 不扫描；D6 无有效收盘价不买入、不顺延 D7；日志含 `strategy_id` 便于检索
- [x] T011 [US3] 在 `backend/tests/test_duo_zhou_qi_macd_gong_zhen.py` 补充（若 T005 未覆盖）：仅 5 根递增红柱不触发、`macd_hist` 为 `None` 的日线跳过；`pytest` 通过

---

## Phase 6：Polish & Cross-Cutting Concerns

**Purpose**：回测明细可读性、规格收尾、全量自检。

- [x] T012 [P] 审阅 `frontend/src/components/BacktestResultDetail.vue`：为 `exit_reason` 增加映射（`stop_loss_7pct`、`sell_macd_red_to_green`、`sell_three_down_days`、`trailing_take_profit_3pct`；后两者文案须体现**不论盈亏**，见 `contracts/strategy-api.md` §5）
- [x] T013 完整执行 `specs/027-多周期MACD共振主升浪/quickstart.md` 自检清单（§2 单测 + §3 API + §5 人工抽查）；实现完成后将 `specs/027-多周期MACD共振主升浪/spec.md` 顶部**状态**更新为「已实现」（若团队流程要求）

---

## Phase 7：Backlog（Phase 2 产品扩展，**不阻塞** MVP）

**Purpose**：`plan.md` 列出的后续能力；本 tasks 迭代**可不执行**。

- [ ] T014 [P] 实现 `execute()` 全市场扫描（复用 `six_increasing_red_ends_at` 等），写入既有策略选股快照表；`as_of_date` 为候选 D6
- [ ] T015 [P] 新建 `frontend/src/views/DuoZhouQiMacdGongZhenView.vue`、在 `frontend/src/router/index.ts` 与 `frontend/src/views/Layout.vue` 增加路由/菜单；页内 `el-tooltip` 说明能力边界（与 `spec.md` 一致）
- [ ] T016 在 `backend/app/core/scheduler.py` 注册 `_job_strategy_duo_zhou_qi_macd_gong_zhen_daily`（**17:24** `Asia/Shanghai`，调用 `execute_strategy(..., strategy_id="duo_zhou_qi_macd_gong_zhen")`）；失败不重试、打 error 日志

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**：无依赖，立即开始  
- **Phase 2**：依赖 Phase 1；**阻塞** Phase 3～6  
- **Phase 3（US1）**：依赖 Phase 2  
- **Phase 4（US2）**：依赖 Phase 2（`describe()` 在 T002）  
- **Phase 5（US3）**：依赖 Phase 2；可与 Phase 4 并行  
- **Phase 6**：依赖 Phase 3 冒烟通过；T012 可与 T011 并行  
- **Phase 7**：依赖 Phase 2～3 稳定后按需启动  

### User Story Dependencies

- **US1**：仅依赖 Phase 2  
- **US2**：依赖 Phase 2 `describe()` / T004  
- **US3**：依赖 Phase 2 实现文件  

### Parallel Opportunities

- **T005** 与 **T002** 可交错：先写纯函数 + 测试，再补 `run_*_backtest` 与类（同文件需注意合并顺序）  
- **T012** 与 **T011** 可并行（前端 vs 测试）  
- **Phase 7** 中 **T014** 与 **T015** 可并行（后端 execute vs 前端页）

---

## Parallel Example：Phase 2

```text
# 推荐顺序：
T002 先实现纯函数 + simulate_exit（可供 T005 引用）
T005 并行或紧随：backend/tests/test_duo_zhou_qi_macd_gong_zhen.py
T003、T004 在 T002 类与 strategy_id 稳定后注册
```

---

## Parallel Example：Phase 6

```text
T012 修改 frontend/src/components/BacktestResultDetail.vue
T011 修改 backend/tests/test_duo_zhou_qi_macd_gong_zhen.py
# 可同时进行
```

---

## Implementation Strategy

### MVP First（仅 User Story 1）

1. 完成 Phase 1 + Phase 2  
2. 完成 Phase 3（T006–T007）  
3. **停止并验证**：`quickstart.md` §3 回测跑通  
4. 再按需完成 Phase 4～6  

### Incremental Delivery

1. Phase 2 → 回测引擎可调用（US1）  
2. Phase 4 → 产品说明可读（US2）  
3. Phase 5 → 边界可靠（US3）  
4. Phase 6 → 明细 Tooltip + 规格状态  
5. Phase 7 → 选股页 + 定时任务（产品确认后）  

### Suggested MVP Scope

- **包含**：T001–T007（Setup + Foundational + US1）  
- **建议同期完成**：T005（单测）、T008–T011（US2/US3 轻量验收）  
- **可选**：T012–T013  
- **不含**：T014–T016（Backlog）  

---

## Notes

- 所有百分比口径为**相对价格**（10%/7%/3%），非 tick  
- MACD 颜色仅看 `macd_hist`：`>0` 红柱，`≤0` 或缺失为绿/不可比  
- 买入日 **D6** 的 `trigger_date` 与 `buy_date` **相同**  
- 首期**不**修改 `backend/app/core/scheduler.py`（除非执行 Phase 7）
