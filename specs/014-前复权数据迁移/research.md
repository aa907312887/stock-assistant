# Phase 0 调研结论：前复权数据迁移

本文档固化技术选型与范围决策，供 Phase 1 设计与实现引用。

---

## 1. 日线行情：从 `daily` 改为 `pro_bar`（`qfq`）

**决策**：日线 OHLC 与涨跌幅相关字段以 Tushare **`pro_bar`**、`adj='qfq'` 为准，落库至既有 `stock_daily_bar`（字段语义变更为**前复权价**）。

**理由**：

- 功能规格（`spec.md` FR-001）明确要求使用 [通用行情 `pro_bar`](https://tushare.pro/document/2?doc_id=109) 前复权。
- 当前实现（`tushare_client.get_daily_by_trade_date`）使用 **`pro.daily`**，为**未复权**口径，与目标不一致。
- `daily_basic`（换手率、市值、估值等）与价格复权无关，可继续按交易日全市场拉取，与 `pro_bar` 结果按 `ts_code` 关联写入同行。

**备选方案及未采用原因**：

| 备选 | 未采用原因 |
|------|------------|
| 继续用 `pro.daily` + 本地复权因子推算 | 与规格指定的 `pro_bar`/`qfq` 不一致，且实现与 Tushare 官方复权算法易漂移 |
| 仅改文档声明「近似前复权」 | 不满足规格与验收 |

**全市场同步形态变化**：

- **现状**：`pro.daily(trade_date=…)` 单次返回**全市场**当日一行，请求次数少。
- **目标**：`pro_bar` 按文档为**单证券** `ts_code` 请求；全市场需对 `stock_basic` 中每个代码循环（或受控并发），请求量约为「标的数 × 交易日数（回灌）」。需在实现中采用：**速率限制**（沿用 `tushare_rate_pause_sec`）、**分批提交**、**可恢复批次**，并在 `plan.md` 中写明运维预期耗时。

---

## 2. 周/月线：从 `stk_weekly_monthly` 改为 `stk_week_month_adj`（`*_qfq`）

**决策**：周、月 K 线数据源由 **`stk_weekly_monthly`** 切换为 Tushare [**`stk_week_month_adj`**](https://tushare.pro/document/2?doc_id=365)（文档名：股票周/月线行情(复权--每日更新)），落库时 **OHLC 取 `open_qfq` / `high_qfq` / `low_qfq` / `close_qfq`**，成交量额等仍取接口中的 `vol` / `amount`（与文档一致）。

**理由**：规格明确要求复权周/月线接口及前复权价字段；当前 `get_stk_weekly_monthly_by_trade_date` 使用未复权为主的 `stk_weekly_monthly`，不满足口径。

**备选**：在本地用日线前复权聚合周月——未采用，因规格已指定独立接口，且与现有「按 trade_date 批量拉全市场」模式需重新评估一致性。

**权限与限量**：官方文档标注 **`stk_week_month_adj` 需至少 2000 积分**、单次最大 6000 行。实施前需确认生产 Token 权限；若单批截断需按 `ts_code` 或日期分段循环（与现周线批量逻辑类似）。

---

## 3. 派生数据清空与重算顺序

**决策**：清空顺序为「先派生、后行情」或「先断依赖表、后主表」——具体以 `data-model.md` 中**外键与业务依赖**为准；重算顺序为「**先主行情 → 再指标填充 → 再大盘温度 → 再策略选股快照 → 再历史极值**」，与现有 `stock_sync_orchestrator`、`scheduler` 链路对齐。

**理由**：`spec.md` FR-001a 要求派生数据与行情同步清空并全量重算；现有编排已在日线写入后调用 `fill_*`、大盘温度联动、定时策略；`cum_hist_*` 与日线 upsert 同路径，迁移后仍保持「先 K 线、再派生」的顺序感以减少分叉。

---

## 4. 日线测试接口（FR-007）

**决策**：新增 **HTTP 管理端探测接口**（建议 `GET` + `X-Admin-Secret`），内部调用与正式同步**相同**的 `pro_bar` 封装（`ts_code`、`start_date`、`end_date`、`adj='qfq'`），返回**少量行** JSON，不默认写库。联调通过并留痕（检查表/发布说明）后，再合并正式同步路径。

**理由**：Tushare 对 `pro_bar` 无官方网页试单；规格要求先测后用。

---

## 5. 章程与模板

项目 `.specify/memory/constitution.md` 仍为占位模板，**未核定**；本调研不引入额外强制门禁，以本功能 `spec.md` 与本文档为准。
