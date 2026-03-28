---
description: "013-历史高低价 实现任务清单"
---

# Tasks：历史高低价

**Input**：`/Users/yangjiaxing/Coding/CursorProject/stock-assistant/specs/013-历史高低价/` 下 `plan.md`、`spec.md`、`data-model.md`、`research.md`、`contracts/`、`quickstart.md`  
**Prerequisites**：已阅读 `plan.md` 与 `spec.md`  
**Tests**：规格未强制 TDD，本清单**不含**单独测试任务；验收以 `quickstart.md` 与独立测试说明为准。

**Organization**：按用户故事（US1～US4）分阶段，便于分步交付；路径相对于仓库根目录。

## Format：`[ID] [P?] [Story] Description`

---

## Phase 1：Setup（对齐设计）

**Purpose**：确认实现与规格、契约一致后再改代码。

- [x] T001 阅读并对齐 `specs/013-历史高低价/plan.md`、`specs/013-历史高低价/research.md`、`specs/013-历史高低价/data-model.md`、`specs/013-历史高低价/contracts/stock-basic-list-extrema.md`

---

## Phase 2：Foundational（阻塞所有用户故事）

**Purpose**：数据库与 ORM 具备 `hist_*` 三列后，才能写服务与接口。

**⚠️**：未完成本阶段前不要开始用户故事实现。

- [x] T002 新增迁移脚本 `backend/scripts/add_stock_basic_hist_extrema.sql`（为 `stock_basic` 增加 `hist_high`、`hist_low`、`hist_extrema_computed_at`，类型与 `data-model.md` 一致）
- [x] T003 [P] 在 `backend/app/models/stock_basic.py` 为 `StockBasic` 增加 `hist_high`、`hist_low`、`hist_extrema_computed_at` 的 SQLAlchemy 映射
- [x] T004 在本地/开发 MySQL 执行 `add_stock_basic_hist_extrema.sql` 并确认表结构

**Checkpoint**：`stock_basic` 已含三列且 ORM 可加载。

---

## Phase 3：User Story 1 — 每只股票具备可复用的历史最高价与历史最低价（Priority: P1）🎯 MVP

**Goal**：基于 `stock_daily_bar` 全历史聚合，将极值写入 `stock_basic`；可通过本机 CLI 全量跑通。

**Independent Test**：执行全量脚本后，任选一只股票用 SQL 核对 `MAX(high)`/`MIN(low)` 与 `stock_basic.hist_high`/`hist_low` 一致。

### Implementation for User Story 1

- [x] T005 [US1] 新建并实现 `backend/app/services/stock_hist_extrema_service.py` 中 `run_full_recompute(db) -> dict`（按 `data-model.md` 全量 `GROUP BY stock_code` 聚合并更新 `stock_basic`；无日线标的置 `NULL`；写 `hist_extrema_computed_at`；打日志摘要）
- [x] T006 [US1] 新建 `backend/app/scripts/recompute_hist_extrema_full.py`，`python -m app.scripts.recompute_hist_extrema_full` 调用 `run_full_recompute`，打印条数/耗时并以非零退出码表示失败（行为见 `quickstart.md`）

**Checkpoint**：CLI 全量成功后库内极值与日线手工汇总一致。

---

## Phase 4：User Story 2 — 增量定时更新与手动全量重算（Priority: P2）

**Goal**：交易日 **18:00** 自动对「当日有日线」的股票集合做全历史聚合回写；全量仍仅 CLI（规格无 HTTP）。

**Independent Test**：在交易日造当日日线数据或等待定时器，查看日志中增量任务摘要；非交易日应跳过。

### Implementation for User Story 2

- [x] T007 [US2] 在 `backend/app/services/stock_hist_extrema_service.py` 实现 `run_incremental_for_trade_date(db, trade_date: date) -> dict`（仅 `trade_date` 当日存在日线的 `stock_code` 集合，对每 code 做全历史 `MAX/MIN` 回写；空集合时 INFO 跳过；失败记录与规格「保留旧极值」一致）
- [x] T008 [US2] 在 `backend/app/core/scheduler.py` 注册 Cron `hour=18, minute=0`、`Asia/Shanghai`，job id 建议 `hist_extrema_incremental_daily`，入口函数内用 `get_latest_open_trade_date` 判断交易日后调用 `run_incremental_for_trade_date`；异常使用 `log_scheduled_job_failure`（与现有 stock_sync 任务一致）

**Checkpoint**：调度器启动后日志可见新 job；交易日 18:00 行为符合 `plan.md`。

---

## Phase 5：User Story 3 — 下游可依赖的一致性与可核对性（Priority: P3）

**Goal**：同一日行情快照下重复计算/读取结果一致；口径在代码层可读。

**Independent Test**：对固定样本股连续执行两次全量或两次读取 `stock_basic`，数值不变；与 `spec.md` 验收场景一致。

### Implementation for User Story 3

- [x] T009 [US3] 在 `backend/app/services/stock_hist_extrema_service.py` 模块级 docstring（或简短注释）中写明：聚合口径、失败时保留旧极值、历史修订需 CLI 全量；保证实现无随机或非确定性写库

**Checkpoint**：评审可读性与行为与 `spec.md` FR-005、FR-006 一致。

---

## Phase 6：User Story 4 — 股票基本信息页列表展示历史极值（Priority: P2）

**Goal**：`GET /api/stock/basic` 与页面列表展示 `hist_high`、`hist_low`（及可选 `hist_extrema_computed_at`）；`null` 显示「—」；Tooltip 说明非实时价。

**Independent Test**：打开股票基本信息页，首屏可见两列；接口 JSON 含字段（见 `contracts/stock-basic-list-extrema.md`）。

### Implementation for User Story 4

- [x] T010 [P] [US4] 在 `backend/app/schemas/stock_basic.py` 的 `StockBasicItem` 增加 `hist_high`、`hist_low`、`hist_extrema_computed_at`（可选 `None`）
- [x] T011 [US4] 在 `backend/app/api/stock_basic.py` 的 `list_stock_basic` 中从 `StockBasic` ORM 映射上述三字段到 `StockBasicItem`
- [x] T012 [P] [US4] 在 `frontend/src/api/stockBasic.ts` 扩展 `StockBasicItem` 类型与列表响应类型
- [x] T013 [US4] 在 `frontend/src/views/StockBasicView.vue` 增加「历史最高价」「历史最低价」列（`null`/空 显示「—」），并在表头或「?」Tooltip 中补充历史极值说明（与 `spec.md`、产品能力提示规则一致）
- [x] T014 [US4] 更新 `specs/003-股票基本信息/contracts/api-stock-basic.md` 中示例与字段表，与实现及 `specs/013-历史高低价/contracts/stock-basic-list-extrema.md` 一致

**Checkpoint**：前后端联调列表可见列且与库一致。

---

## Phase 7：Polish & Cross-Cutting

**Purpose**：端到端验收与规格收尾。

- [x] T015 按 `specs/013-历史高低价/quickstart.md` 顺序验证：迁移、CLI 全量、`curl` 列表、前端目检、（可选）观察 Scheduler 日志
- [x] T016 [P] 实现全部完成后将 `specs/013-历史高低价/spec.md` 顶部 **状态** 更新为「已实现」

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** → **Phase 2** → **Phase 3 (US1)** → **Phase 4 (US2)** → **Phase 5 (US3)** → **Phase 6 (US4)** → **Phase 7**
- **US4** 仅依赖 **Phase 2** 的 ORM/表结构即可开始接口与 UI（可先显示 `—`）；**展示真实数值**需在 **US1** 全量或 **US2** 增量执行之后。

### User Story Dependencies

| Story | 依赖 |
|-------|------|
| US1 | Phase 2 |
| US2 | US1（共用 `stock_hist_extrema_service.py`） |
| US3 | US1～US2 行为已存在，仅文档与一致性强化 |
| US4 | Phase 2；与 US1 数据展示弱耦合 |

### Parallel Opportunities

- **T003** 可与 **T002** 并行（不同文件），但迁移文件应先于生产库执行落地。
- **T010** 与 **T012** 可在 Phase 6 内并行（后端 schema 与前端 types）。
- **T016** 可与 **T015** 并行（不同文件）。

### Parallel Example：Phase 6

```text
同时：T010 backend/app/schemas/stock_basic.py
同时：T012 frontend/src/api/stockBasic.ts
随后：T011 → T013 → T014
```

---

## Implementation Strategy

### MVP First（仅 US1）

1. Phase 1 + Phase 2  
2. Phase 3（T005、T006）  
3. **STOP**：CLI 全量 + SQL 抽检通过  

### Incremental Delivery

1. 接上 Phase 4（定时增量）  
2. Phase 5（文档/一致性）  
3. Phase 6（列表 API + 页面）  
4. Phase 7（quickstart 全流程）  

---

## Summary

| 项 | 数量 |
|----|------|
| 任务总数 | 16 |
| US1 | 2（T005–T006） |
| US2 | 2（T007–T008） |
| US3 | 1（T009） |
| US4 | 5（T010–T014） |
| 其余 | Setup 1 + Foundational 3 + Polish 2 |

**建议 MVP 范围**：Phase 1～3（T001–T006）。

**生成路径**：`/Users/yangjiaxing/Coding/CursorProject/stock-assistant/specs/013-历史高低价/tasks.md`
