# Phase 0 调研结论：前复权数据迁移

本文档固化技术选型与范围决策，供 Phase 1 设计与实现引用。

---

## 1. 日线行情：`daily`（未复权）+ `adj_factor` 合成前复权

**决策（2026-04-14 修订）**：日线 OHLC 与涨跌幅相关字段以 Tushare [**`daily`（未复权）**](https://tushare.pro/document/2?doc_id=27) 与 [**`adj_factor`（复权因子）**](https://tushare.pro/document/2?doc_id=28) 合并计算前复权，落库至 `stock_daily_bar`；因子原样持久化至 **`stock_adj_factor`**。

**锚定公式**（与 `tests/test_pro_bar_qfq_export.py` 说明一致）：在回算区间 \([D_{start}, D_{end}]\) 内，取 \(F_{anchor}\) 为 **不超过锚定日** 的最近一条 `adj_factor`；各交易日 \(F_t\) 由与 `daily` 按 `trade_date` 对齐后对因子列 ffill/bfill 得到；则 \(P_{qfq}(t)=P_{raw}(t)\times F_t/F_{anchor}\)。成交量、成交额沿用 `daily` 未复权口径。

**理由**：

- 用户明确要求以 **`adj_factor` 接口** 获取日复权因子并**单独建表**，避免与「复权行情」等易混接口选错；`daily` 文档明确为**未复权**行情，与因子拆分清晰。
- 与 Tushare SDK `pro_bar(adj='qfq')` 可能存在展示锚点差异时，本方案因子可查、可重算，便于审计。

**曾采用路径**：曾以 **`pro_bar` + `qfq`** 作为唯一日线来源（见 2026-03-28 实现说明）；现生产同步已切换为 **`daily`+`adj_factor`**，`pro_bar` 保留为探测/对照。

**备选及未采用原因**：

| 备选 | 未采用原因 |
|------|------------|
| 仅用 `pro_bar` 不落因子表 | 无法满足「因子独立落库、按需使用」与排错需求 |
| 本地手搓因子、不调用 `adj_factor` | 与权威数据源不一致，维护成本高 |

**全市场同步形态**：

- **增量日**：`pro.daily(trade_date=…)` 与 `pro.adj_factor(trade_date=…)` 各 **1 次**全市场拉取；再按标的合并写入；缺当日因子的标的**跳过日线写入**（避免未复权冒充前复权）。
- **回灌**：按标的 `daily` 区间 + `adj_factor` 区间（延伸至回灌 `end_date` 作锚）合并；每标的每自然年窗口约 **2 次**区间请求（`daily` + `adj_factor`），仍须速率限制与分批提交。

---

## 2. 周/月线：从 `stk_weekly_monthly` 改为 `stk_week_month_adj`（`*_qfq`）

**决策**：周、月 K 线数据源由 **`stk_weekly_monthly`** 切换为 Tushare [**`stk_week_month_adj`**](https://tushare.pro/document/2?doc_id=365)（文档名：股票周/月线行情(复权--每日更新)），落库时 **OHLC 取 `open_qfq` / `high_qfq` / `low_qfq` / `close_qfq`**，成交量额等仍取接口中的 `vol` / `amount`（与文档一致）。

**理由**：规格明确要求复权周/月线接口及前复权价字段；与日线「因子+未复权」方案并列，周月直接消费接口给出的前复权列即可。

**备选**：在本地用日线前复权聚合周月——未采用，因规格已指定独立接口，且与现有「按 trade_date 批量拉全市场」模式需重新评估一致性。

**权限与限量**：官方文档标注 **`stk_week_month_adj` 需至少 2000 积分**、单次最大 6000 行。实施前需确认生产 Token 权限；若单批截断需按 `ts_code` 或日期分段循环（与现周线批量逻辑类似）。

---

## 3. 派生数据清空与重算顺序

**决策**：清空顺序为「先派生、后行情」或「先断依赖表、后主表」——具体以 `data-model.md` 中**外键与业务依赖**为准；重算顺序为「**先主行情 → 再指标填充 → 再大盘温度 → 再策略选股快照 → 再历史极值**」，与现有 `stock_sync_orchestrator`、`scheduler` 链路对齐。

**理由**：`spec.md` FR-001a 要求派生数据与行情同步清空并全量重算；现有编排已在日线写入后调用 `fill_*`、大盘温度联动、定时策略；`cum_hist_*` 与日线 upsert 同路径，迁移后仍保持「先 K 线、再派生」的顺序感以减少分叉。

---

## 4. 日线联调与探测（FR-007）

**决策（修订）**：保留 **HTTP 管理端 `pro_bar`（qfq）探测**作为与 `daily`+`adj_factor` 合成结果的**对照**；正式落库以 **`daily`+`adj_factor` + `stock_adj_factor`** 为准。新增/强化的验证可包括：对抽样标的比对 `merge_daily_unadjusted_with_adj_factor_qfq` 与 `pro_bar` 输出差异是否在可接受范围。

**理由**：`pro_bar` 仍便于在无网页试单时快速验 Token；权威因子以 `adj_factor` 表可追溯为准。

---

## 5. 章程与模板

项目 `.specify/memory/constitution.md` 仍为占位模板，**未核定**；本调研不引入额外强制门禁，以本功能 `spec.md` 与本文档为准。
