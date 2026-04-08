# 接口契约：市盈率早晨十字星策略

**创建日期**: 2026-04-07  
**关联规格**: [../spec.md](../spec.md)

## 概述

本策略通过 `StockStrategy` 基类暴露两个核心接口：
1. **回测接口** (`backtest()`)：历史数据回测
2. **选股接口** (`execute()`)：实时/指定日期选股

## 1. 回测接口

### 方法签名

```python
def backtest(
    self,
    stock_codes: list[str],
    start_date: date,
    end_date: date,
) -> BacktestResult
```

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `stock_codes` | `list[str]` | 是 | 股票代码列表，如 `["000001.SZ", "600000.SH"]` |
| `start_date` | `date` | 是 | 回测起始日期（含） |
| `end_date` | `date` | 是 | 回测结束日期（含） |

### 响应结构

```python
@dataclass
class BacktestResult:
    trades: list[BacktestTrade]
    skipped_count: int
    skip_reasons: list[str]
```

#### BacktestTrade 结构

```python
@dataclass
class BacktestTrade:
    stock_code: str              # 股票代码
    stock_name: str              # 股票名称
    buy_date: date               # 买入日期
    buy_price: float             # 买入价格
    sell_date: date | None       # 卖出日期（None=未平仓）
    sell_price: float | None     # 卖出价格
    return_rate: float | None    # 收益率（小数，如 0.08 表示 8%）
    trade_type: str              # "closed" | "unclosed"
    trigger_date: date           # 信号触发日（第三根阳线日 T）
    extra: dict[str, Any]        # 附加信息（见下方）
```

#### extra 字段（本策略特有）

| 字段 | 类型 | 说明 |
|------|------|------|
| `trigger_pe_percentile` | float | 触发日 T 的 PE 百分位（< 10） |
| `trigger_roe` | float | 触发日最近一期 ROE（> 15） |
| `trigger_roe_report_date` | str | ROE 对应的财报日期（ISO 格式） |
| `exit_reason` | str | 离场原因："stop_loss_8pct" / "trailing_stop_5pct" / "unclosed" |
| `day_minus_2_date` | str | T-2 日期（大阴线日） |
| `day_minus_1_date` | str | T-1 日期（锤头线日） |
| `day_0_date` | str | T 日期（阳线日，即 trigger_date） |

### 示例

**请求**：
```python
strategy = PeZaoChenShiZiXingStrategy()
result = strategy.backtest(
    stock_codes=["000001.SZ", "600000.SH"],
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31),
)
```

**响应**：
```python
BacktestResult(
    trades=[
        BacktestTrade(
            stock_code="000001.SZ",
            stock_name="平安银行",
            buy_date=date(2024, 3, 15),
            buy_price=12.50,
            sell_date=date(2024, 4, 10),
            sell_price=13.75,
            return_rate=0.10,
            trade_type="closed",
            trigger_date=date(2024, 3, 12),
            extra={
                "trigger_pe_percentile": 8.5,
                "trigger_roe": 18.2,
                "trigger_roe_report_date": "2023-12-31",
                "exit_reason": "trailing_stop_5pct",
                "day_minus_2_date": "2024-03-10",
                "day_minus_1_date": "2024-03-11",
                "day_0_date": "2024-03-12",
            }
        ),
    ],
    skipped_count=0,
    skip_reasons=[],
)
```

## 2. 选股接口

### 方法签名

```python
def execute(
    self,
    target_date: date | None = None,
) -> StrategyExecutionResult
```

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `target_date` | `date \| None` | 否 | 目标日期，默认 None（使用最新交易日） |

### 响应结构

```python
@dataclass
class StrategyExecutionResult:
    candidates: list[StrategyCandidate]
    execution_date: date
    total_scanned: int
```

#### StrategyCandidate 结构

```python
@dataclass
class StrategyCandidate:
    stock_code: str
    stock_name: str
    signal_date: date
    signal_price: float
    summary: str              # 人类可读的信号摘要
    extra: dict[str, Any]     # 附加信息（见下方）
```

#### extra 字段（本策略特有）

| 字段 | 类型 | 说明 |
|------|------|------|
| `pe_percentile` | float | 当日 PE 百分位 |
| `roe` | float | 最近一期 ROE |
| `roe_report_date` | str | ROE 对应的财报日期（ISO 格式） |
| `day_minus_2_date` | str | T-2 日期 |
| `day_minus_1_date` | str | T-1 日期 |
| `day_0_date` | str | T 日期（即 signal_date） |

### 示例

**请求**：
```python
strategy = PeZaoChenShiZiXingStrategy()
result = strategy.execute(target_date=date(2024, 12, 31))
```

**响应**：
```python
StrategyExecutionResult(
    candidates=[
        StrategyCandidate(
            stock_code="000001.SZ",
            stock_name="平安银行",
            signal_date=date(2024, 12, 31),
            signal_price=12.50,
            summary="PE百分位: 8.5%, ROE: 18.2%, 早晨十字星形态",
            extra={
                "pe_percentile": 8.5,
                "roe": 18.2,
                "roe_report_date": "2024-09-30",
                "day_minus_2_date": "2024-12-27",
                "day_minus_1_date": "2024-12-30",
                "day_0_date": "2024-12-31",
            }
        ),
    ],
    execution_date=date(2024, 12, 31),
    total_scanned=5000,
)
```

## 3. 策略描述接口

### 方法签名

```python
def describe(self) -> StrategyDescriptor
```

### 响应结构

```python
@dataclass
class StrategyDescriptor:
    strategy_id: str
    name: str
    description: str
    version: str
```

### 示例

```python
StrategyDescriptor(
    strategy_id="pe_zao_chen_shi_zi_xing",
    name="市盈率早晨十字星",
    description="在早晨十字星形态基础上，叠加PE百分位<10%与ROE>15%过滤",
    version="v1.0.0",
)
```

## 错误处理

### 常见错误场景

1. **数据缺失**：
   - PE 百分位字段为空 → 跳过该标的，不产生信号
   - ROE 数据不可用 → 跳过该标的，不产生信号
   - K 线数据不足 → 跳过该标的，不产生信号

2. **参数错误**：
   - `start_date > end_date` → 抛出 `ValueError`
   - `stock_codes` 为空 → 返回空结果（不报错）

3. **数据库错误**：
   - 连接失败 → 抛出 `OperationalError`
   - 查询超时 → 抛出 `TimeoutError`

## 性能约定

- **回测**：单标的单年数据处理时间 < 100ms（与「早晨十字星」对齐）
- **选股**：全市场扫描（约 5000 只股票）< 30s（取决于 ROE 查询优化）

## 版本兼容性

- 策略版本：`v1.0.0`
- 基类版本：继承自 `StockStrategy`（项目统一基类）
- 数据模型版本：依赖现有表结构，无版本依赖
