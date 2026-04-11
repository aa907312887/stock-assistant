# 数据模型：历史模拟交易

**日期**: 2026-04-09 | **规格**: `./spec.md` | **调研**: `./research.md`

## 新增表

### 1. `paper_trading_session`（模拟交易会话）

一次交互式历史模拟交易游戏的主记录，包含起始配置、当前进度和账户状态。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 自增主键 |
| `session_id` | VARCHAR(64) | UNIQUE, NOT NULL | 业务唯一标识，格式 `pt-{uuid8}` |
| `name` | VARCHAR(100) | NULL | 用户自定义会话名称（如「2021年牛市复盘」） |
| `start_date` | DATE | NOT NULL | 模拟起始日期（用户选择的历史节点） |
| `current_date` | DATE | NOT NULL | 当前模拟日期（随「进入下一交易日」推进） |
| `current_phase` | VARCHAR(10) | NOT NULL, DEFAULT 'open' | 当前时间节点：`open`（开盘）/ `close`（收盘） |
| `initial_cash` | DECIMAL(20,2) | NOT NULL | 初始资金（元） |
| `available_cash` | DECIMAL(20,2) | NOT NULL | 当前可用现金（元） |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'active' | 会话状态：`active`（进行中）/ `ended`（已结束） |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| `updated_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE | 最后更新时间 |

**索引**：

| 索引名 | 类型 | 字段 | 用途 |
|--------|------|------|------|
| `uk_pts_session_id` | UNIQUE | `session_id` | 按 session_id 查询 |
| `idx_pts_status` | INDEX | `status, created_at` | 按状态筛选 + 排序 |

**状态流转**：

```
active → ended（用户主动结束会话）
```

---

### 2. `paper_trading_position`（持仓批次）

每次买入操作产生一条独立记录，支持 FIFO 卖出和精确 T+1 判断。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 自增主键，FIFO 排序依据之一 |
| `session_id` | VARCHAR(64) | NOT NULL | 所属会话标识 |
| `stock_code` | VARCHAR(20) | NOT NULL | 股票代码（如 `000001.SZ`） |
| `stock_name` | VARCHAR(50) | NULL | 股票名称（冗余存储，避免关联查询） |
| `buy_date` | DATE | NOT NULL | 买入日期（模拟日期），T+1 判断依据 |
| `buy_price` | DECIMAL(12,4) | NOT NULL | 买入价格（用户输入） |
| `quantity` | INT | NOT NULL | 持仓数量（股），必须为 100 的整数倍 |
| `remaining_quantity` | INT | NOT NULL | 剩余未卖出数量（初始等于 quantity） |
| `commission` | DECIMAL(12,4) | NOT NULL | 买入手续费（元） |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'holding' | 批次状态：`holding`（持有中）/ `closed`（已全部卖出） |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**索引**：

| 索引名 | 类型 | 字段 | 用途 |
|--------|------|------|------|
| `idx_ptp_session_stock` | INDEX | `session_id, stock_code, buy_date` | 按会话+股票查询持仓批次（FIFO 排序） |
| `idx_ptp_session_status` | INDEX | `session_id, status` | 查询会话内所有持有中批次 |

**与会话 API 的关联**：当某 `stock_code` 在会话内已无任何 `status='holding'` 批次、但仍存在 `status='closed'` 批次时，后端将会话响应中的 `closed_stocks` 纳入该代码（展示名称、已关闭批次数、**已实现盈亏**等摘要；盈亏由同会话下该代码全部 `paper_trading_order` 汇总：∑(卖出成交额−卖手续费) − ∑(买入成交额+买手续费)，比例相对于买入总成本）。前端「已清仓」列表依赖此聚合，成交明细仍通过 `paper_trading_order` 按 `session_id` + `stock_code` 查询。若用户再次买入同一代码，该代码重新出现 holding 批次后应从 `closed_stocks` 中移除。

---

### 3. `paper_trading_order`（交易记录）

每笔买入或卖出操作的完整记录，用于交易历史查询和账户流水核对。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 自增主键 |
| `session_id` | VARCHAR(64) | NOT NULL | 所属会话标识 |
| `order_type` | VARCHAR(10) | NOT NULL | 交易类型：`buy` / `sell` |
| `stock_code` | VARCHAR(20) | NOT NULL | 股票代码 |
| `stock_name` | VARCHAR(50) | NULL | 股票名称 |
| `trade_date` | DATE | NOT NULL | 交易日期（当前模拟日期） |
| `price` | DECIMAL(12,4) | NOT NULL | 成交价格（用户输入） |
| `quantity` | INT | NOT NULL | 成交数量（股） |
| `amount` | DECIMAL(20,2) | NOT NULL | 成交金额（price × quantity，元） |
| `commission` | DECIMAL(12,4) | NOT NULL | 手续费（元） |
| `cash_after` | DECIMAL(20,2) | NOT NULL | 交易后账户可用现金（元） |
| `position_id` | BIGINT | NULL | 关联的持仓批次 ID（卖出时填写，买入时为 NULL） |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**索引**：

| 索引名 | 类型 | 字段 | 用途 |
|--------|------|------|------|
| `idx_pto_session` | INDEX | `session_id, trade_date` | 按会话查询交易记录 |
| `idx_pto_session_stock` | INDEX | `session_id, stock_code` | 按会话+股票查询 |

---

## 复用现有表（只读）

| 表名 | 用途 |
|------|------|
| `stock_daily_bar` | K 线图数据（日线）、涨跌停计算（prev_close）、技术指标（MA/MACD）、股票筛选 |
| `stock_weekly_bar` | K 线图数据（周线） |
| `stock_monthly_bar` | K 线图数据（月线） |
| `stock_basic` | 股票名称查询 |

---

## 关键业务规则

### 买入流程

```
1. 验证：stock_code 当日有数据（非停牌）
2. 验证：price 在 [prev_close × 0.9, prev_close × 1.1] 范围内
3. 验证：quantity > 0 且 quantity % 100 == 0
4. 计算：amount = price × quantity
5. 计算：commission = max(amount × 0.0003, 5.0)
6. 验证：available_cash >= amount + commission
7. 写入：paper_trading_position（新批次，remaining_quantity = quantity）
8. 写入：paper_trading_order（order_type = 'buy'）
9. 更新：paper_trading_session.available_cash -= (amount + commission)
```

### 卖出流程（FIFO）

```
1. 验证：stock_code 当日有数据（非停牌）
2. 验证：price 在 [prev_close × 0.9, prev_close × 1.1] 范围内
3. 验证：quantity > 0 且 quantity % 100 == 0
4. 查询：该 session 该 stock_code 所有 status='holding' 的批次
         按 buy_date ASC, id ASC 排序
         过滤掉 buy_date == current_date 的批次（T+1）
5. 验证：可卖总量（sum of remaining_quantity）>= quantity
6. FIFO 扣减：从最早批次开始扣减 remaining_quantity
             若某批次 remaining_quantity 归零，status 改为 'closed'
7. 计算：amount = price × quantity
8. 计算：commission = max(amount × 0.0013, 5.0)
9. 写入：paper_trading_order（order_type = 'sell'，position_id 指向最早被扣减的批次）
10. 更新：paper_trading_session.available_cash += (amount - commission)
```

### 持仓聚合展示（前端计算）

前端从 API 获取所有 `status='holding'` 的批次后，按 `stock_code` 聚合：

```
加权均价 = sum(buy_price × remaining_quantity) / sum(remaining_quantity)
总持仓数量 = sum(remaining_quantity)
持仓成本 = sum(buy_price × remaining_quantity)
当前市值 = 当日收盘价 × 总持仓数量
盈亏金额 = 当前市值 - 持仓成本
盈亏比例 = 盈亏金额 / 持仓成本
```

### 推进到收盘

```
1. 验证 session.current_phase == 'open'
2. 更新 session.current_phase = 'close'
3. 返回持仓列表（市值改用当日 close 价格重算）
```

### 进入下一交易日

```
1. 验证 session.current_phase == 'close'（开盘状态不可跳日）
2. 查询下一个交易日（stock_daily_bar 中 > current_date 的最小 trade_date）
3. 更新 session.current_date = 下一交易日，current_phase = 'open'
4. 返回新当日数据（持仓市值暂用新日开盘价）
```
