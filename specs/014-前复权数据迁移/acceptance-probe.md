# 探测接口验收（SC-006）

**状态**：**已通过**（用户确认本地探测无误）

| 项 | 内容 |
|----|------|
| 日期 | 2026-03-28 |
| 执行人 | 项目维护者（用户确认） |
| 环境 | 本地（127.0.0.1:8000） |

## 检查项

- [x] `GET /api/admin/tushare-probe/pro-bar-qfq` 返回 200，`sample` 非空，价格为前复权口径（抽样 000001.SZ 等）
- [x] `GET /api/admin/tushare-probe/stk-week-month-adj-qfq` 返回 200，`sample` 中含 `open_qfq` 或已映射 OHLC（与接口一致）
- [x] 请求/响应已脱敏存档（不保存明文 Token）

## 附：示例 curl

见 [quickstart.md](./quickstart.md) 第 3 节。

## 后续（非本文件范围）

- **T014**：生产/预发库**清空 + 全量回灌**须在维护窗口执行，见 [migration-runbook.md](./migration-runbook.md)；执行前务必备份数据库。
