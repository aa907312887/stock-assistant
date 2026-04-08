# 调研结论：历史模拟优化

## 1. 与回测对齐方式

**决策**：历史模拟在「分析维度」上与智能回测对齐——落库字段、筛选语义（温度/交易所/板块/买入年）、复算指标与分年聚合规则与回测侧一致；**不**引入单仓资金仿真与 `not_traded`。

**理由**：规格要求「相互呼应」且避免用户认知分裂；当前 `simulation_engine` 已复用 `enrich_trades_with_stock_dimension`，仅缺少 `enrich_trades_with_temperature` 及库表字段，补齐即可与 `backtest` 的 `_apply_trade_filters` 同源。

**备选**：仅在内存中补温度不落库、每次筛选时联表查 `market_temperature_daily`——可减少迁移，但与回测「明细可离线筛选」不一致，且与 FR-007「明细可查温度」冲突，故不采用。

---

## 2. 筛选与指标逻辑复用

**决策**：将「交易维度筛选」与「由 ORM 行列表计算 filtered metrics」抽取为独立模块（如 `app/services/trade_metrics.py`），入参为 SQLAlchemy Query 或行列表 + 模型列引用，供 `/backtest` 与 `/simulation` 共用；`yearly-analysis` 与 `filtered-report` 在模拟侧增加与回测对称的路由。

**理由**：`backtest.py` 中 `_apply_trade_filters`、`_calculate_metrics_from_rows` 已与回测表字段耦合；抽取后避免复制粘贴导致语义漂移。

**备选**：在 `simulation.py` 中复制一份筛选逻辑——改动量小但长期易不一致，仅作为抽取失败时的临时方案。

---

## 3. 任务完成时的预聚合

**决策**：模拟任务完成时，在 `simulation_task.assumptions_json` 中写入与回测类似的**全量**分组摘要（如 `temp_level_stats`、`exchange_stats`、`market_stats`），字段形状尽量与回测任务详情中已有结构一致，便于前端复用展示组件或对齐文案。

**理由**：规格 FR-006 要求汇总层具备分组信息；回测已在 `backtest_report.calculate_*` 与 `assumptions_json` 中实践。

**备选**：仅提供按需 API、任务详情不写分组——列表加载多一次全表扫描，体验弱于回测，故作为补充而非替代。

---

## 4. 历史任务与数据迁移

**决策**：为 `simulation_trade` 新增 `market_temp_score`、`market_temp_level` 列；**已存在**的模拟任务明细在迁移前无温度字段，展示为「未知」或在筛选「缺失温度」时与回测一致（不匹配具体级别；仅当用户选择「未知」档时纳入）。

**理由**：温度只能按买入日回溯，可对旧任务写**离线补数脚本**（可选任务）批量回填；首版实现可只保证新任务有温度，旧任务筛选时温度维为空档归入未知。

**备选**：强制重跑所有历史模拟——成本高，不作为默认。

---

## 5. 前端交互

**决策**：`SimulationResultDetail.vue` 对齐回测结果页模式：交易明细区增加**大盘温度**多选、**买入年份**筛选；增加「筛选后复算」指标区（调 `filtered-report`）及「分年度分析」表格（调 `yearly-analysis`）；配置区 Tooltip 补充「与历史回测的区别：无资金仿真、全量闭仓样本」。

**理由**：与规格 P2、与 `HistoryBacktestView` 既有模式一致，降低学习成本。

**备选**：仅表格筛选不调复算接口——用户看不到筛选后的总胜率/总收益，不满足 FR-001/FR-002。
