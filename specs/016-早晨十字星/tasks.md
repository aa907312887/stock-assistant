# Tasks：早晨十字星（回测内置策略）

**Input**：设计文档位于 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/specs/016-早晨十字星/`（`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/strategy-api.md`、`quickstart.md`）

**Tests**：规格未强制 TDD；本清单**不包含**独立测试任务，实现中可在锤头判定处按需补单元测试。

**格式**：`[ID] [P?] [Story?] 描述（含确切文件路径）`

---

## Phase 1：Setup（共享准备）

**Purpose**：对齐文档与参考实现，无代码变更或仅只读。

- [x] T001 通读 `specs/016-早晨十字星/plan.md`、`specs/016-早晨十字星/spec.md`、`specs/016-早晨十字星/research.md`，确认 `strategy_id=zao_chen_shi_zi_xing`、索引 `i≥9`、锤头与 T−9…T−3 窗口口径
- [x] T002 [P] 精读 `backend/app/services/strategy/strategies/shu_guang_chu_xian.py` 中 `_run_backtest` 的数据查询、`ST` 过滤、`last_block` 单仓约束、买入扫描与卖出循环（止损/止盈），标出应对齐的行号范围供复制对照
- [x] T003 [P] 对照 `specs/016-早晨十字星/contracts/strategy-api.md`，确认对外不新增路由、仅扩展 `GET /api/strategies` 与 `POST /api/backtest/run` 的 `strategy_id` 取值

---

## Phase 2：Foundational（阻塞项，先于各用户故事）

**Purpose**：建立策略文件骨架、锤头判定与注册表，使 `GET /api/strategies` 能列出「早晨十字星」；完整回测逻辑在 Phase 3 完成。

**⚠️**：未完成本 Phase 前，不应宣称 US1 已交付。

- [x] T004 新建 `backend/app/services/strategy/strategies/zao_chen_shi_zi_xing.py`：类 `ZaoChenShiZiXingStrategy`、`strategy_id="zao_chen_shi_zi_xing"`、`_Params` dataclass、`describe()` 返回 `StrategyDescriptor`（名称「早晨十字星」、`route_path="/strategy/zao-chen-shi-zi-xing"`）、模块与类 docstring 符合 `.cursor/rules/strategy-class-documentation.mdc`
- [x] T005 在同一文件实现静态锤头判定（或模块级函数），严格遵循 `specs/016-早晨十字星/research.md` 中「下影/上影/实体上端」数值规则，输入为含 `open, high, low, close` 的 bar（或 float 四元组）
- [x] T006 在同一文件为 `backtest()`/`_run_backtest` 提供临时实现：`backtest` 调用 `_run_backtest` 并返回 `BacktestResult(trades=[])`，待 T007 填满
- [x] T007 在 `backend/app/services/strategy/registry.py` 中 `import ZaoChenShiZiXingStrategy` 并将 `ZaoChenShiZiXingStrategy()` 加入 `list_strategies()`（顺序紧挨 `ShuGuangChuXianStrategy()` 为宜）

**Checkpoint**：启动应用后 `GET /api/strategies` 可见 `zao_chen_shi_zi_xing`；`POST /api/backtest/run` 不因策略缺失而 404（结果可为空）。

---

## Phase 3：User Story 1 — 回测可选用早晨十字星并得到可解释结果（优先级：P1）🎯 MVP

**Goal**：完整形态判定 + 放量/高位 + 与曙光一致的买卖仿真；`trigger_date` 为第三根阳线日 **T**；同一标的未平仓后不再开仓。

**Independent Test**：仅选本策略跑短区间回测，核对交易明细中 `trigger_date` 为阳线完成日，买入不早于该信号逻辑；单仓约束生效。

### Implementation for User Story 1

- [x] T008 [US1] 在 `backend/app/services/strategy/strategies/zao_chen_shi_zi_xing.py` 的 `_run_backtest` 中：`select` 增加 `StockDailyBar.high`、`StockDailyBar.low`；`extended_start`/`extended_end` 与曙光初现一致；主循环 `i` 从 `9` 起；以 `bars_list[i]` 为 **T**，实现 FR-002/003/004/005/006（含 T−9…T−3 弱势与累计跌幅、三根 K 线、锤头 + 涨跌幅 ≤1%、T 日放量与 `cum_hist_high`）
- [x] T009 [US1] 在同一 `_run_backtest` 中复制并校准 `shu_guang_chu_xian.py` 的买入（自 `i` 起首次 `close>MA5`）与卖出仿真（**本策略** `stop_loss_8pct` / 买入×0.92，**异于**曙光初现之 10%；`take_profit_10pct`、`unclosed`）、`last_block` 行为；`BacktestTrade.trigger_date=bar_t.trade_date`；`extra` 含 `exit_reason` 及便于审计的要点字段
- [x] T010 [US1] 在同一文件实现 `execute()`：与 `ShuGuangChuXianStrategy.execute` 相同模式（`as_of_date` 单日 `_run_backtest`，仅保留 `buy_date==as_of_date` 的候选并组装 `StrategyCandidate`/`StrategySignal`）
- [x] T011 [US1] 按 `specs/016-早晨十字星/quickstart.md` 用本地接口验证：`GET /api/strategies` 含本策略；`POST /api/backtest/run` 提交 `strategy_id=zao_chen_shi_zi_xing`；任务完成后检查交易明细中 `trigger_date` 与策略名称

**Checkpoint**：US1 单独验收通过即构成 MVP。

---

## Phase 4：User Story 2 — 与曙光初现可区分、可核对（优先级：P2）

**Goal**：说明文字与输出字段能区分两策略；`trigger_date` 语义清晰。

**Independent Test**：对比两策略在同一区间的任务记录与明细，`strategy_id`/名称不同；明细中触发日为第三根阳线日。

### Implementation for User Story 2

- [x] T012 [US2] 在 `backend/app/services/strategy/strategies/zao_chen_shi_zi_xing.py` 的 `describe()` 中更新 `short_description`、`description`、`assumptions`，明确「三根 K 线 / 锤头 / 跌势窗口 T−9…T−3」与「曙光初现单日阳线」差异，及买卖规则与曙光一致
- [x] T013 [P] [US2] 在 `_run_backtest` 写入的 `extra` 中增加可核对字段（如 `pattern_yin_date`、`pattern_hammer_date`、`pattern_yang_date` 或 ISO 字符串），与 `specs/016-早晨十字星/spec.md` 中关键实体一致
- [x] T014 [P] [US2] 可选：在 `frontend/src/components/BacktestResultDetail.vue` 中扩展触发日 `el-tooltip` 文案，提及「早晨十字星」与第三根阳线日（与现有曙光说明并列，保持简短）

---

## Phase 5：User Story 3 — 数据不适用时跳过（优先级：P3）

**Goal**：缺字段、无效数值时不误触发。

**Independent Test**：对缺 `volume`、缺均线、缺 `cum_hist_high` 的 bar 路径走查，均为 `continue`。

### Implementation for User Story 3

- [x] T015 [US3] 在 `backend/app/services/strategy/strategies/zao_chen_shi_zi_xing.py` 中逐项核对：凡 `open`/`close`/`high`/`low`、`volume`、`ma5`/`ma10`/`ma20`、`cum_hist_high` 及锤头所需价格在任一步无效则跳过该 `i`，行为与 `shu_guang_chu_xian.py` 一致；缺 `cum_hist_high` 时错误提示可复用曙光迁移文案模式（若本策略单独抛错须含迁移指引）

---

## Phase 6：Polish & Cross-Cutting

**Purpose**：规格同步、交付前自检。

- [x] T016 [P] 在 `specs/016-早晨十字星/spec.md` 增加「策略标识」小节（`strategy_id`、`展示名称`），与 `specs/016-早晨十字星/contracts/strategy-api.md` 一致，满足 Spec 驱动同步
- [x] T017 全量执行 `specs/016-早晨十字星/quickstart.md` 自检清单；若有 SC-003 人工样本计划，在备注中记录待办或链接

---

## Dependencies & Execution Order

### Phase Dependencies

| Phase | 依赖 |
|-------|------|
| Phase 1 | 无 |
| Phase 2 | Phase 1 建议完成（读懂参考代码） |
| Phase 3（US1） | Phase 2 必须完成 |
| Phase 4（US2） | Phase 3 中 `describe`/`extra` 可增量强化，建议 T008–T010 完成后做 T012–T014 |
| Phase 5（US3） | 与 Phase 4 可并行，但依赖于 T008 主体逻辑已存在 |
| Phase 6 | US1 完成后即可开始 T016；T017 依赖功能可用 |

### User Story Dependencies

- **US1**：仅依赖 Phase 2；无其它故事前置。
- **US2**：依赖 US1 核心回测与注册；可与 US3 并行由不同人处理。
- **US3**：依赖 US1 主循环存在，便于走查分支。

### Within-Story Order（US1）

T008（形态与数据）→ T009（买卖与单仓）→ T010（execute）→ T011（联调）。

### Parallel Opportunities

- T002 ∥ T003；T005 ∥ T006（若拆人：一人锤头 + 一人骨架）；T013 ∥ T014；T016 ∥ 部分文档审阅。
- US2 文案（T012–T014）与 US3 走查（T015）可在 T008 合并后并行。

---

## Parallel Example：User Story 1

```text
# 串行关键路径：
T008 → T009 → T010 → T011

# T008 内部可先实现「仅形态+过滤无卖出」再 T009 接卖出，仍属同一任务文件内顺序。
```

---

## Implementation Strategy

### MVP（仅 User Story 1）

1. 完成 Phase 1 → Phase 2（T001–T007）
2. 完成 Phase 3（T008–T011）
3. **停止并验收**：回测可选早晨十字星、`trigger_date` 正确

### 增量交付

1. MVP 通过后 → Phase 4（T012–T014）增强可区分性与 UI 提示
2. Phase 5（T015）加固数据边界
3. Phase 6（T016–T017）规格与 quickstart 闭环

### 多人并行建议

- 开发者 A：T008–T010
- 开发者 B：T005 锤头单测（若后续补充）+ T015 走查 + T014 前端文案

---

## Notes

- 所有实现任务默认修改 `backend/app/services/strategy/strategies/zao_chen_shi_zi_xing.py` 与 `backend/app/services/strategy/registry.py`，除非任务另行指定路径。
- `[P]` 表示与其它标注 `[P]` 的任务可并行（不同文件或无依赖）。

---

## Task Summary

| 指标 | 数量 |
|------|------|
| 总任务数 | 17 |
| Phase 1 | 3 |
| Phase 2 | 4 |
| US1 | 4 |
| US2 | 3 |
| US3 | 1 |
| Polish | 2 |

**建议 MVP 范围**：Phase 1–3（T001–T011）。

**格式校验**：本文件全部任务均采用 `- [x] Tnnn …`  checklist，用户故事阶段任务含 `[US1]`/`[US2]`/`[US3]`，并含确切文件路径。
