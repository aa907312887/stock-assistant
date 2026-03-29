# Phase 0 调研结论：早晨十字星

**日期**：2026-03-29  
**对应规格**：`spec.md`

## 1. 策略标识与注册方式

- **决策**：新增 `strategy_id = zao_chen_shi_zi_xing`（与现有 `shu_guang_chu_xian` 等保持 snake_case）；在 `backend/app/services/strategy/registry.py` 的 `list_strategies()` 中注册新类实例，插入顺序建议置于「曙光初现」附近以便展示。
- **理由**：回测引擎与 `GET /api/strategies` 均从注册表解析策略；无需改表结构即可让 `POST /api/backtest/run` 接受新 `strategy_id`。
- **备选**：在配置文件中维护策略列表——当前项目以代码注册为准，不引入新配置层。

## 2. 锤头线数值判定

- **决策**（与规格「业界常见锤头」一致，且可单测）：
  - 记当日 `high`、`low`、`open`、`close`，`body = |close − open|`，`upper = high − max(open, close)`，`lower = min(open, close) − low`，`range_ = high − low`。
  - 若 `range_ ≤ 0` 或 `high`/`low` 缺失 → 该日不满足锤头（跳过信号）。
  - **实体位于区间上端**：`min(open, close) ≥ low + 0.5 × range_`（实体下端落在 K 线下半部以上）。
  - **下影显著长于实体、上影较短**：
    - 若 `body` 相对收盘价过小（如 `body < max(|close|, 1) × 1e−8`）：要求 `lower ≥ 0.55 × range_` 且 `upper ≤ 0.15 × range_`（避免除零，适配近似一字线）。
    - 否则：要求 `lower ≥ 2 × body` 且 `upper ≤ body`。
- **理由**：与教材常见「锤头」一致，且与 `shu_guang_chu_xian.py` 中「显式公式 + 边界保护」风格一致，便于审查与回归。
- **备选**：仅用 `lower ≥ 2×body` 不要求实体位置——会误收「长腿十字」类样本，与「实体在上」语义不符，故不采用。

## 3. 第二根 K 线「涨跌幅绝对值 ≤ 1%」

- **决策**：`(close_{T−1} / close_{T−2} − 1)` 的绝对值 ≤ `0.01`；边界等于 1% 视为满足（与规格假设一致）。
- **理由**：规格 `spec.md` 假设章节已明确口径。
- **备选**：改用全日振幅 `(high−low)/close_{T−2}`——与用户已确认的规格不一致，不采用。

## 4. 索引与数据加载

- **决策**：回测主循环中令索引 `i` 对应 **T**（第三根阳线日），则 `T−k` 对应 `bars_list[i−k]`。形态与跌势要求至少存在 `i−9`，故 **`i` 从 9 开始**；`min_i = max(9, weak_lookback_days)`（`weak_lookback_days=7` 时取 9）。
- **决策**：`select` 在现有 `shu_guang_chu_xian` 字段基础上**增加** `StockDailyBar.high`、`StockDailyBar.low`，供锤头判定使用。
- **理由**：`stock_daily_bar` 已含 `high`/`low`（`app/models/stock_daily_bar.py`），仅需查询列扩展。
- **备选**：不查 high/low，用 `|open−close|` 近似锤头——无法判定影线，不满足规格。

## 5. 买入后卖出仿真与「曙光初现」一致

- **决策**：从 `ShuGuangChuXianStrategy._run_backtest` 中复制「自 `buy_idx` 次日起」的止损 / 止盈分支逻辑，但**止损比例固定为 8%**（`买入价×0.92`、`stop_loss_8pct`），与曙光初现的 **10%** 区分；止盈分支一致。
- **理由**：规格明确要求一致；当前仓库未抽取公共 `simulate_exit_from_buy` 函数，首版以复制为主降低耦合风险。
- **备选**：抽公共函数到 `strategy_base` 或 `portfolio_simulation`——可作为后续重构，非本功能阻塞项。

## 6. 选股 `execute` 与 `as_of_date`

- **决策**：与 `ShuGuangChuXianStrategy.execute` 相同模式：对 `as_of_date`（默认最新交易日）跑 **单日** `start_date=end_date=as_of_date` 的回测内核，筛选 **`buy_date == as_of_date`** 的成交，组装 `StrategyCandidate` / `StrategySignal`。
- **理由**：项目既有契约；用户从策略页「当日买入候选」与回测共用同一判定。

## 7. 前端与路由

- **决策**：**回测历史页**通过 `GET /api/strategies` 拉列表，注册后即出现在策略下拉框，**不必**为每个策略单独改 `BacktestConfigPanel`。
- **决策**：侧边栏「策略选股」目前仅挂载「冲高回落」「恐慌回落」；**曙光初现亦无独立菜单项**。本功能 **P1 不强制**新增 `Layout.vue` / `router` 菜单；若需与规格 FR-001「策略说明页」完全一致，可在实现阶段按 `ChongGaoHuiLuoView.vue` 范式新增 `ZaoChenShiZiXingView.vue` 并注册 `route_path=/strategy/zao-chen-shi-zi-xing`。
- **理由**：规格成功标准以回测可区分为主；菜单为增量体验项。

---

**待澄清项**：无（均在规格或上文已闭合）。
