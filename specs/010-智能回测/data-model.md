# 数据模型：智能回测

**日期**: 2026-03-26 | **规格**: `./spec.md` | **调研**: `./research.md`

## 新增表

### 1. `backtest_task`（回测任务 + 绩效报告）

一次历史回测的执行记录及其绩效统计。绩效报告与任务 1:1，合并存储以减少查询。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 自增主键 |
| `task_id` | VARCHAR(64) | UNIQUE, NOT NULL | 业务唯一标识（UUID 格式） |
| `strategy_id` | VARCHAR(64) | NOT NULL | 策略标识（如 `chong_gao_hui_luo`） |
| `strategy_version` | VARCHAR(32) | NOT NULL | 执行时的策略版本（如 `v1.1.3`） |
| `start_date` | DATE | NOT NULL | 回测起始日期 |
| `end_date` | DATE | NOT NULL | 回测结束日期 |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'running' | 任务状态：`running` / `completed` / `incomplete` / `failed` |
| `total_trades` | INT | NULL | 正常平仓的总交易笔数 |
| `win_trades` | INT | NULL | 盈利交易笔数 |
| `lose_trades` | INT | NULL | 亏损交易笔数（含平局） |
| `win_rate` | DECIMAL(8,4) | NULL | 胜率（win_trades / total_trades），百分比小数形式 |
| `total_return` | DECIMAL(12,4) | NULL | 总收益率（所有单笔收益率之和），百分比小数形式 |
| `avg_return` | DECIMAL(12,4) | NULL | 平均单笔收益率 |
| `max_win` | DECIMAL(12,4) | NULL | 最大单笔盈利（收益率） |
| `max_loss` | DECIMAL(12,4) | NULL | 最大单笔亏损（收益率，负值） |
| `unclosed_count` | INT | NOT NULL, DEFAULT 0 | 未平仓交易笔数 |
| `skipped_count` | INT | NOT NULL, DEFAULT 0 | 因数据缺失跳过的交易笔数 |
| `error_message` | TEXT | NULL | 失败时的错误信息 |
| `assumptions_json` | JSON | NULL | 回测口径与假设（价格类型、数据源等） |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 任务创建时间 |
| `finished_at` | DATETIME | NULL | 任务完成时间 |

**索引**：

| 索引名 | 类型 | 字段 | 用途 |
|--------|------|------|------|
| `uk_backtest_task_id` | UNIQUE | `task_id` | 按 task_id 查询 |
| `idx_backtest_task_strategy` | INDEX | `strategy_id, created_at` | 按策略筛选 + 排序 |
| `idx_backtest_task_status` | INDEX | `status` | 按状态筛选 |

**状态流转**：

```
running → completed  （所有交易正常平仓）
running → incomplete （存在未平仓交易，unclosed_count > 0）
running → failed     （执行过程异常）
```

---

### 2. `backtest_trade`（模拟交易明细）

回测过程中产生的每一笔模拟买卖记录。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 自增主键 |
| `task_id` | VARCHAR(64) | NOT NULL | 所属回测任务标识（关联 `backtest_task.task_id`） |
| `stock_code` | VARCHAR(20) | NOT NULL | 股票代码 |
| `stock_name` | VARCHAR(50) | NULL | 股票名称 |
| `buy_date` | DATE | NOT NULL | 买入日期 |
| `buy_price` | DECIMAL(12,4) | NOT NULL | 买入价格 |
| `sell_date` | DATE | NULL | 卖出日期（未平仓时为 NULL） |
| `sell_price` | DECIMAL(12,4) | NULL | 卖出价格（未平仓时为 NULL） |
| `return_rate` | DECIMAL(12,4) | NULL | 单笔收益率（(sell_price - buy_price) / buy_price），未平仓时为 NULL |
| `trade_type` | VARCHAR(16) | NOT NULL, DEFAULT 'closed' | 交易类型：`closed`（实际成交平仓）/ `not_traded`（同日选中未交易）/ `unclosed`（未平仓） |
| `exchange` | VARCHAR(10) | NULL | 交易所：SSE/SZSE/BSE（来自 `stock_basic.exchange`） |
| `market` | VARCHAR(20) | NULL | 板块：主板/创业板/科创板/北交所等（来自 `stock_basic.market`） |
| `market_temp_score` | DECIMAL(5,2) | NULL | 买入日当天的大盘温度分数（关联 `market_temperature_daily`） |
| `market_temp_level` | VARCHAR(16) | NULL | 买入日当天的大盘温度级别（如"冰点"/"低温"/"温和"/"高温"/"沸腾"） |
| `extra_json` | JSON | NULL | 策略特有的附加信息（如冲高回落的 trigger_date、冲高幅度等） |
| `user_decision` | VARCHAR(16) | NULL | 用户对策略决策的主观评价：`excellent`（优秀）/ `wrong`（错误） |
| `user_decision_reason` | VARCHAR(2000) | NULL | 评价理由 |
| `user_decision_at` | DATETIME | NULL | 评价时间 |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 记录创建时间 |

**索引**：

| 索引名 | 类型 | 字段 | 用途 |
|--------|------|------|------|
| `idx_bt_trade_task_id` | INDEX | `task_id` | 按任务查询交易明细 |
| `idx_bt_trade_stock` | INDEX | `stock_code, buy_date` | 按股票查询 |
| `idx_bt_trade_type` | INDEX | `task_id, trade_type` | 按类型筛选（正常/未平仓） |
| `idx_bt_trade_exchange` | INDEX | `task_id, exchange` | 按交易所分组统计 |
| `idx_bt_trade_market` | INDEX | `task_id, market` | 按板块分组统计 |
| `idx_bt_trade_temp` | INDEX | `task_id, market_temp_level` | 按大盘温度级别分组统计 |

---

## 新增建表 SQL

```sql
-- 智能回测：回测任务 + 绩效报告
CREATE TABLE IF NOT EXISTS backtest_task (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id VARCHAR(64) NOT NULL,
  strategy_id VARCHAR(64) NOT NULL,
  strategy_version VARCHAR(32) NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'running',
  total_trades INT NULL,
  win_trades INT NULL,
  lose_trades INT NULL,
  win_rate DECIMAL(8,4) NULL,
  total_return DECIMAL(12,4) NULL,
  avg_return DECIMAL(12,4) NULL,
  max_win DECIMAL(12,4) NULL,
  max_loss DECIMAL(12,4) NULL,
  unclosed_count INT NOT NULL DEFAULT 0,
  skipped_count INT NOT NULL DEFAULT 0,
  error_message TEXT NULL,
  assumptions_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at DATETIME NULL,
  UNIQUE KEY uk_backtest_task_id (task_id),
  KEY idx_backtest_task_strategy (strategy_id, created_at),
  KEY idx_backtest_task_status (status)
);

-- 智能回测：模拟交易明细
CREATE TABLE IF NOT EXISTS backtest_trade (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id VARCHAR(64) NOT NULL,
  stock_code VARCHAR(20) NOT NULL,
  stock_name VARCHAR(50) NULL,
  buy_date DATE NOT NULL,
  buy_price DECIMAL(12,4) NOT NULL,
  sell_date DATE NULL,
  sell_price DECIMAL(12,4) NULL,
  return_rate DECIMAL(12,4) NULL,
  trade_type VARCHAR(16) NOT NULL DEFAULT 'closed',
  exchange VARCHAR(10) NULL,
  market VARCHAR(20) NULL,
  market_temp_score DECIMAL(5,2) NULL,
  market_temp_level VARCHAR(16) NULL,
  extra_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_bt_trade_task_id (task_id),
  KEY idx_bt_trade_stock (stock_code, buy_date),
  KEY idx_bt_trade_type (task_id, trade_type),
  KEY idx_bt_trade_exchange (task_id, exchange),
  KEY idx_bt_trade_market (task_id, market),
  KEY idx_bt_trade_temp (task_id, market_temp_level)
);
```

---

### 3. `backtest_task` 中的温度分组统计

分组统计结果以 JSON 存入 `backtest_task.assumptions_json`（避免新增表），包含 `temp_level_stats`、`exchange_stats`、`market_stats` 三个字段，结构如下：

```json
{
  "temp_level_stats": [
    {
      "level": "冰点",
      "total": 12,
      "wins": 8,
      "win_rate": 0.6667,
      "avg_return": 0.0234
    },
    {
      "level": "低温",
      "total": 25,
      "wins": 10,
      "win_rate": 0.4000,
      "avg_return": 0.0012
    }
  ],
  "exchange_stats": [
    {
      "name": "SSE",
      "total": 30,
      "wins": 16,
      "win_rate": 0.5333,
      "avg_return": 0.0042
    }
  ],
  "market_stats": [
    {
      "name": "创业板",
      "total": 18,
      "wins": 9,
      "win_rate": 0.5000,
      "avg_return": 0.0068
    }
  ]
}
```

查询时也可直接从 `backtest_trade` 表按 `market_temp_level` 分组聚合实时计算。

---

## 与现有表的关系

| 现有表 | 关系 | 说明 |
|--------|------|------|
| `stock_daily_bar` | 读取 | 回测策略读取日线数据进行模拟交易 |
| `stock_basic` | 读取 | 补齐股票名称 |
| `market_temperature_daily` | 读取 | 回测引擎根据买入日期查询当天大盘温度分数与级别，写入 `backtest_trade` |
| `strategy_execution_snapshot` | 无直接关联 | 当日选股执行与回测是独立场景 |

## 策略接口新增数据类

以下数据类新增于 `backend/app/services/strategy/strategy_base.py`：

### `BacktestTrade`（回测交易记录）

```python
@dataclass(frozen=True)
class BacktestTrade:
    """回测中的单笔模拟交易。"""
    stock_code: str
    stock_name: str | None
    buy_date: date
    buy_price: float
    sell_date: date | None          # 未平仓时为 None
    sell_price: float | None        # 未平仓时为 None
    return_rate: float | None       # 未平仓时为 None
    trade_type: str                 # "closed" 或 "unclosed"
    market_temp_score: float | None # 买入日大盘温度分数
    market_temp_level: str | None   # 买入日大盘温度级别
    extra: dict[str, Any]           # 策略特有附加信息
```

### `BacktestResult`（策略回测返回值）

```python
@dataclass(frozen=True)
class BacktestResult:
    """策略 backtest() 方法的返回值。"""
    trades: list[BacktestTrade]
    skipped_count: int
    skip_reasons: list[str]
```
