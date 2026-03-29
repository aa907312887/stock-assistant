# 实现计划：历史高低价

**分支**: `013-历史高低价` | **日期**: 2026-03-28 | **规格**: [spec.md](./spec.md)  
**输入**: 功能规格来自 `specs/013-历史高低价/spec.md`；Clarifications 已约定全量仅本机 CLI、不提供全量 HTTP。

**说明**: 全文使用**中文**；与 [research.md](./research.md)、[data-model.md](./data-model.md)、[contracts/](./contracts/)、[quickstart.md](./quickstart.md) 一致。

## 概要

**（2026-03-29 修订）** 在 `stock_daily_bar` 每行写入按日递推的 **`cum_hist_high` / `cum_hist_low`**（截至该 `trade_date` 含扩展最高/最低），**不再**在 `stock_basic` 存全表终态极值，避免回测泄露未来。**增量**：在 `stock_daily_bar_sync_service` 每次日线 upsert 后调用 `apply_cum_extrema_after_daily_upsert`（纯尾部追加 O(1)；中间改数则该股整段重算）；**无** 18:00 独立 Job。**全量**：本机 `python -m app.scripts.recompute_hist_extrema_full`。**列表**：`GET /api/stock/basic` 仍返回 `hist_high`/`hist_low`，语义为**最新日线**上的累计列；回测按日读日线表。

## 技术背景

- **语言/版本**: Python 3.x（与仓库 `backend` 一致）
- **主要依赖**: FastAPI、SQLAlchemy、APScheduler（`apscheduler`）、Pydantic、MySQL
- **存储**: MySQL；表 `stock_basic`、`stock_daily_bar`
- **测试**: pytest（与仓库 `backend/tests` 惯例一致）
- **目标平台**: 本机/服务器部署，浏览器访问前端
- **项目类型**: Web 应用（FastAPI 后端 + Vue 前端）+ 本机运维脚本
- **性能目标**: 列表首屏与 003 一致（≤3s 级体验）；日线同步内 O(1) 递推避免全市场逐股全历史重扫
- **约束**: 全量 HTTP 禁止；增量须与交易日判断一致；失败时保留旧极值（见规格假设）
- **规模/范围**: A 股全市场约数千 `stock_basic` 行；日线千万级行需避免无索引全表扫描（聚合使用 `stock_code` 上已有索引）

## 章程检查

仓库 `.specify/memory/constitution.md` 仍为模板占位，**未核定**，无强制门禁。设计遵循项目既有 Spec 与「中文注释」规则；若后续章程核定，需复检本计划与实现一致。

## 关键设计详述

### 数据流与接口职责

```text
[stock_daily_bar_sync_service] upsert 日线行
        ↓ flush 后
[stock_hist_extrema_service.apply_cum_extrema_after_daily_upsert]
        ↓ UPDATE 该行 cum_hist_*（或该股整段 _recompute_cumulative_for_code）
[stock_daily_bar]
        ↓ 列表：最新日线左连
GET /api/stock/basic → StockBasicItem（hist_* 来自最新日线 cum）
        ↓
股票基本信息页表格列
```

| 层级 | 职责 |
|------|------|
| **日线同步** `app/services/stock_daily_bar_sync_service.py` | `sync_daily_bars` / `sync_daily_bars_backfill_range` 在每次成功 `_upsert_daily_bar` 后 `flush` 并调用 `apply_cum_extrema_after_daily_upsert`；回灌内对 pro_bar 行按 `trade_date` 升序处理。 |
| **服务层** `app/services/stock_hist_extrema_service.py` | `apply_cum_extrema_after_daily_upsert`：O(1) 递推或整股重算；`run_full_recompute(db) -> dict`：全量纠偏 CLI 用。 |
| **脚本** `backend/app/scripts/recompute_hist_extrema_full.py` | `cd backend && python -m app.scripts.recompute_hist_extrema_full`；创建 `SessionLocal`，调用 `run_full_recompute`，打印/退出码供运维查看。 |
| **API** `app/api/stock_basic.py` | `list_stock_basic` 左连最新日线映射 `hist_high`、`hist_low`、`hist_extrema_computed_at`（≈ 日线 `updated_at`）。 |
| **Schema** `app/schemas/stock_basic.py` | `StockBasicItem` 三字段，可选 `None`。 |
| **前端** `frontend/src/views/StockBasicView.vue` | 表格列 + 表头 Tooltip；`frontend/src/api/stockBasic.ts` 类型同步。 |

**错误约定**：列表接口不因极值缺失单独报错；日线写入失败则该行 cum 不更新；全量 CLI 失败时日志可见。

### 定时任务与部署设计

- **极值无独立 Cron**：不与 APScheduler 绑定；日常随 `stock_sync` 子任务中的 `daily` 写入一并完成。
- **部署时是否执行一次**: **否**。首次或迁移后依赖运维执行 **CLI 全量脚本**（见 [quickstart.md](./quickstart.md)）。
- **手动触发方式**（规格要求至少一种）:
  - [ ] HTTP 接口：~~不提供~~（全量禁止 HTTP）。
  - [x] **管理命令/脚本**：`cd backend && python -m app.scripts.recompute_hist_extrema_full`。
  - [ ] 日常增量：**不提供**单独 HTTP；由日线同步路径自动维护。

**递推算法摘要（实现口径）**:

1. 写入/更新 `trade_date = T` 的一行后，若该股存在 `trade_date > T` 的行 → 对该 `stock_code` 按时间序整段重算 `cum_hist_*`。
2. 否则取 `trade_date < T` 中最大一日的行 `prev`；若 `prev` 两列 cum 皆为 `NULL` 且仍存在更早日线 → 整段重算（回填链断裂兜底）。
3. 否则 `cum_hist_high = 扩展 max(prev.cum_hist_high, T.high)`（`NULL` 不参与比较则继承），`cum_hist_low` 同理。

### 其他关键设计

- **复权**: 不引入；直接使用 `stock_daily_bar.high`/`low` 存储值（见 research）。
- **并发**: 全量 CLI 与大批量日线回灌不建议并行；运维文档注明「全量 CLI 尽量在交易空闲期执行」。
- **003 契约同步**: 实现后保持 `specs/003-股票基本信息/contracts/api-stock-basic.md` 与 [contracts/stock-basic-list-extrema.md](./contracts/stock-basic-list-extrema.md) 字段一致。

## 项目结构

### 本功能文档

```text
specs/013-历史高低价/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── stock-basic-list-extrema.md
└── tasks.md             # 由 /speckit.tasks 生成
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── api/stock_basic.py           # 列表响应增加 hist_* 字段
│   ├── core/scheduler.py            # 无 hist 独立 Job
│   ├── models/stock_basic.py        # 极值列已迁走（见 data-model）
│   ├── schemas/stock_basic.py       # StockBasicItem 扩展
│   ├── scripts/recompute_hist_extrema_full.py     # 新增：全量 CLI
│   └── services/stock_hist_extrema_service.py     # 新增：聚合与写回
├── scripts/
│   └── add_stock_basic_hist_extrema.sql           # 新增：迁移
└── tests/                           # 可选：服务层单测

frontend/
├── src/views/StockBasicView.vue     # 列 + Tooltip
└── src/api/stockBasic.ts            # 类型
```

**结构说明**: 日常递推在 `stock_daily_bar_sync_service` + `stock_hist_extrema_service`；全量纠偏用 CLI；前端仅扩展 003 页面，不新增路由。

## 复杂度与例外

无额外章程违反项；若全市场单次聚合超时，可在实现阶段将全量 CLI 改为分批 `LIMIT` 更新，无需变更规格口径。
