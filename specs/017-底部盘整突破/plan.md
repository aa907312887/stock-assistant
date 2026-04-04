# 实现计划：底部盘整突破

**分支**：`master` | **日期**：2026-03-30 | **规格**：`./spec.md`  
**输入**：功能规格来自 `specs/017-底部盘整突破/spec.md`

## 概要

本期交付一个新策略：**底部盘整突破**。该策略在A股中识别"处于相对低位（历史最高价二分之一以下）、经历至少15个交易日盘整后向上突破"的个股，在突破确认后买入，通过动态止盈止损规则控制风险收益比。

核心架构：**复用现有智能回测框架**（策略接口 + 回测引擎 + 资金仿真），仅新增：
- 一个新策略实现（`bottom_consolidation_breakout`）及其策略模块
- 策略在回测引擎中的注册与可选择
- 前端策略选股菜单新增"底部盘整突破"入口

## 技术背景

- **语言/版本**：Python 3.12（后端）、TypeScript 5.x（前端）
- **主要依赖**：FastAPI、SQLAlchemy 2.0、MySQL；Vue 3、Vite、Element Plus
- **存储**：MySQL（复用现有 stock_daily_bar、stock_basic、backtest_task、backtest_trade 表）
- **测试**：pytest
- **目标平台**：本地部署 + 现代浏览器
- **项目类型**：Web 应用（前后端分离）
- **性能目标**：
  - 全 A 股近三年回测：5 分钟内完成
  - 策略选股页面首屏加载 < 3 秒
- **约束**：
  - 仅日线数据，无分时数据
  - 止盈止损采用"条件单"模式模拟（用日线最低价判断触碰）
  - 资金仿真规则与现有框架一致
- **规模/范围**：A 股全市场约 5000+ 标的 × 近 3 年 ≈ 700+ 交易日

## 章程检查

`constitution.md` 当前为占位模板，未包含已核定的强制原则与门禁条款，因此本计划按项目既有规范执行（中文文档、Spec 驱动、避免超范围交付、复用现有框架）。

## 关键设计详述

### 数据流与接口职责

#### 整体数据流

```
用户操作                          前端                          后端
───────                          ────                          ────
进入策略选股页面    →  GET /api/strategies     →  返回策略列表（含底部盘整突破）
                     ← 200 [strategies...]
                     
点击"底部盘整突破"  →  GET /api/strategies/bottom_consolidation_breakout
                     ← 200 { 策略说明 }
                     
执行选股            →  POST /api/strategies/bottom_consolidation_breakout/execute
                     ← 200 { execution, items[], signals[] }
                     
发起回测            →  POST /api/backtest/run   →  创建 backtest_task (status=running)
                     ← 202 { task_id }              启动后台线程
                                                  strategy.backtest(start, end)
                                                       │
                                                  收集 trades → 资金仿真筛选
                                                       │
                                                  写入 backtest_trade
                                                  更新 backtest_task
                                                       │
轮询/刷新列表      →  GET /api/backtest/tasks   →  读取 backtest_task 列表
                     ← 200 [tasks...]
```

#### 后端分层

```
API 层 (app/api/strategy.py)
  ↓ 复用现有策略路由，新增策略执行入口
Strategy 层 (app/services/strategy/)
  ├── strategy_base.py           ← 复用，无需修改
  └── strategies/
      └── bottom_consolidation_breakout.py  ← [新增] 策略实现
Model 层 (app/models/)
  ├── backtest_task.py           ← 复用
  └── backtest_trade.py          ← 复用，extra 字段存储策略特有信息
```

### 策略核心算法

#### 1. 盘整形态识别

```python
def find_consolidation_breakout(bars: list[DailyBar], hist_highs: dict[date, Decimal]) -> list[Signal]:
    """
    盘整识别算法：
    1. 遍历日线，维护当前盘整状态（基准价、盘整天数、状态）
    2. 每日检查：
       - 若收盘价偏离基准价 > +3% 且 盘整天数 >= 15 → 触发突破信号
       - 若收盘价偏离基准价 < -3% → 盘整失效，从次日开始新盘整
       - 否则 → 继续盘整
    """
    signals = []
    consolidation_state = None  # { base_price, start_date, days, status }
    
    for i, bar in enumerate(bars):
        # 低位约束检查
        hist_high = hist_highs.get(bar.trade_date)
        if hist_high is None or bar.close > hist_high * 0.5:
            # 不满足低位约束，重置盘整状态
            consolidation_state = None
            continue
        
        if consolidation_state is None:
            # 开始新盘整
            consolidation_state = {
                "base_price": bar.close,
                "start_date": bar.trade_date,
                "days": 1,
                "status": "active"
            }
        else:
            # 检查盘整条件
            deviation = (bar.close - consolidation_state["base_price"]) / consolidation_state["base_price"]
            
            if deviation > 0.03:  # 突破
                if consolidation_state["days"] >= 15:
                    signals.append(BreakoutSignal(
                        stock_code=bar.stock_code,
                        trigger_date=bar.trade_date,
                        base_price=consolidation_state["base_price"],
                        days=consolidation_state["days"],
                    ))
                consolidation_state = None
            elif deviation < -0.03:  # 失效
                consolidation_state = None
            else:  # 继续盘整
                consolidation_state["days"] += 1
    
    return signals
```

#### 2. 持仓监控与卖出判定

```python
def check_exit_conditions(
    trade: BacktestTrade,
    bar: DailyBar,
    position_state: dict,
) -> tuple[bool, str, float]:
    """
    卖出条件检查：
    1. 止损：最低价 <= 止损价（基准价 * 0.97）→ 以止损价卖出
    2. 止盈：若已进入止盈监控（收益 >= 15%）且最低价 <= 止盈触发价 → 以止盈触发价卖出
    
    返回：(是否卖出, 卖出原因, 卖出价格)
    """
    stop_loss_price = position_state["base_price"] * 0.97
    
    # 止损检查
    if bar.low <= stop_loss_price:
        return (True, "止损（跌破支撑位）", stop_loss_price)
    
    # 止盈检查
    if position_state.get("in_profit_monitor"):
        take_profit_price = position_state["highest_close"] * 0.95
        if bar.low <= take_profit_price:
            return (True, "止盈（最高价回落5%）", take_profit_price)
    
    return (False, None, None)
```

#### 3. 回测主流程

```python
def backtest(self, *, start_date: date, end_date: date) -> BacktestResult:
    """
    回测流程：
    1. 批量查询时间范围内所有日线数据 + 历史最高价
    2. 按股票分组，逐股识别盘整突破信号
    3. 对每个信号：
       a. T+1 开盘价买入
       b. 逐日检查卖出条件（止损/止盈）
       c. 卖出后生成交野
    4. 返回所有交易记录
    """
    trades = []
    
    # 1. 批量查询数据
    bars = query_daily_bars(start_date, end_date)
    hist_highs = query_cumulative_hist_highs(end_date)
    
    # 2. 按股票分组
    bars_by_code = group_by_stock_code(bars)
    
    # 3. 逐股处理
    for stock_code, stock_bars in bars_by_code.items():
        signals = find_consolidation_breakout(stock_bars, hist_highs[stock_code])
        
        for signal in signals:
            trade = simulate_trade(signal, stock_bars)
            if trade:
                trades.append(trade)
    
    return BacktestResult(trades=trades)
```

### 定时任务与部署设计

- **使用的组件**：APScheduler（位于 `backend/app/core/scheduler.py`）
- **注册方式**：在 FastAPI lifespan 的 startup 中注册，复用现有 `_job_strategy_*` 模式
- **调度策略**：每日 17:00（与现有策略同步）
- **部署时是否执行一次**：否
- **手动触发方式**：
  - [x] HTTP 接口：`POST /api/strategies/bottom_consolidation_breakout/execute`，鉴权方式：JWT 登录
  - [x] 或 管理命令：`python -m app.scripts.run_strategy bottom_consolidation_breakout`
- **失败与重试**：失败不重试，记录日志；数据未就绪时返回 425 Too Early
- **日志与可观测**：
  - INFO：策略执行开始/结束、扫描股票数、候选数
  - WARNING：数据缺失、跳过股票

### 其他关键设计

#### 1. 历史最高价获取

使用 `stock_daily_bar.cum_hist_high` 字段（已在 013-历史高低价 中实现），该字段记录截至当日的历史最高价。策略在判断"低位约束"时，使用当日 K 线行的 `cum_hist_high` 值。

#### 2. 条件单模拟

回测中使用日线最低价（`low`）判断是否触碰触发价位：
- 若 `low <= trigger_price`，假设以 `trigger_price` 立即成交
- 这模拟了"条件单在价格触及时立即成交"的效果

#### 3. 资金仿真规则

与现有智能回测框架一致：
- 持仓金额/补仓池约束
- 同一买入日全市场至多成交1笔
- 卖出当日不得换股
- 盈利计入补仓池

#### 4. 策略参数

```python
@dataclass(frozen=True)
class _Params:
    consolidation_days: int = 15       # 最少盘整天数
    consolidation_range: float = 0.03  # 盘整幅度 ±3%
    low_position_ratio: float = 0.5    # 低位约束：历史最高价的 1/2
    profit_monitor_threshold: float = 0.15  # 止盈监控启动阈值 +15%
    profit_trailing_pct: float = 0.05  # 止盈回撤比例 5%
    stop_loss_pct: float = 0.03        # 止损比例 3%
    min_hist_days: int = 60            # 最少历史数据天数
```

## 项目结构

### 本功能文档

```text
specs/017-底部盘整突破/
├── plan.md              # 本文件
├── spec.md              # 功能规格
├── research.md          # Phase 0 调研结论
├── data-model.md        # Phase 1 数据模型
├── quickstart.md        # Phase 1 本地运行与验证
├── contracts/           # Phase 1 接口契约
│   └── strategy-api.md  # 策略 API 契约
├── checklists/
│   └── requirements.md  # 规格质量检查清单
└── tasks.md             # Phase 2 由 /speckit.tasks 生成
```

### 源码结构（本功能新增/修改）

```text
backend/
├── app/
│   ├── core/
│   │   └── scheduler.py                  # [修改] 新增策略定时任务注册
│   ├── services/
│   │   └── strategy/
│   │       ├── registry.py               # [修改] 注册新策略
│   │       └── strategies/
│   │           └── bottom_consolidation_breakout.py  # [新增] 策略实现
│   └── main.py                           # [无需修改] 复用现有策略路由
└── tests/
    └── test_bottom_consolidation_breakout.py  # [新增] 策略单元测试

frontend/
├── src/
│   ├── router/index.ts                   # [修改] 新增策略页面路由
│   ├── views/
│   │   └── Layout.vue                    # [修改] 侧边栏新增"底部盘整突破"菜单
│   └── views/strategy/
│       └── BottomConsolidationBreakoutView.vue  # [新增] 策略页面
└── ...
```

**结构说明**：
- 后端完全复用现有策略框架，仅新增策略实现文件
- 前端新增一个策略展示页面，复用现有策略选股布局
- 回测能力复用智能回测模块，无需新增代码

## 阶段划分

### Phase 1：后端策略实现（核心）

- 新增策略模块 `bottom_consolidation_breakout.py`
- 实现盘整识别算法、信号触发逻辑、回测交易生成
- 实现止盈止损的条件单模拟
- 在策略注册表中注册 `bottom_consolidation_breakout`
- 添加定时任务（每日 17:00 自动执行选股）

### Phase 2：前端页面与集成

- 新增"策略选股 → 底部盘整突破"菜单入口
- 新增策略展示页面（策略说明 + 执行按钮 + 结果列表）
- 集成智能回测（策略出现在回测策略下拉框中）

### Phase 3：测试与验证

- 单元测试：盘整识别、止损止盈计算
- 集成测试：完整回测流程
- 手动验证：用实际股票数据验证信号正确性

## 风险与回退

- **风险**：历史最高价字段 `cum_hist_high` 可能在部分股票上为空
  - **回退**：跳过该股票，在日志中记录原因
- **风险**：盘整期间股票停牌导致数据缺失
  - **回退**：停牌期间不计入盘整天数，复牌后继续计算
- **风险**：极端行情下止盈止损可能同时触发
  - **回退**：按规格优先执行止损（保护本金）
