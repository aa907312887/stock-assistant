# 调研结论：智能回测

**日期**: 2026-03-26 | **规格**: `./spec.md`

## 决策 1：异步回测执行方案

**决策**：使用 `threading.Thread(daemon=True)` 在后台线程中执行回测，API 立即返回 202。

**理由**：
- 项目已在 `admin.py`（股票同步、指标回填）和 `market_temperature.py`（大盘温度）中广泛使用该模式，团队已熟悉
- 回测是 CPU 密集型的一次性任务，不需要 Celery 级别的分布式调度
- 单用户场景下 daemon thread 足够简单可靠，无需引入额外基础设施
- 回测任务通过数据库中的 `backtest_task` 记录状态，即使线程异常也可通过 DB 状态追踪

**备选**：
- Celery + Redis：功能更强（重试、分布式、结果后端），但对单用户场景过重，引入额外运维负担 → 不采用
- FastAPI BackgroundTasks：仅适合轻量任务，无法在请求上下文外访问；且项目未使用过 → 不采用
- APScheduler 一次性任务：可行，但 APScheduler 主要用于定时调度，用于按需触发的后台任务在语义上不直观 → 不采用

## 决策 2：策略回测接口设计

**决策**：在现有 `StockStrategy` Protocol 上新增 `backtest(*, start_date, end_date) -> BacktestResult` 方法。每个策略自行实现回测逻辑。

**理由**：
- 现有 `execute(as_of_date)` 是"给定某天→返回当日候选"的模式，无法高效支撑"遍历日期范围→产出交易列表"的回测需求
- 不同策略的交易模式差异大（冲高回落的 T+0→T+1→T+2 二段式 vs 其他策略可能的直接买卖模式），统一的逐日回调难以表达所有场景
- 让策略自己实现 `backtest()` 可以：批量查询所需数据（一次查全范围 SQL）、内部维护自己的信号→买入→卖出状态机、返回统一的 `BacktestTrade` 列表
- 引擎只需调用 `strategy.backtest()`、收集结果、计算指标、持久化——职责清晰

**备选**：
- 引擎逐日推进，每天调用 `execute(as_of_date)`：语义上可行，但性能差（每天一次全 A 股 SQL 查询 × 700+ 交易日 ≈ 极慢），且 `execute` 返回的 candidates/signals 不直接等于"一笔完整的买卖交易" → 不采用
- 引擎逐日推进 + 策略注册回调 `on_day()`：更灵活但复杂度高，且对于冲高回落这种需要前后文（T-10 天回看、T+1/T+2 判断）的策略不如一次性批处理高效 → 不采用

## 决策 3：回测数据模型设计

**决策**：新建两张表：`backtest_task`（任务+报告合一）和 `backtest_trade`（交易明细），不复用现有 `strategy_execution_snapshot` 等表。

**理由**：
- 回测与"当日策略执行"是不同场景：当日执行是"单日快照"（execution_snapshot），回测是"跨时间范围的模拟交易过程"
- 回测任务需要记录：起止日期、执行状态（running/completed/incomplete/failed）、绩效指标（胜率/收益率等）——这些字段在 `strategy_execution_snapshot` 中不存在
- 回测交易明细需要记录：买入价/卖出价/收益率/交易类型（正常/未平仓）——与 `strategy_selection_item`（候选明细）的语义完全不同
- spec 中绩效报告（BacktestReport）与回测任务 1:1，直接将报告指标嵌入 `backtest_task` 表中（减少 JOIN），不单独建 `backtest_report` 表

**备选**：
- 复用 `strategy_execution_snapshot` + `strategy_signal_event`：语义不匹配，字段差异大，改造风险高 → 不采用
- 绩效报告单独建表（`backtest_report`）：1:1 关系，增加一次 JOIN 但没有额外价值 → 不采用

## 决策 4：前端页面结构

**决策**：新增单个页面 `HistoryBacktestView.vue`，页面内通过 Tab 或区域分隔"配置+发起"与"回测记录列表+详情"。

**理由**：
- 回测功能入口（配置策略+发起）和结果查看（任务列表+详情）为同一用户流程的前后步骤，放在同一页面内减少跳转
- 异步执行后用户回到列表区域等待状态刷新，交互自然
- 与项目中 `ChongGaoHuiLuoView.vue`（策略页）的单页模式一致

**备选**：
- 配置页和结果页分为两个独立路由页面：增加路由复杂度，用户需要来回跳转 → 不采用

## 决策 5：回测结果中策略特有字段的存储

**决策**：`backtest_trade` 表设 `extra_json JSON` 字段，策略特有信息（如冲高回落的触发日期、冲高幅度等）存入此字段。

**理由**：
- 不同策略的交易阶段与关键信息不同，无法用统一的固定列满足所有策略
- JSON 扩展字段在项目中已有先例（`strategy_signal_event.event_payload_json`、`strategy_selection_item.summary_json`）
- 前端展示时按策略类型解析 `extra_json` 中的字段即可

**备选**：
- 为每种策略建独立交易表：表数量随策略增长，维护成本高 → 不采用
- 在通用交易表中加大量可选列（trigger_date、signal_strength 等）：列越来越多、大部分为 NULL → 不采用
