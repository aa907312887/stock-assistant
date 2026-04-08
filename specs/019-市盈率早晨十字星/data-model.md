# 数据模型：市盈率早晨十字星

**创建日期**: 2026-04-07  
**关联规格**: [spec.md](spec.md)

## 概述

本策略**无需新增数据库表或字段**，完全复用现有数据模型。

## 依赖的现有表

### stock_daily_bar（股票日线数据）

| 字段 | 类型 | 说明 | 本策略用途 |
|------|------|------|-----------|
| `stock_code` | VARCHAR(20) | 股票代码 | 标的标识 |
| `trade_date` | DATE | 交易日期 | 信号日 T 及前序日 |
| `open` | DECIMAL | 开盘价（前复权） | 形态判断 |
| `high` | DECIMAL | 最高价（前复权） | 形态判断 |
| `low` | DECIMAL | 最低价（前复权） | 形态判断 |
| `close` | DECIMAL | 收盘价（前复权） | 形态判断、买卖判定 |
| `ma5` | DECIMAL | 5日均线 | 跌势结构判断、买入触发 |
| `ma10` | DECIMAL | 10日均线 | 跌势结构判断 |
| `ma20` | DECIMAL | 20日均线 | 跌势结构判断 |
| `cum_hist_high` | DECIMAL | 累计历史最高价 | 历史高位过滤 |
| `pe_percentile` | DECIMAL | PE历史百分位（预计算） | **PE过滤核心字段**，须 < 10% |
| `pe` | DECIMAL | 市盈率 | 辅助判断（PE为负时跳过） |
| `volume` | DECIMAL | 成交量 | 仅用于 extra 参考字段，不作过滤 |

**关键约束**：
- `pe_percentile` 为 NULL 时，该标的不产生信号
- `pe_percentile` 须严格 < 10.0（不含等号）
- `pe` 为负时，`pe_percentile` 通常为 NULL，直接跳过

### stock_financial_report（股票财报数据）

| 字段 | 类型 | 说明 | 本策略用途 |
|------|------|------|-----------|
| `stock_code` | VARCHAR(20) | 股票代码 | 关联标的 |
| `report_date` | DATE | 财报日期（报告期） | 排序取最近一期 |
| `ann_date` | DATE | 披露日期 | 可选：用于判断是否已披露 |
| `roe` | DECIMAL(20,4) | 净资产收益率（%） | **ROE过滤核心字段**，须 > 15% |
| `report_type` | VARCHAR(16) | 报告类型（年报/中报等） | 不限制类型，取最近一期 |

**关键约束**：
- 查询条件：`stock_code = ?` AND `report_date <= 信号日T` AND `roe IS NOT NULL`
- 排序：`report_date DESC LIMIT 1`（取最近一期已有 ROE 数据的财报）
- `roe` 须严格 > 15.0（不含等号）
- `roe` 为 NULL 或无记录时，该标的不产生信号

**唯一约束**：`uk_stock_report (stock_code, report_date)`

### stock_basic（股票基础信息）

| 字段 | 类型 | 说明 | 本策略用途 |
|------|------|------|-----------|
| `code` | VARCHAR(20) | 股票代码 | 剔除 ST 与北交所 |
| `name` | VARCHAR(64) | 股票名称 | 剔除含 ST/*ST 的标的 |
| `exchange` | VARCHAR(16) | 交易所 | 剔除 BSE（北交所） |

## 策略输出数据结构

### BacktestTrade.extra（回测交易明细附加字段）

在「早晨十字星」策略现有 extra 字段基础上，新增：

| 字段 | 类型 | 说明 |
|------|------|------|
| `trigger_pe_percentile` | float | 触发日 T 的 PE 百分位值 |
| `trigger_roe` | float | 触发日最近一期 ROE 值（%） |
| `trigger_roe_report_date` | str (ISO) | ROE 对应的财报日期 |

### StrategyCandidate.summary（选股候选附加字段）

| 字段 | 类型 | 说明 |
|------|------|------|
| `pe_percentile` | float | 当日 PE 百分位值 |
| `roe` | float | 最近一期 ROE 值（%） |
| `roe_report_date` | str (ISO) | ROE 对应的财报日期 |

## 数据查询示意

### ROE 查询（伪 SQL）

```sql
SELECT roe, report_date
FROM stock_financial_report
WHERE stock_code = :code
  AND report_date <= :signal_date
  AND roe IS NOT NULL
ORDER BY report_date DESC
LIMIT 1;
```

### PE 百分位查询

直接从 `stock_daily_bar` 的 `pe_percentile` 字段读取，无需额外查询。

### 批量 ROE 预加载（回测性能优化）

回测时，可对所有候选标的批量预加载最近一期 ROE，避免逐标的查询：

```sql
SELECT stock_code, roe, report_date
FROM stock_financial_report sfr
WHERE (stock_code, report_date) IN (
    SELECT stock_code, MAX(report_date)
    FROM stock_financial_report
    WHERE report_date <= :end_date
      AND roe IS NOT NULL
    GROUP BY stock_code
);
```
