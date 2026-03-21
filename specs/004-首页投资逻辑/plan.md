# 实现计划：首页投资逻辑

**分支**: `master` | **日期**: 2026-03-21 | **规格**: [spec.md](./spec.md)  
**输入**: 功能规格 `004` 已升级为：**独立表**、**技术面/基本面/消息面**三面、**权重**、**新增记时**、**增删改查 + 全历史回顾**、首页**空状态友好引导**。

**说明**: 全文使用中文，粒度达到**可直接按方案实现**。

## 概要

- **目标**：首页欢迎 + **显著区**展示**当前**投资逻辑（三面正文 + 三面权重 + 警示语义）；无数据时**友好空状态**；用户可**新增/修改/删除**条目，并查看**全部历史**；每次**新增**记录 **`created_at`**。  
- **技术路线**：新建表 **`investment_logic_entry`**（含 **`extra_json`** 扩展列，见 `data-model.md`）；FastAPI 路由前缀建议 **`/api/investment-logic`**（`current`、`entries` CRUD）；Vue 首页改造 **`HomeView.vue`**，并增加**历史列表**（可同页折叠区、抽屉或独立路由 `/investment-logic/history`，实现阶段二选一，契约以资源为准）。  
- **与旧方案差异**：**不再**使用 `user` 单列 `TEXT` 存全文；登录与 `GET /auth/me` **不强制**携带三面长文（以 `GET .../current` 为准）。

## 技术背景

- **语言/版本**: Python 3.12、TypeScript + Vue 3 + Vite  
- **主要依赖**: FastAPI、SQLAlchemy、MySQL、Pydantic；Element Plus、Pinia、vue-router  
- **存储**: MySQL，新表 **`investment_logic_entry`**，外键 **`user_id` → user.id**  
- **测试**: pytest（校验权重和、越权 404、空三面等）；前端手工 + 契约  
- **性能**: 单用户历史条数预期 < 数百条，列表一次性返回可接受；若增长再分页（后续迭代）  
- **约束**: 三面权重整数且和为 100；禁止跨用户访问  

## 章程检查

- `.specify/memory/constitution.md` 仍为占位；**无强制门禁**。

## 关键设计详述

### 数据流与接口职责

1. **首页加载**  
   - 已登录 → 调 **`GET /api/investment-logic/current`**。  
   - `entry === null` → 渲染**空状态**（友好文案 + 去填写按钮）→ 打开表单走 **`POST /api/investment-logic/entries`**。  
   - `entry` 有值 → 显著区展示三面、权重、警示标题；数据来自响应 JSON。

2. **新增**  
   - 表单：三面 `textarea` + 三个权重输入（或滑块归一化）；前端预校验和为 100。  
   - **`POST /api/investment-logic/entries`** → 写库，`created_at` / `updated_at` 由服务端赋值。

3. **修改**  
   - 用户在历史列表或「编辑当前」进入 → **`PUT /api/investment-logic/entries/{id}`** → 更新正文与权重，**刷新 `updated_at`**。

4. **删除**  
   - **`DELETE /api/investment-logic/entries/{id}`** → 物理删除。删除后首页重新拉 `current`，按规则取新的「当前」或空状态。

5. **历史列表**  
   - **`GET /api/investment-logic/entries`** → 展示时间线；每条展示 `created_at`（及可选 `updated_at` 说明「曾修改」）。

6. **前端产品提示**  
   - 遵守 `.cursor/rules/frontend-product-capability-hints.mdc`：标题旁 **Tooltip** 简述本页能力（三面、权重、历史回顾），**不占大块首屏**。

### 定时任务与部署设计

本功能**不涉及定时任务**。

### 其他关键设计

- **路由**：最低限度改 **`/` 首页**；历史若数据量大可后续加分页参数 `page`/`page_size`（契约可预留，首版可省略）。  
- **安全**：所有 ORM 查询带 `user_id == current_user.id`。  
- **日志**：禁止 INFO 级打印三面全文。  
- **迁移**：`CREATE TABLE` SQL 见 `quickstart.md`；若已有 `user.investment_logic`，提供**一次性迁移说明**（导入一条或弃用）。

## 项目结构

### 本功能文档

```text
specs/004-首页投资逻辑/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/investment-logic-api.md
└── checklists/requirements.md
```

### 源码结构（拟变更）

```text
backend/app/
├── models/investment_logic_entry.py
├── schemas/investment_logic.py
├── api/investment_logic.py          # router 注册到 main.py prefix=/api
├── services/investment_logic_service.py  # 当前条目解析、校验权重与正文
frontend/src/
├── api/investmentLogic.ts
├── views/HomeView.vue               # 显著区 + 空状态 + 弹窗表单
└── views/InvestmentLogicHistoryView.vue  # 可选：或 Home 内嵌列表
```

## Phase 0 / Phase 1 产出核对

- [x] `research.md`  
- [x] `data-model.md`  
- [x] `contracts/investment-logic-api.md`  
- [x] `quickstart.md`（随 SQL 更新）  

**下一步**：`/speckit.tasks` 或按契约直接开发；**同步** `docs/数据库设计.md` 第 1.2 节。
