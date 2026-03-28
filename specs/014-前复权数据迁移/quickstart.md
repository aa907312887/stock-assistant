# 快速开始：前复权迁移验证

本文档说明如何在本地/预发环境验证 **Tushare 探测接口**、**清空脚本**与**回灌**顺序；路径以仓库实际代码为准。

---

## 0. 迁移前检查（运维）

执行 `truncate_for_qfq_migration.sql` 或生产回灌前必须完成：

| 检查项 | 说明 |
|--------|------|
| `TUSHARE_TOKEN` / `ADMIN_SECRET` | 已在 `backend/.env` 配置且有效 |
| 数据库备份 | 全库或关键表备份已完成；**备份路径**：________；**责任人**：________ |
| 维护窗口 | 已通知；可接受长耗时回灌 |
| 探测验收 | 见 [acceptance-probe.md](./acceptance-probe.md)（SC-006） |

---

## 1. 环境准备

1. **后端**：`backend/.env` 配置  
   - `TUSHARE_TOKEN`：有效 Token（需满足 `stk_week_month_adj` 积分要求时才能测周月线探测）。  
   - `ADMIN_SECRET`：管理接口鉴权，与下述 `curl` 中请求头一致。  
2. **数据库**：MySQL 连接串与 `docs/数据库设计.md` 一致，库名通常为 `stock_assistant`。

---

## 2. 启动后端

在 `backend` 目录：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

（若项目使用其他启动方式，以 `README` 为准。）

---

## 3. 调用日线前复权探测接口（门禁）

实现完成后，示例：

```bash
curl -sS -H "X-Admin-Secret: YOUR_ADMIN_SECRET" \
  "http://127.0.0.1:8000/api/admin/tushare-probe/pro-bar-qfq?ts_code=000001.SZ&start_date=20240102&end_date=20240105&limit=10"
```

**期望**：HTTP 200，`ok: true`，`sample` 非空，且业务确认价格为前复权口径。

将本次请求与响应**保存为验收附件**（脱敏 Token），满足 `spec.md` SC-006。

---

## 4. 数据清空与回灌（运维向）

> **警告**：以下操作会删除业务数据，仅在维护窗口、已备份前提下执行。

1. 执行 `backend/scripts/truncate_for_qfq_migration.sql`（或按 `data-model.md` 调整）；详见 [migration-runbook.md](./migration-runbook.md)。  
2. 使用现有管理接口触发全量同步（示例，参数以 `TriggerSyncRequest` 为准）：

```bash
curl -sS -X POST -H "X-Admin-Secret: YOUR_ADMIN_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"mode":"backfill","modules":["basic","daily","weekly","monthly"],"start_date":"2010-01-01","end_date":"2026-03-28"}' \
  "http://127.0.0.1:8000/api/admin/stock-sync"
```

3. 同步完成后触发指标回填（若未在编排内自动跑完）：

```bash
curl -sS -X POST -H "X-Admin-Secret: YOUR_ADMIN_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"mode":"full","timeframes":["daily","weekly","monthly"]}' \
  "http://127.0.0.1:8000/api/admin/stock-indicators"
```

4. 大盘温度、策略选股、历史极值：依赖现有定时任务或 `plan.md` 中的手动触发说明。

---

## 5. 常见问题

| 现象 | 可能原因 |
|------|----------|
| 503 ADMIN_SECRET | 未配置 `ADMIN_SECRET` |
| Tushare 报错积分不足 | 升级 Token 或改用有权限的环境测 `stk_week_month_adj` |
| 全市场日线极慢 | `pro_bar` 按标的请求，回灌需分批；属预期，见 `research.md` |
