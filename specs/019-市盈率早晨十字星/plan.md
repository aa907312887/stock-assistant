# 实现计划：市盈率早晨十字星

**功能分支**: `main`  
**创建日期**: 2026-04-07  
**规格文件**: [spec.md](spec.md)

## 技术上下文

### 现有技术栈

- **后端**: Python 3.12 + FastAPI + SQLAlchemy + MySQL
- **策略框架**: 基于 `StockStrategy` 抽象基类，策略注册在 `registry.py`
- **数据模型**: 
  - `StockDailyBar`: 日线数据（含 pe_percentile 预计算字段）
  - `StockFinancialReport`: 财报数据（含 roe 字段）
- **已有策略**: 
  - `ZaoChenShiZiXingStrategy`: 早晨十字星（形态判断逻辑可复用）
  - `PeValueInvestmentStrategy`: 市盈率价值投资（PE 百分位读取逻辑可参考）

### 依赖服务与数据

- **PE 百分位**: 已预计算存储在 `stock_daily_bar.pe_percentile` 字段
- **ROE 数据**: 存储在 `stock_financial_report.roe` 字段，需按 `report_date` 降序取最近一期
- **K 线与技术指标**: `stock_daily_bar` 表（open/high/low/close/ma5/ma10/ma20/cum_hist_high）

### 集成点

- **策略注册**: 在 `registry.py` 的 `list_strategies()` 中添加新策略实例
- **策略描述**: 在 `strategy_descriptions.py` 的 `STRATEGY_DESCRIPTIONS` 字典中添加策略说明
- **回测接口**: 通过 `backtest()` 方法集成到现有回测框架
- **选股接口**: 通过 `execute()` 方法集成到策略选股功能

## 关键设计详述

### 策略实现架构

本策略采用**组合模式**：复用「早晨十字星」的形态判断逻辑，叠加 PE 百分位与 ROE 过滤。

**核心流程**：
1. 调用 `ZaoChenShiZiXingStrategy` 的形态判断逻辑（或直接复用其私有方法）
2. 对满足形态的候选标的，额外检查：
   - 信号日 T 的 `pe_percentile < 10%`
   - 最近一期财报的 `roe > 15%`
3. 仅当三个条件同时满足时产生信号

**数据查询策略**：
- PE 百分位：直接从 `stock_daily_bar` 读取，无需额外计算
- ROE：对每个候选标的，查询 `stock_financial_report` 表，按 `stock_code` 过滤并按 `report_date DESC` 排序取第一条

**买卖规则**：完全继承「早晨十字星」策略（止损 8%、移动止盈 15%+5%）

### 数据模型

**无需新增表或字段**，使用现有表：

- `stock_daily_bar.pe_percentile`: PE 百分位（已预计算）
- `stock_financial_report.roe`: 净资产收益率
- `stock_financial_report.report_date`: 财报日期（用于排序取最近一期）

### 接口契约

**回测接口**（继承自 `StockStrategy.backtest()`）：
- 输入：`stock_codes: list[str]`, `start_date: date`, `end_date: date`
- 输出：`BacktestResult`（含 `trades: list[BacktestTrade]`）
- `BacktestTrade.extra` 字段新增：
  - `trigger_pe_percentile`: 触发日 PE 百分位
  - `trigger_roe`: 触发日最近一期 ROE

**选股接口**（继承自 `StockStrategy.execute()`）：
- 输入：`target_date: date | None`（默认最新交易日）
- 输出：`StrategyExecutionResult`（含 `candidates: list[StrategyCandidate]`）
- `StrategyCandidate.extra` 字段新增：
  - `pe_percentile`: 当日 PE 百分位
  - `roe`: 最近一期 ROE
  - `roe_report_date`: ROE 对应的财报日期

### 实现细节

#### 1. 策略类定义

```python
# backend/app/services/strategy/strategies/pe_zao_chen_shi_zi_xing.py

class PeZaoChenShiZiXingStrategy(StockStrategy):
    """市盈率早晨十字星策略：早晨十字星形态 + PE百分位<10% + ROE>15%"""
    
    strategy_id = "pe_zao_chen_shi_zi_xing"
    version = "v1.0.0"
    
    def describe(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            name="市盈率早晨十字星",
            description="在早晨十字星形态基础上，叠加PE百分位<10%与ROE>15%过滤",
            version=self.version,
        )
```

#### 2. 形态判断复用

**方案 A（推荐）**：将 `ZaoChenShiZiXingStrategy` 的形态判断逻辑提取为独立函数，两个策略共享。

**方案 B**：在新策略中直接调用 `ZaoChenShiZiXingStrategy` 实例的私有方法（需确保方法可访问）。

**方案 C**：复制粘贴形态判断代码（不推荐，违反 DRY 原则）。

本计划采用**方案 A**：在 `zao_chen_shi_zi_xing.py` 中将形态判断逻辑提取为模块级函数 `_check_morning_star_pattern()`，供两个策略调用。

#### 3. ROE 查询逻辑

```python
def _get_latest_roe(session, stock_code: str, as_of_date: date) -> float | None:
    """查询指定日期前最近一期已披露的ROE"""
    stmt = (
        select(StockFinancialReport.roe)
        .where(
            StockFinancialReport.stock_code == stock_code,
            StockFinancialReport.report_date <= as_of_date,
            StockFinancialReport.roe.isnot(None),
        )
        .order_by(StockFinancialReport.report_date.desc())
        .limit(1)
    )
    result = session.execute(stmt).scalar_one_or_none()
    return float(result) if result else None
```

#### 4. 回测实现

```python
def backtest(
    self,
    stock_codes: list[str],
    start_date: date,
    end_date: date,
) -> BacktestResult:
    """回测逻辑：
    1. 调用形态判断函数找出满足早晨十字星的候选
    2. 对每个候选，检查触发日T的pe_percentile < 10%
    3. 查询最近一期ROE > 15%
    4. 三者同时满足才记录信号
    5. 买卖规则与早晨十字星一致
    """
    trades = []
    
    with SessionLocal() as session:
        for code in stock_codes:
            # 1. 获取K线数据
            bars = _load_bars(session, code, start_date, end_date)
            
            # 2. 形态扫描（复用早晨十字星逻辑）
            pattern_signals = _check_morning_star_pattern(bars)
            
            # 3. 对每个形态信号，叠加PE与ROE过滤
            for signal in pattern_signals:
                trigger_bar = signal.trigger_bar
                
                # PE百分位过滤
                pe_pct = trigger_bar.pe_percentile
                if pe_pct is None or pe_pct >= 10.0:
                    continue
                
                # ROE过滤
                roe = _get_latest_roe(session, code, trigger_bar.trade_date)
                if roe is None or roe <= 15.0:
                    continue
                
                # 通过过滤，生成交易记录
                trade = _execute_trade_logic(signal, pe_pct, roe)
                trades.append(trade)
    
    return BacktestResult(trades=trades, skipped_count=0, skip_reasons=[])
```

#### 5. 选股实现

```python
def execute(
    self,
    target_date: date | None = None,
) -> StrategyExecutionResult:
    """选股逻辑：
    1. 确定目标日期（默认最新交易日）
    2. 扫描全市场，找出当日满足早晨十字星形态的标的
    3. 对每个候选，检查pe_percentile < 10% 且 roe > 15%
    4. 返回满足条件的标的列表
    """
    candidates = []
    
    with SessionLocal() as session:
        if target_date is None:
            target_date = get_latest_bar_date(session)
        
        # 获取全市场股票列表
        all_stocks = _get_all_stocks(session)
        
        for stock in all_stocks:
            # 形态判断
            if not _check_pattern_on_date(session, stock.stock_code, target_date):
                continue
            
            # PE百分位过滤
            bar = _get_bar_on_date(session, stock.stock_code, target_date)
            if bar.pe_percentile is None or bar.pe_percentile >= 10.0:
                continue
            
            # ROE过滤
            roe = _get_latest_roe(session, stock.stock_code, target_date)
            if roe is None or roe <= 15.0:
                continue
            
            # 通过过滤，加入候选列表
            candidates.append(StrategyCandidate(
                stock_code=stock.stock_code,
                stock_name=stock.stock_name,
                signal_date=target_date,
                extra={
                    "pe_percentile": float(bar.pe_percentile),
                    "roe": roe,
                    "roe_report_date": _get_latest_report_date(session, stock.stock_code, target_date),
                },
            ))
    
    return StrategyExecutionResult(
        candidates=candidates,
        total_scanned=len(all_stocks),
        execution_date=target_date,
    )
```

### 注册与描述

#### 1. 注册策略

在 `backend/app/services/strategy/registry.py` 中：

```python
from app.services.strategy.strategies.pe_zao_chen_shi_zi_xing import PeZaoChenShiZiXingStrategy

def list_strategies() -> list[StockStrategy]:
    return [
        ChongGaoHuiLuoStrategy(),
        PanicPullbackStrategy(),
        ShuGuangChuXianStrategy(),
        ZaoChenShiZiXingStrategy(),
        PeZaoChenShiZiXingStrategy(),  # 新增
        BottomConsolidationBreakoutStrategy(),
        MAGoldenCrossStrategy(),
        DaYangHuiLuoStrategy(),
        PeValueInvestmentStrategy(),
        DuoTouPaiLieStrategy(),
    ]
```

#### 2. 添加策略描述

在 `backend/app/services/strategy/strategy_descriptions.py` 中：

```python
STRATEGY_DESCRIPTIONS: dict[str, str] = {
    # ... 现有策略 ...
    "pe_zao_chen_shi_zi_xing": """【买入条件】
- 早晨十字星形态：T-2大阴(跌≥2%) + T-1锤头线 + T阳线(实体≥3%)
- 跌势结构：MA5<MA10<MA20，收盘<MA20
- 前7天(T-9至T-3)≥5根阴线，累计跌幅≥10%
- 收盘≤历史最高价的50%
- PE百分位<10%（严格小于）
- 最近一期ROE>15%（严格大于）
- 入场：首次收盘站上MA5时以收盘价买入

【卖出条件】
- 止损：收盘≤买入价×0.92 → 固定按买入价×0.92卖出（亏损8%）
- 移动止盈：涨幅≥15%后启动追踪，从最高价回落≥5% → 当日收盘价卖出

【关键参数】
pe_threshold=10.0, roe_threshold=15.0, stop_loss_pct=0.08, arm_profit_trigger_pct=0.15, trailing_stop_pct=0.05""",
}
```

## 实现步骤

### Phase 1: 代码重构与准备

1. **提取形态判断逻辑**
   - 在 `zao_chen_shi_zi_xing.py` 中将形态判断提取为独立函数
   - 确保函数签名清晰，可被外部调用
   - 运行现有测试确保重构未破坏原策略

2. **创建 ROE 查询工具函数**
   - 在新策略文件中实现 `_get_latest_roe()`
   - 编写单元测试验证查询逻辑

### Phase 2: 策略实现

1. **创建策略文件**
   - 文件路径：`backend/app/services/strategy/strategies/pe_zao_chen_shi_zi_xing.py`
   - 实现 `PeZaoChenShiZiXingStrategy` 类
   - 实现 `describe()` 方法

2. **实现回测逻辑**
   - 实现 `backtest()` 方法
   - 复用形态判断 + 叠加 PE/ROE 过滤
   - 确保 `BacktestTrade.extra` 包含 PE 百分位与 ROE 信息

3. **实现选股逻辑**
   - 实现 `execute()` 方法
   - 扫描全市场 + 三重过滤
   - 确保 `StrategyCandidate.extra` 包含完整信息

### Phase 3: 集成与注册

1. **注册策略**
   - 在 `registry.py` 中添加策略实例
   - 在 `strategy_descriptions.py` 中添加策略描述

2. **验证集成**
   - 通过 API 调用回测接口，验证策略可选择
   - 通过选股接口验证策略可执行

### Phase 4: 测试与验证

1. **单元测试**
   - 测试 ROE 查询逻辑（边界情况：无数据、多条记录）
   - 测试 PE 百分位过滤（边界值 10%）
   - 测试 ROE 过滤（边界值 15%）

2. **集成测试**
   - 准备测试数据：已知满足/不满足条件的标的
   - 运行回测，验证信号数量与预期一致
   - 运行选股，验证结果列表正确

3. **人工验收**
   - 按 spec.md 中的验收场景逐一验证
   - 对比「早晨十字星」策略，确认信号数量减少（验证过滤生效）

## 风险与依赖

### 技术风险

1. **ROE 数据缺失**
   - 风险：新上市或未披露财报的标的无 ROE 数据
   - 缓解：在查询逻辑中明确处理 `None` 情况，跳过该标的

2. **PE 百分位字段为空**
   - 风险：亏损企业或数据未同步时 `pe_percentile` 为 `None`
   - 缓解：在过滤逻辑中检查 `None`，跳过该标的

3. **形态判断逻辑变更**
   - 风险：若「早晨十字星」策略逻辑调整，本策略需同步
   - 缓解：通过共享函数确保逻辑一致；在文档中注明依赖关系

### 数据依赖

1. **PE 百分位预计算**
   - 依赖：`stock_daily_bar.pe_percentile` 字段已填充
   - 验证：在实现前检查生产环境数据完整性

2. **财报数据同步**
   - 依赖：`stock_financial_report` 表数据及时更新
   - 验证：确认财报同步任务正常运行

### 性能考虑

1. **选股性能**
   - 风险：全市场扫描 + 逐标的查询 ROE 可能较慢
   - 优化：考虑批量查询 ROE（一次查询所有候选标的的最近一期 ROE）

2. **回测性能**
   - 风险：大量标的 + 长时间区间可能耗时
   - 优化：与现有策略性能对齐，无需额外优化

## 验收标准

按 [spec.md](spec.md) 中的成功标准验收：

- **SC-001**: 可复现性 - 同一数据集重复运行，结果一致
- **SC-002**: 过滤生效 - 相比「早晨十字星」，信号数量减少
- **SC-003**: 准确率 - 人工标注样本一致率 100%
- **SC-004**: 可追溯性 - 回测报告中 `trigger_date` 正确
- **SC-005**: 选股正确性 - 选股结果可人工核验三个条件

## 后续优化

1. **参数可配置化**
   - 当前 PE 阈值 10% 与 ROE 阈值 15% 硬编码
   - 未来可考虑支持用户自定义阈值

2. **性能优化**
   - 批量查询 ROE 减少数据库往返
   - 缓存最近一期 ROE 数据

3. **监控与告警**
   - 记录 ROE 数据缺失率
   - 记录 PE 百分位字段为空的比例
