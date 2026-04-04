# 数据模型：底部盘整突破

**日期**：2026-03-30  
**功能规格**：`specs/017-底部盘整突破/spec.md`

## 概述

本策略**不新增数据库表**，复用现有数据结构：

- `stock_daily_bar`：日线行情数据（含 `cum_hist_high` 历史最高价）
- `stock_basic`：股票基础信息
- `backtest_task`：回测任务（010 智能回测已创建）
- `backtest_trade`：回测交易明细（010 智能回测已创建）

## 复用表结构

### stock_daily_bar（关键字段）

| 字段名 | 类型 | 说明 | 用途 |
|-------|------|------|------|
| `stock_code` | VARCHAR(16) | 股票代码 | 关联股票 |
| `trade_date` | DATE | 交易日期 | 时间轴 |
| `open` | DECIMAL(12,4) | 开盘价 | 买入执行价 |
| `high` | DECIMAL(12,4) | 最高价 | 止盈监控参考 |
| `low` | DECIMAL(12,4) | 最低价 | 条件单触碰判断 |
| `close` | DECIMAL(12,4) | 收盘价 | 信号判定、止盈监控基准 |
| `volume` | DECIMAL(20,4) | 成交量 | 可选过滤 |
| `cum_hist_high` | DECIMAL(12,4) | 历史最高价 | 低位约束判断 |

**索引**：
- 主键：`id`
- 唯一约束：`(stock_code, trade_date)`
- 查询索引：`trade_date`, `stock_code`

### backtest_trade（extra 字段扩展）

策略特有信息存储在 `extra` JSON 字段中：

```json
{
  "base_price": 10.50,           // 盘整基准价
  "consolidation_days": 18,      // 盘整天数
  "breakout_date": "2024-03-15", // 突破日期
  "stop_loss_price": 10.19,      // 止损价（base_price * 0.97）
  "highest_close": 12.80,        // 持仓期间最高收盘价
  "in_profit_monitor": true,     // 是否进入止盈监控
  "take_profit_trigger": 12.16,  // 止盈触发价（highest_close * 0.95）
  "exit_reason": "止盈（最高价回落5%）"  // 卖出原因
}
```

## 策略内部数据结构

### _ConsolidationState（盘整状态）

```python
@dataclass
class _ConsolidationState:
    """盘整形态状态（运行时数据，不持久化）"""
    base_price: Decimal           # 基准价（盘整首日收盘价）
    start_date: date              # 盘整起始日
    days: int                     # 已盘整天数
    status: Literal["active", "broken", "invalid"]  # 状态
```

### _PositionState（持仓状态）

```python
@dataclass
class _PositionState:
    """持仓监控状态（运行时数据，不持久化）"""
    stock_code: str
    buy_date: date
    buy_price: Decimal
    base_price: Decimal           # 盘整基准价
    stop_loss_price: Decimal      # 止损价
    highest_close: Decimal        # 持仓期间最高收盘价
    in_profit_monitor: bool       # 是否进入止盈监控
    take_profit_trigger: Decimal | None  # 止盈触发价
```

### _BreakoutSignal（突破信号）

```python
@dataclass
class _BreakoutSignal:
    """突破信号（策略内部产出）"""
    stock_code: str
    trigger_date: date            # 突破日（收盘价确认突破的那天）
    base_price: Decimal           # 盘整基准价
    breakout_price: Decimal       # 突破日收盘价
    consolidation_days: int       # 盘整天数
    buy_date: date                # 买入日（trigger_date + 1）
```

## 状态流转

### 盘整形态状态机

```
          ┌──────────────────────────────────────────┐
          │                                          │
          ▼                                          │
    ┌──────────┐  收盘偏离>3%且天数>=15  ┌──────────┐ │
    │  active  │ ─────────────────────▶ │  broken  │ │
    │ (盘整中) │                        │ (已突破) │ │
    └──────────┘                        └──────────┘ │
          │                                          │
          │ 收盘偏离<-3%                             │
          ▼                                          │
    ┌──────────┐                                     │
    │  invalid │ ────────────────────────────────────┘
    │ (已失效) │         从次日重新开始
    └──────────┘
```

### 持仓状态流转

```
买入（T+1开盘）
    │
    ▼
┌─────────────────────┐
│   持仓中（观察）      │
│   每日更新最高收盘价   │
└─────────────────────┘
    │
    ├─ 收益 >= 15% ─▶ 进入止盈监控状态
    │
    ├─ 最低价 <= 止损价 ─▶ 止损卖出
    │
    └─ 最低价 <= 止盈触发价（若在监控中）─▶ 止盈卖出
```

## 数据量估算

| 数据项 | 估算量 | 说明 |
|-------|-------|------|
| 股票数量 | ~5,000 | A 股全市场 |
| 日线记录 | ~350 万 | 5000 股 × 700 交易日 |
| 单次回测交易 | ~100-500 笔 | 取决于市场波动 |
| extra 字段大小 | ~500 字节/笔 | JSON 存储 |

## 无需变更说明

- **无需新增表**：完全复用现有结构
- **无需修改表结构**：`backtest_trade.extra` 字段已预留 JSON 存储
- **无需新增索引**：现有索引满足查询需求
