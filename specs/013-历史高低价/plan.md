# 实现计划：历史高低价

**分支**: `013-历史高低价` | **日期**: 2026-03-28 | **规格**: [spec.md](./spec.md)  
**输入**: 功能规格来自 `specs/013-历史高低价/spec.md`；Clarifications 已约定全量仅本机 CLI、不提供全量 HTTP。

**说明**: 全文使用**中文**；与 [research.md](./research.md)、[data-model.md](./data-model.md)、[contracts/](./contracts/)、[quickstart.md](./quickstart.md) 一致。

## 概要

基于 `stock_daily_bar` 全历史 `high`/`low` 聚合每只股票的历史最高价、历史最低价，写入 `stock_basic` 三列（`hist_high`、`hist_low`、`hist_extrema_computed_at`）。**增量**：每个交易日 **18:00（Asia/Shanghai）** 由 APScheduler 触发，仅对「当日有日线写入」的股票集合做该股全历史聚合回写。**全量**：运维在本机执行 **Python 脚本**，全市场 `GROUP BY stock_code` 聚合后回写；**不提供**全量重算 HTTP。**前端**：股票基本信息页列表与 `GET /api/stock/basic` 增加三字段展示；列头 Tooltip 说明为历史极值、非实时价。

## 技术背景

- **语言/版本**: Python 3.x（与仓库 `backend` 一致）
- **主要依赖**: FastAPI、SQLAlchemy、APScheduler（`apscheduler`）、Pydantic、MySQL
- **存储**: MySQL；表 `stock_basic`、`stock_daily_bar`
- **测试**: pytest（与仓库 `backend/tests` 惯例一致）
- **目标平台**: 本机/服务器部署，浏览器访问前端
- **项目类型**: Web 应用（FastAPI 后端 + Vue 前端）+ 本机运维脚本
- **性能目标**: 列表首屏与 003 一致（≤3s 级体验）；18:00 增量任务在常规全市场规模下应在可接受时间内完成（单批大 SQL 或分批，见关键设计）
- **约束**: 全量 HTTP 禁止；增量须与交易日判断一致；失败时保留旧极值（见规格假设）
- **规模/范围**: A 股全市场约数千 `stock_basic` 行；日线千万级行需避免无索引全表扫描（聚合使用 `stock_code` 上已有索引）

## 章程检查

仓库 `.specify/memory/constitution.md` 仍为模板占位，**未核定**，无强制门禁。设计遵循项目既有 Spec 与「中文注释」规则；若后续章程核定，需复检本计划与实现一致。

## 关键设计详述

### 数据流与接口职责

```text
[stock_daily_bar] 只读 high/low/stock_code/trade_date
        ↓ 聚合（MAX/MIN 按 stock_code）
[stock_hist_extrema_service]
        ↓ UPDATE stock_basic.hist_* / hist_extrema_computed_at
[StockBasic ORM]
        ↓ 同页查询
GET /api/stock/basic → StockBasicItem（含 hist_*）
        ↓
股票基本信息页表格列
```

| 层级 | 职责 |
|------|------|
| **服务层** `app/services/stock_hist_extrema_service.py`（建议名） | `run_full_recompute(db) -> dict`：全量聚合；`run_incremental_for_trade_date(db, trade_date: date) -> dict`：仅对「该日有日线」的 code 做该股全历史聚合；统一写日志摘要（成功/失败条数、耗时、可选失败 code 列表）。 |
| **调度** `app/core/scheduler.py` | 注册 `_job_hist_extrema_incremental`：18:00 Cron；内部先判断交易日（与 `_job_sync_stock` 相同：`get_latest_open_trade_date(today) == today`）；非交易日直接 return。 |
| **脚本** `backend/app/scripts/recompute_hist_extrema_full.py` | `cd backend && python -m app.scripts.recompute_hist_extrema_full`；创建 `SessionLocal`，调用 `run_full_recompute`，打印/退出码供运维查看。 |
| **API** `app/api/stock_basic.py` | `list_stock_basic` 查询 `StockBasic` 时映射 `hist_high`、`hist_low`、`hist_extrema_computed_at` 至 `StockBasicItem`。 |
| **Schema** `app/schemas/stock_basic.py` | `StockBasicItem` 增加三字段，可选 `None`。 |
| **前端** `frontend/src/views/StockBasicView.vue` | 表格列 + 表头 Tooltip；`frontend/src/api/stockBasic.ts` 类型同步。 |

**错误约定**：列表接口不因极值缺失单独报错；任务失败仅体现在日志与 `hist_extrema_computed_at` 不更新（旧值保留）。

### 定时任务与部署设计

- **使用的组件**: **APScheduler** `BackgroundScheduler`，与现有模块一致；位置：`backend/app/core/scheduler.py`；时区常量复用 `TIMEZONE = "Asia/Shanghai"`。
- **注册方式**: 在 `start_scheduler()` 内与现有 `add_job` 并列新增一条；应用生命周期在 `app/main.py` 的 `lifespan` 中 `startup` 调用 `start_scheduler()`（**已存在**，无需改注册入口，仅扩展 `scheduler.py`）。
- **调度策略**: `CronTrigger(hour=18, minute=0, timezone=TIMEZONE)`，**job id** 建议 `hist_extrema_incremental_daily`。
- **部署时是否执行一次**: **否**。不在 `start_scheduler` 中增加 `DateTrigger` 启动后立刻全量极值（避免拖慢启动、未迁移时误跑）；首次数据依赖运维执行 **CLI 全量脚本**（见 [quickstart.md](./quickstart.md)）。
- **手动触发方式**（规格要求至少一种）:
  - [ ] HTTP 接口：~~不提供~~（全量禁止 HTTP）。
  - [x] **管理命令/脚本**：`cd backend && python scripts/recompute_hist_extrema_full.py`（脚本名以实现为准，见 quickstart）。
  - [ ] 增量：**不提供**单独 HTTP；开发调试可临时在 Python shell 中调用服务层函数。
- **失败与重试**: APScheduler **默认不对本 job 自动重试**；单次失败记录 `log_scheduled_job_failure`（与 `_job_sync_stock` 同模式，复用 `app.core.scheduled_job_logging`）；**下一交易日 18:00** 自然再次执行。不在任务内做多次重试以免 DB 压力；若需人工补跑，执行 CLI 全量或日后加运维脚本单次增量。
- **日志与可观测**: 任务开始/结束 INFO；包含 `trade_date`、更新行数、耗时（秒）；异常时 ERROR + `log_scheduled_job_failure`。

**增量算法摘要（与 [research.md](./research.md) 一致）**:

1. 取 `T = get_latest_open_trade_date(date.today())`；若 `T != date.today()` 则跳过（非交易日）。
2. 集合 `S` = 在 `stock_daily_bar` 中满足 `trade_date = T` 的 `distinct stock_code`。
3. 对 `S` 中每个 code（或批量 SQL）：`SELECT MAX(high), MIN(low) FROM stock_daily_bar WHERE stock_code = ?`，更新 `stock_basic` 对应 `code`；`hist_extrema_computed_at = NOW()`。
4. 对 `S` 为空：可记 INFO「无当日日线，跳过」；**不**清空已有极值。

### 其他关键设计

- **复权**: 不引入；直接使用 `stock_daily_bar.high`/`low` 存储值（见 research）。
- **并发**: 全量脚本与 18:00 增量不建议并行；运维文档注明「全量 CLI 尽量在交易空闲期执行」。
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
│   ├── core/scheduler.py            # 18:00 增量 job
│   ├── models/stock_basic.py        # 三列 ORM
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

**结构说明**: 调度与业务逻辑集中在 `scheduler` + `stock_hist_extrema_service`，与现有 `stock_sync`、策略定时任务风格一致；前端仅扩展 003 页面，不新增路由。

## 复杂度与例外

无额外章程违反项；若全市场单次聚合超时，可在实现阶段将全量 CLI 改为分批 `LIMIT` 更新，无需变更规格口径。
