# 任务清单：首页投资逻辑

**说明**：由 `/speckit.implement` 在缺少预生成 `tasks.md` 时按 `plan.md` 直接实现后补记。

## 已完成

- [x] **T001** 后端：`InvestmentLogicEntry` 模型、`schemas`、`investment_logic_service` 校验与当前条目查询
- [x] **T002** 后端：`/api/investment-logic` 路由（current、entries CRUD），注册 `main.py`
- [x] **T003** 数据库：脚本 `backend/scripts/migrations/004_investment_logic_entry.sql`
- [x] **T004** 前端：`api/investmentLogic.ts`、`HomeView.vue`（显著区、空状态、历史表、弹窗、Tooltip）
- [x] **T005** 前端：`npm run build` 通过

## 待运维 / 本地

- [ ] 在目标 MySQL 执行迁移 SQL 创建 `investment_logic_entry` 表
