# 数据模型：手动模拟交易

**日期**: 2026-06-06 | **规格**: [spec.md](./spec.md) | **调研**: [research.md](./research.md)

## 新增表

### 1. `manual_trading_session`（手动模拟会话）

一次比例跟盘验算的主记录；持仓名义金额与参考价冗余存于会话，便于快速读取。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 自增主键 |
| `session_id` | VARCHAR(64) | UNIQUE, NOT NULL | 业务 ID，格式 `mt-{uuid8}` |
| `user_id` | BIGINT | NOT NULL | 所属用户 |
| `name` | VARCHAR(100) | NULL | 会话备注名（可选） |
| `asset_name` | VARCHAR(100) | NOT NULL | 自定义标的名称，如「纳斯达克100」 |
| `start_date` | DATE | NOT NULL | 起始模拟日 |
| `current_date` | DATE | NOT NULL | 当前模拟日 |
| `reference_price` | DECIMAL(16,4) | NULL | 比例跟盘参考价；首买或录价后更新 |
| `position_value` | DECIMAL(20,2) | NOT NULL, DEFAULT 0 | 持仓名义金额（元） |
| `total_invested` | DECIMAL(20,2) | NOT NULL, DEFAULT 0 | 累计买入金额（元） |
| `awaiting_reval` | TINYINT(1) | NOT NULL, DEFAULT 0 | 是否待录入收盘价：0 否 / 1 是 |
| `last_advance_step` | VARCHAR(10) | NULL | 最近一次推进步长（待录价期间保留，供 reval 流水） |
| `first_operation_date` | DATE | NULL | 首笔操作日（买入），用于总交易时间 |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'active' | `active` 进行中 / `ended` 已结束 |
| `end_date` | DATE | NULL | 结束日（结束交易时写入） |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| `updated_at` | DATETIME | NOT NULL, ON UPDATE CURRENT_TIMESTAMP | 更新时间 |

**索引**：

| 索引名 | 类型 | 字段 | 用途 |
|--------|------|------|------|
| `uk_mts_session_id` | UNIQUE | `session_id` | 按业务 ID 查询 |
| `idx_mts_user_status` | INDEX | `user_id, status, created_at` | 用户会话列表 |

**状态流转**：

```text
active（awaiting_reval=0）→ 买入 / 发起推进
active（awaiting_reval=1）→ 仅允许录价
active → ended（结束交易，须已有买入流水）
```

**派生指标（API 计算，不落库）**：

- `total_pnl` = `position_value` − `total_invested`
- `total_pnl_pct` = `total_pnl / total_invested`（`total_invested > 0` 时）
- `total_trading_days` = `end_date − first_operation_date`（已结束）或 `current_date − first_operation_date`（进行中）

---

### 2. `manual_trading_operation`（操作流水）

会话内有序操作记录；复盘、单次盈亏与间隔均基于此表。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 自增主键 |
| `session_id` | VARCHAR(64) | NOT NULL | 所属会话 |
| `op_type` | VARCHAR(20) | NOT NULL | `buy` / `reval` / `end` |
| `op_date` | DATE | NOT NULL | 操作对应模拟日 |
| `price` | DECIMAL(16,4) | NULL | 成交价或收盘价（`end` 可为 NULL） |
| `buy_amount` | DECIMAL(20,2) | NULL | 买入金额（仅 `buy`） |
| `advance_step` | VARCHAR(10) | NULL | 推进步长：`day`/`week`/`month`/`year`（仅发起推进时在 `reval` 前一条逻辑或合并见下） |
| `position_before` | DECIMAL(20,2) | NOT NULL | 操作前持仓名义金额 |
| `position_after` | DECIMAL(20,2) | NOT NULL | 操作后持仓名义金额 |
| `segment_pnl` | DECIMAL(20,2) | NULL | 本段盈亏（`reval` 写入；`buy`/`end` 为 NULL 或 0） |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 写入时间 |

**索引**：

| 索引名 | 类型 | 字段 | 用途 |
|--------|------|------|------|
| `idx_mto_session_date` | INDEX | `session_id, op_date, id` | 按会话 chronological 查询 |

**说明**：估值推进在实现上拆为两步 API（advance → reval），但**流水仅在 reval 成功时写入一条 `reval` 记录**（含 `advance_step`、`price`、`segment_pnl`），避免半成品流水。`buy` 与 `end` 各写一条。

**间隔天数（API 层计算）**：

对第 i 条操作（i>0）：`days_since_prev = (op_date[i] − op_date[i−1]).days`；首条为 NULL。

---

## 业务规则（校验）

| 规则 | 说明 |
|------|------|
| 创建 | `asset_name` 非空；`start_date` 合法 |
| 买入 | 会话 `status=active` 且 `awaiting_reval=0`；`buy_amount>0`，`price>0` |
| 推进 | 同上；`step ∈ {day,week,month,year}`；推进后 `awaiting_reval=1` |
| 录价 | `awaiting_reval=1`；`close_price>0`；若 `position_value>0` 且 `reference_price>0` 则按比例更新 |
| 结束 | 至少一条 `buy`；`status=active` 且 `awaiting_reval=0` |
| 删除 | 仅所属用户；级联删除该会话全部 `manual_trading_operation` |
| 已结束 | 只读，拒绝 buy/advance/reval |

---

## 与现有表关系

- **独立**：不引用 `stock_basic`、`paper_trading_*`。
- **用户**：`user_id` → `user.id`（逻辑外键，与项目其他模块一致可不建 DB FK）。

---

## 迁移脚本

新增 `backend/scripts/add_manual_trading_tables.sql`，并登记到 `backend/scripts/run_migration.py`（若项目使用该入口）。
