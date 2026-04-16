# 实现计划：前复权数据迁移

**分支**: `main`（与仓库工作流一致；功能目录为 `014-前复权数据迁移`）  
**日期**: 2026-03-28  
**规格**: [spec.md](./spec.md)

**输入**: 功能规格来自 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/specs/014-前复权数据迁移/spec.md`

**说明**: 本文件由 `/speckit.plan` 填写，达到可直接按方案实现的粒度。

---

## 概要

将本地股票行情从**未复权**全面切换为 **Tushare 前复权**口径：**日线**为 **`daily`（未复权）+ `adj_factor` → `stock_adj_factor` + 本地合成** 写入 `stock_daily_bar`；**周/月线**仍为 `stk_week_month_adj` 的 `*_qfq` 写入 `stock_weekly_bar` / `stock_monthly_bar`。迁移前对约定表**仅删行、不删表**（含 `stock_adj_factor`），并清空派生数据，再按「先联调/探测 → 再全量回灌 → 再重算」恢复。`pro_bar`（qfq）探测保留作对照。

---

## 技术背景

- **语言/版本**: Python 3.x（与 `backend` 一致）
- **主要依赖**: FastAPI、SQLAlchemy、APScheduler、Tushare Pro SDK（`tushare`）、pandas
- **存储**: MySQL（库名 `stock_assistant`）
- **测试**: pytest（`backend/tests/`）
- **目标平台**: 本地/服务器 Linux 或 macOS，浏览器访问前端（本功能以后端与数据为主）
- **项目类型**: Web 后端 + 定时任务 + 管理 HTTP 接口
- **性能目标**：回灌为每标的每窗口 `daily` + `adj_factor` 各一次区间请求（约 2× 原 `pro_bar` 调用量量级），以**可完成**与**不触发 Tushare 限流**为首要目标；增量日全市场 `daily`/`adj_factor` 各 1 次按日接口，通常优于逐标的 `pro_bar`
- **约束**: Tushare 积分与 QPS/调用频率；`stk_week_month_adj` 单次 ≤6000 行需分段
- **规模/范围**: A 股全市场约数千标的 × 历史交易日（回灌），周/月批量接口按日切批

---

## 章程检查

项目 `.specify/memory/constitution.md` 仍为占位模板，**未核定，无强制门禁**。本计划遵守现有代码风格与仓库规则（中文注释、Spec 同步）。

**Phase 1 设计后复检**：无新增违反项。

---

## 关键设计详述

### 数据流与接口职责

```text
[Tushare]
  daily(未复权) + adj_factor ─► stock_adj_factor + 合成前复权 OHLC ─► stock_daily_bar
  daily_basic ───────────────► stock_daily_bar（估值/换手等同行）
  stk_week_month_adj(*_qfq) ──► stock_weekly_bar / stock_monthly_bar
  stock_basic ───────────────► stock_basic（清空后全量）
  index_daily 等 ────────────► market_index_* → 大盘温度重算

[本系统编排]
  run_stock_sync / sync_task_runner
    → 写完 K 线 → stock_indicator_fill_service（均线/MACD）
    → 大盘温度 rebuild / incremental
    → 策略 execute_strategy（定时）
    → 日线 upsert 内 apply_cum_extrema_after_daily_upsert（无 18:00 Job）
```

**后端职责**：

- 封装 `daily` 区间与 `adj_factor` 区间拉取；`merge_daily_unadjusted_with_adj_factor_qfq` 产出与 `normalize_bar` 兼容的日线行；`stock_adj_factor` 与 `stock_daily_bar` 同步写入。
- 封装 `stk_week_month_adj`：在 `normalize_bar` 之前将 `open_qfq` 等映射为 `open`/`high`/`low`/`close`，再统一单位换算（成交量额与现逻辑一致）。
- **日线全市场某日同步**：`daily(trade_date)` + `adj_factor(trade_date)` 各一次，再按标的合并；缺因子标的跳过日线写入。
- **周/月**：`get_stk_weekly_monthly_by_trade_date` 调用 `pro.stk_week_month_adj`，`freq=week|month`，字段取 qfq。

**前端职责**：本阶段**无必须 UI 变更**；若需在「同步监控」页展示新批次说明，可后续迭代。

**错误约定**：Tushare 异常统一转为 `TushareClientError` 或 HTTP 502/500 + `detail` 文本；管理探测接口见 `contracts/admin-tushare-probe.md`。

---

### 定时任务与部署设计

本功能**涉及**定时任务（沿用现有，不改调度时刻，仅改数据源与清空/回灌流程）。

- **使用的组件**: **APScheduler** `BackgroundScheduler`，位置：`/Users/yangjiaxing/Coding/CursorProject/stock-assistant/backend/app/core/scheduler.py`。
- **注册方式**: 在 FastAPI **`lifespan` 启动**时调用 `start_scheduler()`（见 `backend/app/main.py`），于应用进程内注册全部 Cron 与一次性 bootstrap 任务。
- **调度策略**（与现网一致，本功能不强制改时刻）：
  - **17:00** `Asia/Shanghai`：`_job_sync_stock` → `ensure_auto_tasks_for_trade_date` + `execute_pending_auto_sync`（股票 basic/日/周/月等子任务）。
  - **17:10**：`_job_sync_market_temperature` 大盘温度增量。
  - **启动后约 30 秒**：再次执行大盘温度（bootstrap），避免冷启动遗漏。
  - **17:20**：冲高回落、恐慌回落策略。
  - ~~**18:00**：历史极值~~ **已移除**：`cum_hist_*` 在日线写入流程内维护（见 `stock_hist_extrema_service.apply_cum_extrema_after_daily_upsert`）。
- **部署时是否执行一次**：**是**——启动后 **30 秒** 执行一次大盘温度（`DateTrigger`）；**不**在启动时自动全量股票同步（避免部署拖死）。
- **手动触发方式**（已存在，迁移后仍使用）：
  - [x] **HTTP**：`POST /api/admin/stock-sync`（`X-Admin-Secret`），请求体支持 `mode`、`modules`、`start_date`、`end_date` 等（见 `TriggerSyncRequest`）。
  - [x] **HTTP**：`POST /api/admin/stock-indicators` 触发指标回填。
  - [x] **代码**：`app.core.scheduler.run_sync_once_now(...)` 供内部或脚本调用。
- **新增手动方式（本功能）**：
  - `GET /api/admin/tushare-probe/pro-bar-qfq`（及可选周月探测）——**仅探测，不写库**，详见 `contracts/admin-tushare-probe.md`。
- **失败与重试**：
  - Tushare 层：`tushare_client` 已设 `MAX_RETRIES=3`、`RETRY_INTERVAL_SEC=5`、请求前 `_rate_pause()`；迁移后 `pro_bar` 循环需避免放大突发流量，可在循环内保留相同 pause。
  - 调度任务：异常走 `log_scheduled_job_failure`，不自动无限重试；由次日 Cron 或人工 `POST /api/admin/stock-sync` 补数。
- **日志与可观测**：保持 `logger.info` 打印 `batch_id`、`trade_date`、写入行数；`pro_bar` 建议每 N 只打印进度（与现周月回灌「每 5～10 批打印」类似），避免日志爆炸。

---

### 其他关键设计

1. **清空脚本**：在 `backend/scripts/` 新增 SQL 或 Python 脚本，按 `data-model.md` 顺序 `TRUNCATE`/`DELETE`；**禁止** `DROP TABLE`。执行前要求备份。
2. **探测接口门禁**：合并正式同步前，必须在检查表记录 `GET .../pro-bar-qfq` 成功样例（SC-006）。
3. **周/月补充逻辑**：`_supplement_weekly_from_daily` / `_supplement_monthly_from_daily` 依赖 `stock_daily_bar` 聚合；日线改为前复权后，**补充 K 线与批量接口周月线应同为前复权口径**，避免混用；若发现语义冲突，优先以 `stk_week_month_adj` 落库为准，补充逻辑仅当规格允许时使用（在实现 PR 中注明）。
4. **指数与大盘温度**：指数 `index_daily` 本身无股票复权问题；若温度公式混用个股与指数，个股侧数据已全部前复权后需回归验证温度数值区间。
5. **用户持仓收益**：`user_position` 中收益依赖现价时，现价应来自前复权日线收盘价，与规格一致。

---

## 项目结构

### 本功能文档

```text
specs/014-前复权数据迁移/
├── plan.md              # 本文件
├── research.md          # Phase 0 调研结论
├── data-model.md        # Phase 1 数据模型
├── quickstart.md        # Phase 1 本地运行与验证
├── contracts/
│   └── admin-tushare-probe.md   # 管理端探测接口契约
└── tasks.md             # 由 /speckit.tasks 生成（若启用）
```

### 源码结构（与本功能强相关）

```text
/Users/yangjiaxing/Coding/CursorProject/stock-assistant/backend/
├── app/
│   ├── api/
│   │   └── admin.py                    # 新增探测路由注册
│   ├── core/
│   │   └── scheduler.py                # 调度（逻辑少改）
│   ├── services/
│   │   ├── tushare_client.py           # pro_bar、stk_week_month_adj 封装
│   │   ├── stock_daily_bar_sync_service.py
│   │   ├── stock_weekly_bar_sync_service.py
│   │   ├── stock_monthly_bar_sync_service.py
│   │   ├── stock_sync_orchestrator.py
│   │   ├── stock_indicator_fill_service.py
│   │   ├── market_temperature/         # 温度重算入口
│   │   └── stock_hist_extrema_service.py
│   └── schemas/                        # 探测接口 Pydantic（若需要）
├── scripts/                            # 新增清空 SQL/说明
└── tests/                              # 探测接口与 normalize 单测（建议）
```

**结构说明**：同步主链路集中在 `services`；探测接口挂在 `admin` 路由下，与现有 `X-Admin-Secret` 一致，降低暴露面。

---

## 复杂度与例外

> 章程占位，无强制违反项；下列为范围说明，非「违反」。

| 项 | 说明 |
|----|------|
| 请求量显著增加 | `pro_bar` 按标的调用，全市场日线回灌耗时与配额压力上升；通过限速、分批、可选夜间任务缓解。 |
| 与现 `stk_weekly_monthly` 代码路径分叉 | 需完整替换为 `stk_week_month_adj` 并回归周月增量与回灌。 |

---

## Phase 2（本命令范围说明）

本 `/speckit.plan` 命令在 **Phase 1 设计文档与契约**完成后结束；**任务拆解**由 `/speckit.tasks` 生成 `tasks.md`（若项目启用）。
