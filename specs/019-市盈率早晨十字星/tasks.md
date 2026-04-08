# Tasks: 市盈率早晨十字星

**输入**: `specs/019-市盈率早晨十字星/`  
**前置条件**: plan.md ✅, spec.md ✅, data-model.md ✅, contracts/ ✅

## 格式说明

- **[P]**: 可并行执行（不同文件，无依赖）
- **[Story]**: 对应 spec.md 中的用户需求（US1/US2/US3）
- 每个任务包含精确文件路径

---

## Phase 1: 基础准备

**目的**: 确认现有代码结构，为新策略做好准备

- [ ] T001 阅读 `backend/app/services/strategy/strategies/zao_chen_shi_zi_xing.py`，理解 `_run_backtest()` 的形态判断逻辑，确认可提取的边界
- [ ] T002 [P] 阅读 `backend/app/services/strategy/strategy_base.py`，确认 `StockStrategy`、`BacktestTrade`、`StrategyCandidate`、`StrategyExecutionResult` 的完整签名
- [ ] T003 [P] 阅读 `backend/app/models/stock_financial_report.py`，确认 `roe`、`report_date`、`ann_date` 字段类型与约束

**检查点**: 已掌握现有策略框架与数据模型，可开始实现

---

## Phase 2: 基础重构（阻塞前置）

**目的**: 将早晨十字星形态判断逻辑提取为可复用函数，供新策略调用

**⚠️ 重要**: 此阶段完成前不得开始 US1/US2

- [ ] T004 在 `backend/app/services/strategy/strategies/zao_chen_shi_zi_xing.py` 中，将 `_run_backtest()` 内的形态判断核心逻辑提取为模块级函数 `run_morning_star_backtest(db, *, start_date, end_date, p, extra_filter=None)`，`extra_filter` 为可选回调，接收 `(stock_code, trigger_bar)` 返回 `bool`，默认 `None` 表示不过滤；原 `ZaoChenShiZiXingStrategy.backtest()` 改为调用此函数（行为不变）
- [ ] T005 运行现有测试确认重构未破坏原策略：`cd backend && pytest tests/ -k "zao_chen" -v`（若无测试则手动验证策略注册表可正常加载）

**检查点**: `ZaoChenShiZiXingStrategy` 行为不变，`run_morning_star_backtest` 可被外部调用

---

## Phase 3: 用户需求 1 — 回测功能（优先级：P1）🎯 MVP

**目标**: 用户可在回测中选择「市盈率早晨十字星」策略，系统在三个条件同时满足时产生信号

**独立验证**: 运行回测，确认信号数量少于单独使用「早晨十字星」；检查 `extra` 中含 `trigger_pe_percentile` 与 `trigger_roe`

### 实现

- [ ] T006 [US1] 创建策略文件 `backend/app/services/strategy/strategies/pe_zao_chen_shi_zi_xing.py`，写入完整类注释（按 CLAUDE.md 策略注释规范），定义 `PeZaoChenShiZiXingStrategy` 类，`strategy_id = "pe_zao_chen_shi_zi_xing"`，实现 `describe()` 方法返回完整 `StrategyDescriptor`
- [ ] T007 [US1] 在 `pe_zao_chen_shi_zi_xing.py` 中实现模块级函数 `_get_latest_roe(session, stock_code: str, as_of_date: date) -> tuple[float | None, date | None]`，查询 `stock_financial_report` 表，条件：`stock_code = ?` AND `report_date <= as_of_date` AND `roe IS NOT NULL`，按 `report_date DESC LIMIT 1`
- [ ] T008 [US1] 在 `pe_zao_chen_shi_zi_xing.py` 中实现 `backtest(self, *, start_date: date, end_date: date) -> BacktestResult`：调用 `run_morning_star_backtest()`，通过 `extra_filter` 回调注入 PE 百分位（`< 10.0`）与 ROE（`> 15.0`）过滤；在 `BacktestTrade.extra` 中新增 `trigger_pe_percentile`、`trigger_roe`、`trigger_roe_report_date` 字段
- [ ] T009 [US1] 在 `backend/app/services/strategy/registry.py` 中导入并注册 `PeZaoChenShiZiXingStrategy`，插入位置紧跟 `ZaoChenShiZiXingStrategy()` 之后
- [ ] T010 [US1] 在 `backend/app/services/strategy/strategy_descriptions.py` 的 `STRATEGY_DESCRIPTIONS` 字典中添加 `"pe_zao_chen_shi_zi_xing"` 键，内容包含买入条件（形态+PE<10%+ROE>15%）、卖出条件（止损8%、移动止盈15%+5%）、关键参数

**检查点**: 策略可通过 `get_strategy("pe_zao_chen_shi_zi_xing")` 获取；回测可运行并返回 `BacktestResult`；信号数量少于「早晨十字星」

---

## Phase 4: 用户需求 2 — 策略选股功能（优先级：P1）

**目标**: 用户在策略选股页面可选择「市盈率早晨十字星」，系统返回当日满足三个条件的标的列表

**独立验证**: 调用 `execute(as_of_date=某日)`，返回的每只标的均满足形态 + PE < 10% + ROE > 15%

### 实现

- [ ] T011 [US2] 在 `pe_zao_chen_shi_zi_xing.py` 中实现 `execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult`：复用 `ZaoChenShiZiXingStrategy.execute()` 的结构，在形态判断后叠加 PE 百分位与 ROE 过滤；`StrategyCandidate.summary` 中新增 `pe_percentile`、`roe`、`roe_report_date` 字段
- [ ] T012 [US2] 在 `execute()` 中实现批量 ROE 预加载优化：对所有候选标的一次性查询最近一期 ROE，避免逐标的查询（参考 `data-model.md` 中的批量查询 SQL）

**检查点**: `execute()` 可运行；结果列表中每只标的均可人工核验三个条件；空结果时返回空列表而非报错

---

## Phase 5: 用户需求 3 — 数据缺失处理（优先级：P3）

**目标**: PE 百分位或 ROE 数据缺失时，跳过该标的而非产生误信号

**独立验证**: 构造 `pe_percentile = NULL` 或无财报记录的场景，确认不产生信号

### 实现

- [ ] T013 [US3] 在 `backtest()` 与 `execute()` 的过滤逻辑中，确认以下边界处理已覆盖：`pe_percentile IS NULL` → 跳过；`pe_percentile >= 10.0` → 跳过；`roe IS NULL` 或无财报记录 → 跳过；`roe <= 15.0` → 跳过；在日志中记录跳过原因（`logger.debug`）

**检查点**: 缺失数据场景不产生误信号；日志可追溯跳过原因

---

## Phase 6: 收尾与交叉关注点

**目的**: 文档同步、验收确认

- [ ] T014 [P] 更新 `specs/019-市盈率早晨十字星/spec.md`，将状态从「草稿」改为「已实现」
- [ ] T015 运行完整测试套件确认无回归：`cd backend && pytest tests/ -v`
- [ ] T016 [P] 按 `quickstart.md` 中的对比验证步骤，运行「早晨十字星」与「市盈率早晨十字星」回测，确认 SC-002（信号数量可见减少）

---

## 依赖关系

### 阶段依赖

- **Phase 1**（基础准备）: 无依赖，立即开始
- **Phase 2**（基础重构）: 依赖 Phase 1 完成 — **阻塞 US1/US2/US3**
- **Phase 3**（US1 回测）: 依赖 Phase 2 完成
- **Phase 4**（US2 选股）: 依赖 Phase 2 完成，可与 Phase 3 并行
- **Phase 5**（US3 缺失处理）: 依赖 Phase 3 + Phase 4 完成
- **Phase 6**（收尾）: 依赖所有用户需求阶段完成

### 用户需求依赖

- **US1（回测）**: Phase 2 完成后可开始，无其他依赖
- **US2（选股）**: Phase 2 完成后可开始，可与 US1 并行
- **US3（缺失处理）**: US1 + US2 完成后验证

### 并行机会

- T001、T002、T003 可并行（Phase 1 内）
- T006、T007 可并行（同文件但不同函数，注意合并冲突）
- T009、T010 可并行（不同文件）
- Phase 3 与 Phase 4 可并行（US1 与 US2 独立）

---

## 并行示例：Phase 3 + Phase 4

```
# Phase 2 完成后，可同时启动：
任务 A: T006 → T007 → T008（回测实现）
任务 B: T011 → T012（选股实现）

# 同时进行：
任务 C: T009（注册策略）
任务 D: T010（添加描述）
```

---

## 实现策略

### MVP（仅 US1）

1. 完成 Phase 1：基础准备
2. 完成 Phase 2：基础重构（关键，阻塞后续）
3. 完成 Phase 3：US1 回测功能
4. **停止并验证**：回测可运行，信号数量少于「早晨十字星」
5. 可演示/上线

### 完整交付

1. Phase 1 + Phase 2 → 基础就绪
2. Phase 3（US1）→ 独立验证 → 回测可用
3. Phase 4（US2）→ 独立验证 → 选股可用
4. Phase 5（US3）→ 边界处理验证
5. Phase 6 → 收尾

---

## 备注

- `[P]` 任务操作不同文件，无依赖，可并行
- `[Story]` 标签对应 spec.md 中的用户需求编号
- Phase 2 的重构是关键路径，必须优先完成
- 每个检查点后可独立验证，无需等待全部完成
- 提交粒度：每个任务或逻辑组完成后提交
