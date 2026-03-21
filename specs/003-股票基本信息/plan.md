# 实现计划：股票基本信息

**分支**: `master` | **日期**: 2026-03-21 | **规格**: [spec.md](./spec.md)  
**输入**: 功能规格来自 `/specs/003-股票基本信息/spec.md`

**说明**: 全文使用中文，粒度达到**可直接按方案实现**。本功能与 `002-综合选股` **共用** `stock_basic` 表与 Tushare `stock_basic` 数据源；新增**仅针对基础信息的周频同步**、**无鉴权**的查询/手动同步接口，以及独立**前端页面**（含悬浮能力说明，见 `.cursor/rules/frontend-product-capability-hints.mdc`）。

## 概要

- **目标**：每周自动从数据源拉取并落库**全市场股票基本信息**；提供**无鉴权**的手动同步入口；提供**分页 + 筛选**的列表查询接口；提供独立**股票基本信息**页面，展示最近同步时间等时效信息，并在标题旁用 **Tooltip** 展示本页产品能力说明（不占大块版面）。
- **技术路线**：后端在现有 FastAPI + SQLAlchemy + APScheduler + Tushare 体系上，新增 `stock_basic_sync_service`（仅写 `stock_basic`）、扩展调度器注册**周任务**、新增 `api/stock_basic` 路由（**不**使用 `Depends(get_current_user)` / `X-Admin-Secret`）；前端 Vue 3 + Element Plus 新增路由与视图，表格分页筛选，手动同步按钮调用新接口。
- **与 002 关系**：`002` 的每日 17:00 **全量同步**仍会更新 `stock_basic` 第一段；本功能**额外**满足规格中的「每周至少一次」**可观测**的基础信息同步任务，并与综合选股共享同一张主数据表。

## 技术背景

- **语言/版本**: Python 3.12（后端）、TypeScript（前端，Vue 3 + Vite）
- **主要依赖**: FastAPI、SQLAlchemy、MySQL、APScheduler、tushare、pandas；前端 Element Plus、Pinia、vue-router
- **存储**: MySQL，核心实体为已有表 **`stock_basic`**（本功能原则上**不新增业务表**；若需记录「最后一次纯基础同步」可选在配置或日志中体现，默认用 `MAX(stock_basic.synced_at)` 作为列表接口的「数据新鲜度」参考）
- **测试**: pytest（后端，按需）；前端以手工与接口契约为准（与仓库现状一致）
- **目标平台**: 本地/服务器浏览器、局域网 API
- **项目类型**: Web 应用（前后端分离）
- **性能目标**: 列表首屏 **3 秒内**可见内容或明确加载态（与 spec SC-001 一致）；单页分页查询仅扫描当前页所需数据（`LIMIT/OFFSET` 或等价），避免一次性加载全市场到前端
- **约束**: Tushare `stock_basic` 接口积分与频率以官网为准；本功能**不做**登录、角色、管理员等权限管理（与 spec 一致；若部署层有反向代理鉴权，不在本功能代码内实现）
- **规模/范围**: A 股全市场约数千条 `stock_basic` 记录

## 章程检查

- 仓库内 `.specify/memory/constitution.md` 仍为占位模板，**未核定**具体原则与强制门禁。
- **结论**: 无强制章程门禁；本计划按 `003` 规格与项目既有技术栈执行。

## 关键设计详述

### 数据流与接口职责

1. **数据源 → 后端**  
   - 调用已有 `app/services/tushare_client.get_stock_list()`（底层为 Tushare `stock_basic`），得到 `dm/mc/jys` 及后续可扩展字段映射。  
   - **仅基础同步**路径不写 `stock_daily_quote`、`stock_financial_report`。

2. **后端 → 数据库**  
   - 新服务模块（建议路径：`backend/app/services/stock_basic_sync_service.py`）提供 `run_sync_basic_only(db: Session) -> dict[str, int]`：  
     - 拉取列表后按 `code` **upsert** `stock_basic`；  
     - 将 Tushare 返回的 `area`、`industry`、`list_date` 等映射到 ORM 字段（`region`、`industry_name` 或 `industry_code` 等，与现有 `StockBasic` 模型及 `docs/数据库设计.md` 对齐）；  
     - `sync_batch_id` 建议形如 `basic-{YYYY-MM-DD}-weekly` 或带时间戳，便于区分「纯基础同步」与全量任务；  
     - 批量 `commit` 策略与 `stock_sync_service` 类似（如每 500 条），打 INFO 日志（开始、结束、写入条数、异常）。

3. **定时任务**  
   - 见下节「定时任务与部署设计」。

4. **手动触发**  
   - `POST /api/stock/basic/sync`：**无请求体鉴权**；在后台线程中执行 `run_sync_basic_only`，立即返回 **202** + `{ "status": "started", "message": "..." }`（与现有 admin 全量同步返回风格一致，但不校验 `X-Admin-Secret`）。  
   - **注意**：与 `POST /api/admin/stock-sync`（全量 + 需 `ADMIN_SECRET`）**并存**，前端「股票基本信息」页只调新接口。

5. **页面查询**  
   - `GET /api/stock/basic`（或 `/api/stock/basic/list`）：**无 JWT**；Query 参数：`page`、`page_size`（上限如 100）、`code`（模糊）、`name`（模糊）、`market`（可选精确/前缀）、`industry`（可选模糊）等。  
   - 响应 JSON：`items[]`（字段与 `StockBasic` 对外展示一致）、`total`、`page`、`page_size`、**`last_synced_at`**（对 `stock_basic.synced_at` 取 **MAX**，表示库内基础信息最近一次写入时间，满足 FR-005）。  
   - 排序：默认按 `code` 升序（可配置）。

6. **前端**  
   - 新页面组件（建议：`frontend/src/views/StockBasicView.vue`），路由如 `/stock-basic`。
   - **侧栏菜单**：一级菜单 **「股票信息」**（`el-sub-menu`），下挂 **「综合选股」**（`/stock-screening`）与 **「股票基本信息」**（`/stock-basic`），与 Layout 中实现保持一致。  
   - **路由与登录**：当前全局 `requiresAuth: true` 下，用户需登录进入应用后才能打开侧栏菜单；**本功能不在页面内做角色判断**；若产品要求「页面也可匿名访问」，可将该路由拆出 Layout 并设 `meta.guest: true`（**可选**，实现阶段按产品二选一，本计划默认**仍挂在 Layout 下**以降低改动面）。  
   - 页面标题旁放置 **el-tooltip**（或 `el-icon` + `title`），文案为**中文短说明**：本页展示范围（仅基础信息、不含行情/K 线）、数据更新方式（每周定时 + 手动）、与综合选股的关系（共享主数据）。  
   - 表格列：代码、名称、市场、行业、地域、上市日期、`synced_at`（或格式化展示）等；顶部展示 `last_synced_at`；「手动同步」按钮调 `POST /api/stock/basic/sync`，展示返回信息与 loading 状态。

7. **错误约定**  
   - 列表/同步失败返回 JSON `{ "detail": "中文可读说明" }`，HTTP 4xx/5xx 与现有项目一致；不在响应中暴露堆栈（开发环境全局 handler 除外）。

### 定时任务与部署设计

本功能**涉及**定时任务（周频基础信息同步）。

- **使用的组件**: **APScheduler** `BackgroundScheduler`，复用 `backend/app/core/scheduler.py`；与现有 `stock_sync` 任务**同一调度器实例**。

- **注册方式**: 在现有 `start_scheduler()` 内**追加** `add_job`，**不得**重复创建第二个 `BackgroundScheduler`。若需从环境变量读取周频 cron，在 `start_scheduler()` 中解析后注册。

- **调度策略**: 默认 **每周一次**，建议 **周一 03:00**（`Asia/Shanghai`），对应 cron 语义：`分 时 日 月 周` → `0 3 * * mon`（以 APScheduler `CronTrigger` 为准，使用 `day_of_week='mon'` + `hour=3` + `minute=0`）。  
  - 配置项（建议）：环境变量 `STOCK_BASIC_WEEKLY_HOUR`、`STOCK_BASIC_WEEKLY_MINUTE`、`STOCK_BASIC_WEEKLY_WEEKDAY`（0=周一 … 或字符串 `mon`），缺省为上述默认值；写入 `backend/.env.example` 说明。

- **任务入口函数**: 新建 `_job_sync_stock_basic_only()`：创建 `SessionLocal()`，调用 `run_sync_basic_only(db)`，`finally` 中 `db.close()`；异常 `logger.exception`，不抛出到调度器线程外。

- **部署时是否执行一次**: **否**（与「仅基础信息」一致，避免与现有「延迟 30 秒全量同步」重复冲击数据源）。若运维需要首次灌库，使用**手动同步**或保留现有全量脚本。

- **手动触发方式**（至少一种，本功能实现两种以便运维）：  
  - [x] **HTTP**：`POST /api/stock/basic/sync`，**无鉴权**  
  - [x] **管理命令**（建议）：`python -m app.scripts.sync_stock_basic`（在 `backend` 目录、加载 `.env`），内部调用 `run_sync_basic_only`  
  - [ ] 脚本 shell：可选 `scripts/sync-stock-basic.sh` 包装上述命令（按需）

- **失败与重试**: `run_sync_basic_only` 内对 Tushare 调用复用 `tushare_client` 已有重试；任务失败打 **ERROR** 日志；**不在调度器层无限重试**；下次仍按周触发。

- **日志与可观测**: 任务开始/结束、写入条数、耗时；关键字建议 `stock_basic_weekly` 便于 grep。

- **并发**: 若周任务与每日 17:00 全量同步**时间重叠**，依赖 MySQL 行级更新与事务；若出现锁等待，以日志为准；**可选**在后续迭代对 `run_sync` / `run_sync_basic_only` 加互斥锁（本阶段**不强制**，在 `research.md` 中记录风险）。

### 其他关键设计

- **无鉴权接口暴露风险**：规格明确不做应用层权限；生产环境应在**网关/防火墙**限制内网或 VPN 访问；计划在 `quickstart.md` 中提示。  
- **分页上限**: `page_size` 默认 20，最大 100（与综合选股一致）。  
- **CORS**: 沿用 `main.py` 现有全局 CORS。  
- **与现有 `stock_sync_service` 代码复用**: 抽取「仅写 stock_basic」循环为共用函数（可选重构），避免两处逻辑长期分叉。

## 项目结构

### 本功能文档

```text
specs/003-股票基本信息/
├── plan.md              # 本文件
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── api-stock-basic.md
├── spec.md
└── checklists/
    └── requirements.md
```

### 源码结构（拟新增/修改）

```text
backend/
├── app/
│   ├── api/
│   │   └── stock_basic.py       # 新增：GET 列表、POST 手动同步（无 Depends 鉴权）
│   ├── core/
│   │   └── scheduler.py         # 修改：注册周任务 _job_sync_stock_basic_only
│   ├── services/
│   │   └── stock_basic_sync_service.py  # 新增：run_sync_basic_only
│   ├── scripts/
│   │   └── sync_stock_basic.py  # 新增：CLI
│   └── main.py                  # 修改：include_router(stock_basic_router)
└── ...

frontend/
├── src/
│   ├── views/
│   │   └── StockBasicView.vue   # 新增
│   ├── api/
│   │   └── stockBasic.ts        # 新增：封装 GET/POST
│   └── router/index.ts          # 修改：子路由 /stock-basic
```

**结构说明**: 后端将「无鉴权股票基础」独立路由文件，避免与 `api/stock.py`（选股、需登录）混淆；前端独立视图便于挂 Tooltip 与基础列展示。

## 复杂度与例外

> 本功能不引入新中间件；章程无额外违反项。

| 违反项 | 为何需要 | 为何不采用更简单方案 |
|--------|----------|----------------------|
| 无 | — | — |
