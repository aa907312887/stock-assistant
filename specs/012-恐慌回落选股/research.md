# 调研结论：恐慌回落选股界面

**关联规格**：`spec.md`  
**日期**：2026-03-28

## 1. 策略执行能力是否已存在

**决策**：后端已具备 `PanicPullbackStrategy`（`strategy_id = panic_pullback`），已实现 `execute(as_of_date)`，内部通过单日回测扫描得到触发日候选，并已注册到 `registry`；通用 API 已提供 `GET/POST /api/strategies/{strategy_id}/execute|latest`。

**理由**：避免重复造轮子；规格要求与 `011` 口径一致，直接复用同一策略类即可保证选股与回测同源。

**备选**：单独新建「选股专用」扫描 SQL。不采纳：维护两套判定易产生漂移。

## 2. 交易所 / 板块字段来源与 API 形态

**决策**：在组装返回给前端的 `items` 时，**批量关联 `stock_basic`**，为每条候选补充 **`exchange`（SSE/SZSE/BSE）** 与 **`market`（主板/创业板/科创板/北交所等）** 两个独立字段；Pydantic `StrategySelectionItem` 增加可选字段，与 `003-股票基本信息` 语义一致。保留现有 `exchange_type` 字段作**兼容**（例如继续供冲高回落页展示合并文案，或逐步弃用），新页以 `exchange` + `market` 为准。

**理由**：规格要求两维独立筛选，且与回测明细中 `exchange`/`market` 对齐；当前 `get_latest_strategy_result` 使用 `basic.exchange or basic.market` 填单一 `exchange_type`，无法满足「按交易所 AND 按板块」筛选。

**备选**：仅在前端根据代码规则推断交易所。不采纳：与北交所、特殊代码段等边界易不一致，且违背与基础信息一致的假设。

## 3. 筛选交互放在前端还是后端

**决策**：**第一版仅前端筛选**。用户触发 `/execute` 或 `/latest` 后，前端持有完整 `items`，在内存中按多选交易所、多选板块（含 `__EMPTY__` 表示空板块）过滤展示；清空筛选即恢复全量。

**理由**：满足 FR-007（不改变本次执行、不重复跑策略）；与现有策略 API 契约简单叠加字段即可，无需新端点。

**备选**：新增 `GET .../items?exchanges=&markets=`。不采纳：第一版无分页与超大批次瓶颈时增加复杂度；若日后单次结果极大再评估服务端筛选或分页。

## 4. 空板块（`__EMPTY__`）规则

**决策**：与 `specs/010-智能回测/contracts/backtest-api.md` 一致——当 `stock_basic.market` 为 `NULL` 或空字符串时，归并为「空板块」选项；多选包含该选项时，保留 `market` 为空缺的行。

**理由**：与回测结果页用户心智一致。

## 5. 可选「模拟收益」展示

**决策**：在 `panic_pullback` 的 `_select_trigger_day` 中，若 `_run_backtest` 产出为 **已平仓**（`trade_type=closed`），将 `return_rate`、`sell_date`、`sell_price` 等写入 `summary`（或顶层扩展字段）；若为 **未平仓**（最新交易日尚无 T+1 数据），列表仍展示触发信号，但不展示收益率或展示「待 T+1 收盘价」类说明。

**理由**：规格允许可选模拟收益；与「收盘价模拟」叙述一致。

**备选**：第一版不展示收益，仅展示触发日。可作为裁剪项；若工期紧可仅实现列表+筛选，收益列二期再加。

## 6. 菜单与路由

**决策**：前端新增路由 **`/strategy/panic-pullback`**（与策略描述体 `route_path` 一致），在 `Layout.vue` 的「策略选股」子菜单增加「恐慌回落法」；页面能力边界用标题旁悬浮提示（符合项目前端规则）。

**理由**：与冲高回落页同一模式，降低导航与实现成本。

## 7. 定时任务

**决策**：在 `backend/app/core/scheduler.py` 中增加与 **冲高回落战法** 同构的日频任务：`CronTrigger` **17:20 Asia/Shanghai**，`execute_strategy(db, strategy_id="panic_pullback", as_of_date=today)`；非交易日或 `StrategyDataNotReadyError` 时跳过并打日志。

**理由**：与现有 `chong_gao_hui_luo` 定时任务一致，用户在交易日收盘后无需手动执行即可在页面「查询最新结果」看到当日快照。

**历史**：曾有一版规格不写定时；已按产品要求纳入 FR-002a。

---

以上结论已全部消除技术背景中的「待澄清」项，可直接指导 `plan.md` 与 Phase 1 设计文档。
