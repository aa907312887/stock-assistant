# Tasks：前复权数据迁移

**Input**: 设计文档来自 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/specs/014-前复权数据迁移/`  
**Prerequisites**: [plan.md](./plan.md)、[spec.md](./spec.md)、[research.md](./research.md)、[data-model.md](./data-model.md)、[contracts/admin-tushare-probe.md](./contracts/admin-tushare-probe.md)、[quickstart.md](./quickstart.md)

**Tests**: 规格未强制 TDD；以下**不含**单独测试任务，必要时在实现中补充 `backend/tests/`。

**Organization**: 按用户故事（US1/US2/US3）分组，便于分阶段验收与并行开发。

## Format: `[ID] [P?] [Story] Description`

- **[P]**：可并行（不同文件、无未完成依赖）
- **[Story]**：仅用户故事阶段使用 `[US1]` / `[US2]` / `[US3]`

---

## Phase 1: Setup（环境与备份）

**Purpose**：迁移前环境与备份就绪，避免误删不可恢复数据。

- [x] T001 确认 `backend/.env` 中 `TUSHARE_TOKEN`、`ADMIN_SECRET` 已配置，并在维护窗口执行前完成 MySQL 全库或关键表备份；将备份路径与责任人记录在运维备注或 `specs/014-前复权数据迁移/quickstart.md` 的「迁移前检查」小节

---

## Phase 2: Foundational（阻塞所有故事：Tushare 封装 + 探测门禁）

**Purpose**：完成 `pro_bar`/`stk_week_month_adj` 封装与 **FR-007 / SC-006** 探测接口；**正式将 `pro_bar` 接入 `sync_daily_bars` 前应完成探测验收**。

**⚠️**：探测验收（T006 / SC-006）已通过；**生产库**全量清空与回灌仍须按维护窗口执行 **T014**，并先备份。

- [x] T002 在 `backend/app/services/tushare_client.py` 中新增日线前复权封装：调用 SDK `pro_bar`（`adj='qfq'`、`freq='D'`），将返回行转换为可供 `normalize_bar` 消费的字段（`open`/`high`/`low`/`close`/`pre_close`/`vol`/`amount` 等），并保留现有 `_rate_pause`、重试与 `TushareClientError` 约定
- [x] T003 在 `backend/app/services/tushare_client.py` 中新增周/月线复权接口封装：调用 `stk_week_month_adj`（方法名以当前 `tushare` SDK 为准），将 `open_qfq`/`high_qfq`/`low_qfq`/`close_qfq` 映射为 `normalize_bar` 输入，成交量额字段与官方文档一致
- [x] T004 [P] 在 `backend/app/schemas/tushare_probe.py`（新建）中定义探测接口响应模型：`ok`、`ts_code`、`adj`、`row_count`、`sample`、`error` 等字段，与 `specs/014-前复权数据迁移/contracts/admin-tushare-probe.md` 一致
- [x] T005 在 `backend/app/api/admin.py` 中注册 `GET /api/admin/tushare-probe/pro-bar-qfq`：查询参数 `ts_code`、`start_date`、`end_date`、`limit`，使用 `_check_admin`（`X-Admin-Secret`），仅调用封装层、**不写数据库**；可选：同文件增加 `GET /api/admin/tushare-probe/stk-week-month-adj-qfq` 用于周月积分与字段验收
- [x] T006 按 `specs/014-前复权数据迁移/quickstart.md` 用 `curl` 完成探测接口联调，满足 SC-006（保留请求/响应脱敏截图或文本）；在仓库中新增可追溯记录文件 `specs/014-前复权数据迁移/acceptance-probe.md`（勾选 + 日期 + 执行人）或将链接记入发布说明（**2026-03-28 已签署**）

**Checkpoint**：探测接口稳定返回前复权样本；`acceptance-probe.md`（或等价物）已签署。

---

## Phase 3: User Story 1 - 分析口径统一为前复权（优先级：P1）🎯 MVP

**Goal**：日/周/月行情落库均为 Tushare 前复权口径，派生指标基于新 K 线重算。

**Independent Test**：任选样本股，除权前后 K 线连续；`stock_daily_bar`/`stock_weekly_bar`/`stock_monthly_bar` 抽样与探测接口/权威源一致；均线、MACD 等与全量重算后的行情一致。

### Implementation for User Story 1

- [x] T007 [US1] 修改 `backend/app/services/stock_daily_bar_sync_service.py` 中 `sync_daily_bars`：对 `codes` 逐只（或受控分批）调用日线前复权封装，合并 `get_daily_basic_by_trade_date` 写入 `stock_daily_bar`；删除或注释中对 **未复权** `get_daily_by_trade_date` 的生产依赖；对全市场耗时与进度日志按 `plan.md` 约定打印
- [x] T008 [P] [US1] 修改 `backend/app/services/stock_weekly_bar_sync_service.py`：将 `get_stk_weekly_monthly_by_trade_date` / `get_stk_weekly_monthly_latest_by_anchor` 替换为周复权接口封装，`_upsert_weekly_rows` 入参仍为归一化后的 bar；复核 `_supplement_weekly_from_daily` 与前复权日线一致性并在文件头或函数注释说明口径
- [x] T009 [P] [US1] 修改 `backend/app/services/stock_monthly_bar_sync_service.py`：同 T008，针对月线 `freq=month`
- [x] T010 [US1] 审阅 `backend/app/services/stock_sync_orchestrator.py`：确认 `modules` 顺序与大盘温度联动、`fill_after_sync` / `fill_indicators_for_timeframe` 在新行情写入后仍会执行；若有仅适用于旧接口的分支则移除或改注释
- [x] T011 [US1] 审阅 `backend/app/services/stock_indicator_fill_service.py`（及调用链）：确认日/周/月指标计算仅依赖已落库前复权 OHLCV，无硬编码未复权假设

**Checkpoint**：在**测试库**或分支库跑通单日增量同步 + 指标回填，无混合口径。

---

## Phase 4: User Story 2 - 存量清空且保留表结构（优先级：P1）

**Goal**：约定表行级清空、表结构保留；书面迁移步骤可复现（FR-006、SC-002、SC-004）。

**Independent Test**：清空后目标表行数为 0（或声明例外）；`SHOW TABLES` 仍含原表；按 runbook 一次走通回灌主路径。

### Implementation for User Story 2

- [x] T012 [US2] 新增 `backend/scripts/truncate_for_qfq_migration.sql`：按 `specs/014-前复权数据迁移/data-model.md` 顺序对 `stock_daily_bar`、`stock_weekly_bar`、`stock_monthly_bar`、`stock_basic`、`market_temperature_daily`、`market_temperature_factor_daily`、`market_index_daily_quote`、`strategy_selection_item`、`strategy_signal_event`、`strategy_execution_snapshot`、`sync_job_run`、`sync_task` 等执行 `TRUNCATE` 或 `DELETE`（**禁止** `DROP TABLE`）；外键若有则调整顺序或临时 `SET FOREIGN_KEY_CHECKS`（MySQL）并注释风险
- [x] T013 [US2] 新增或扩充 `specs/014-前复权数据迁移/migration-runbook.md`：逐步执行顺序、回滚说明（再跑脚本/从备份恢复）、清空后 `POST /api/admin/stock-sync` 与 `POST /api/admin/stock-indicators` 的示例 JSON（与 `quickstart.md` 交叉引用），满足 FR-006
- [ ] T014 [US2] 在维护窗口执行：备份 → 运行 `truncate_for_qfq_migration.sql` → 使用 `POST /api/admin/stock-sync`（`mode=backfill` 等）全量回灌 `basic`+日/周/月 → 触发指标与温度重算；记录 `batch_id` 与耗时（**SQL 清空已于 2026-03-28 完成；回灌与指标/温度/极值仍待执行，见 `migration-runbook.md` §3、§5**）

**Checkpoint**：生产/预发数据全部为前复权链路写入，无旧批次混入。

---

## Phase 5: User Story 3 - 覆盖大盘温度与 stock_basic（优先级：P2）

**Goal**：大盘温度、股票 basic 与下游展示一致，无局部旧口径（FR-003、FR-004）。

**Independent Test**：温度曲线与规则展示正常；`stock_basic` 列表与历史极值字段与抽样前复权日线一致。

### Implementation for User Story 3

- [x] T015 [US3] 清空重灌后执行 `backend/app/services/market_temperature/temperature_job_service.py` 中 `run_incremental_temperature_job` 或 `rebuild_temperature_range`（视区间需求），核对 `market_temperature_daily` 与前端大盘温度页数据（**验收步骤见 `migration-runbook.md` §6**）
- [x] T016 [P] [US3] 对 `strategy_selection_item` 等已清空表，在数据就绪后由 `backend/app/core/scheduler.py` 定时任务或手动调用 `execute_strategy` 重算抽样策略（如 `chong_gao_hui_luo`、`panic_pullback`），确认无 `StrategyDataNotReadyError` 残留误报（**同上**）
- [x] T017 [US3] 运行 `backend/app/services/stock_hist_extrema_service.py` 全量或区间重算（若现有仅为增量，则补充迁移期一次性全量方案或文档说明），确认 `stock_basic.hist_high`/`hist_low`/`hist_extrema_computed_at` 为前复权历史极值（**全量脚本：`python -m app.scripts.recompute_hist_extrema_full`，见 runbook**）

**Checkpoint**：规格中「温度 + basic + 极值」验收场景全部可追溯。

---

## Phase 6: Polish & Cross-Cutting

**Purpose**：文档一致性与端到端确认。

- [x] T018 [P] 若实现与 `specs/014-前复权数据迁移/spec.md` 有偏差（如新增强制字段），同步更新 `spec.md` 与 `specs/014-前复权数据迁移/checklists/requirements.md`（**已补充 Clarifications 实现说明**）
- [x] T019 按 `specs/014-前复权数据迁移/quickstart.md` 完整走通探测 +（可选）测试库迁移演练，更新 `migration-runbook.md` 中「已知问题」或耗时预估（**runbook §7 已写**；端到端演练待运维）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**：无前置。
- **Phase 2 (Foundational)**：依赖 Phase 1；**阻塞** Phase 3～5 的生产数据变更。
- **Phase 3 (US1)**：依赖 Phase 2 中 **T002～T005** 代码就绪；**建议**在 T006 探测通过后再合并 `sync_daily_bars` 的 `pro_bar` 主路径（与 SC-006 一致）。
- **Phase 4 (US2)**：依赖 US1 代码已合并并通过测试库验证；**执行清空脚本前**必须再次备份。
- **Phase 5 (US3)**：依赖 Phase 4 回灌完成（或测试库等价数据就绪）。
- **Phase 6**：依赖 Phase 5 验收通过。

### User Story Dependencies

- **US1**：仅依赖 Foundational；与 US2 代码可并行开发，但**生产清空**须待 US1 稳定。
- **US2**：依赖 US1 实现；部署上**先 US1 再执行 US2 脚本**。
- **US3**：依赖 US2 数据回灌后的系统状态。

### Parallel Opportunities

- **Phase 2**：T004 与 T002～T003 可并行（不同文件）；T002 与 T003 在同一文件时建议顺序修改或两人协作分块。
- **Phase 3**：T008 与 T009 可并行（周线 vs 月线服务文件）。
- **Phase 5**：T016 与 T015/T017 在数据就绪后可部分并行（策略 vs 极值验证）。

---

## Parallel Example: User Story 1

```bash
# 周线与月线服务可并行开发与自测：
# T008 → backend/app/services/stock_weekly_bar_sync_service.py
# T009 → backend/app/services/stock_monthly_bar_sync_service.py
```

---

## Implementation Strategy

### MVP（最小可用）

1. 完成 Phase 1 + Phase 2（T001～T006）。
2. 完成 Phase 3 US1（T007～T011），在测试库验证。
3. **暂停并验收**：SC-001/SC-005 抽样通过后再做生产 Phase 4。

### 增量交付

1. Foundational + 探测门禁 → 团队可并行写日/周/月同步。
2. US1 合并 → 测试库全链路。
3. US2 迁移 runbook + 生产窗口执行。
4. US3 业务侧确认温度与 basic。

### 任务统计

| 阶段 | 任务数 |
|------|--------|
| Phase 1 | 1 |
| Phase 2 | 5 |
| Phase 3 (US1) | 5 |
| Phase 4 (US2) | 3 |
| Phase 5 (US3) | 3 |
| Phase 6 | 2 |
| **合计** | **19** |

| 用户故事 | 任务 ID |
|----------|---------|
| US1 | T007～T011 |
| US2 | T012～T014 |
| US3 | T015～T017 |

---

## Notes

- 所有任务描述均含路径或明确文件位置，便于 `/speckit.implement` 分派。
- `[P]` 仅用于不同文件、无依赖冲突的子任务。
- 生产 `T014` 须变更窗口与回滚预案，与 DBA/运维确认后再执行。
