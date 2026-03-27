# 实现计划：智能回测

**分支**: `main` | **日期**: 2026-03-26 | **规格**: `./spec.md`  
**输入**: 功能规格来自 `specs/010-智能回测/spec.md`

**说明**: 本模板由 `/speckit.plan` 命令填写。全文须使用**中文**，且达到**可直接按方案实现**的粒度。

## 概要

本期交付"历史回测"功能：用户选择任意内置策略与时间范围，系统在后台异步执行回测（遍历历史数据、模拟交易），完成后展示绩效报告（胜率/总收益率/平均收益等）与逐笔交易明细，帮助用户判断策略在历史上是赚钱还是亏钱。

核心架构：**回测引擎（通用框架）+ 策略回测接口（各策略自行实现）**。引擎负责任务管理、结果收集、指标计算与持久化；每个策略实现自己的 `backtest()` 方法定义具体交易逻辑。

## 技术背景

- **语言/版本**: Python（项目现有版本），TypeScript 5.x
- **主要依赖**: FastAPI、SQLAlchemy 2.0、MySQL；Vue 3、Vite、Element Plus、Pinia、Axios
- **存储**: MySQL
- **测试**: pytest
- **目标平台**: 本地部署（开发机）+ 现代浏览器
- **项目类型**: Web 应用（前后端分离）
- **性能目标**:
  - 全 A 股近三年回测（冲高回落战法）：5 分钟内完成（SC-005）
  - 回测列表页、详情页首屏加载 < 2 秒
- **约束**:
  - 仅日线数据，无分时数据
  - 策略由代码实现，不同策略交易模式不同（引擎不假设固定模式）
  - 单用户/少量用户并发
- **规模/范围**: A 股全市场约 5000+ 标的 × 近 3 年 ≈ 700+ 交易日

## 章程检查

`constitution.md` 当前为占位模板，未包含已核定的强制原则与门禁条款，因此本计划按项目既有规范执行（中文文档、Spec 驱动、避免超范围交付）。

## 关键设计详述

### 数据流与接口职责

#### 整体数据流

```
用户操作                     前端                          后端
───────                     ────                          ────
选择策略+时间范围  →  POST /api/backtest/run   →  创建 backtest_task (status=running)
                        ← 202 { task_id }              启动后台线程
                                                         │
                                                    strategy.backtest(start, end)
                                                         │
                                                    收集 trades → 计算指标
                                                    写入 backtest_trade
                                                    更新 backtest_task (status/metrics)
                                                         │
轮询/刷新列表      →  GET /api/backtest/tasks   →  读取 backtest_task 列表
                        ← 200 [tasks...]
                                                         
查看详情           →  GET /api/backtest/tasks/{id} →  读取 task + 报告指标
                        ← 200 { report }
                        
查看明细           →  GET /api/backtest/tasks/{id}/trades → 分页读取 backtest_trade
                        ← 200 { items[] }
```

#### 后端接口（5 个端点）

详见 `contracts/backtest-api.md`，此处列出职责对照：

| 端点 | 方法 | 职责 | 对应 FR |
|------|------|------|---------|
| `/api/backtest/run` | POST | 创建回测任务、启动后台线程 | FR-001, FR-014 |
| `/api/backtest/tasks` | GET | 分页查询回测任务列表 | FR-015 |
| `/api/backtest/tasks/{task_id}` | GET | 查询单个任务详情与绩效报告 | FR-011~013 |
| `/api/backtest/tasks/{task_id}/trades` | GET | 分页查询交易明细 | FR-003 |
| `/api/backtest/data-range` | GET | 返回数据库日线数据的最早/最晚日期 | FR-009 |

#### 后端分层

```
API 层 (app/api/backtest.py)
  ↓ 参数校验、任务创建、线程启动、响应组装
Service 层 (app/services/backtest/)
  ├── backtest_engine.py    ← 回测引擎：调用策略、收集结果、计算指标、持久化
  └── backtest_report.py    ← 报告计算：从 trades 列表计算绩效指标
Strategy 层 (app/services/strategy/)
  ├── strategy_base.py      ← 新增 BacktestTrade/BacktestResult 数据类、策略 Protocol 新增 backtest()
  └── strategies/chong_gao_hui_luo.py  ← 实现 backtest() 方法
Model 层 (app/models/)
  ├── backtest_task.py      ← SQLAlchemy 模型
  └── backtest_trade.py     ← SQLAlchemy 模型
```

#### 前端页面与路由

- **侧边栏菜单**：在 `Layout.vue` 新增一级菜单"智能回测"，二级菜单"历史回测"
- **路由**：`/backtest/history` → `HistoryBacktestView.vue`
- **API 模块**：`src/api/backtest.ts`（复用现有 Axios 实例）

**页面布局**（单页面内分区域）：

```
┌─────────────────────────────────────────────┐
│  配置区                                       │
│  [策略选择下拉] [开始日期] [结束日期] [开始回测] │
│  可用数据范围提示：2023-01-03 ~ 2026-03-25     │
├─────────────────────────────────────────────┤
│  回测记录列表                                  │
│  策略名称 | 时间范围 | 状态 | 胜率 | 总收益 | 操作 │
│  冲高回落 | 2024-... | 已完成| 42% | +15%  | 查看 │
│  冲高回落 | 2023-... | 运行中| -   | -     | -   │
├─────────────────────────────────────────────┤
│  结果详情（点击"查看"后展开/弹窗）              │
│  ┌─ 绩效概览卡片 ────────────────┐            │
│  │ 总体结论: 盈利 +15.23%        │            │
│  │ 总交易 87 | 胜率 42.5% | ...  │            │
│  └────────────────────────────┘            │
│  ┌─ 大盘温度分组统计 ───────────┐            │
│  │ 温度级别 | 交易数 | 胜率 | 平均收益 │            │
│  │ 冰点     |  12   | 66.7%| +2.34%  │            │
│  │ 低温     |  25   | 40.0%| +0.12%  │            │
│  │ ...                                │            │
│  └────────────────────────────┘            │
│  ┌─ 交易明细表格 ────────────────┐            │
│  │ 股票 | 买入日 | 买入价 | 温度 | ... | 收益率 │       │
│  │ 分页控制                       │            │
│  └────────────────────────────┘            │
└─────────────────────────────────────────────┘
```

### 定时任务与部署设计

本功能不涉及定时任务。回测任务由用户通过 HTTP 接口按需发起，后台线程异步执行。

### 其他关键设计

#### 1）异步回测执行模式

沿用项目已有模式（`admin.py`、`market_temperature.py`）：

```python
def _runner() -> None:
    db = SessionLocal()
    try:
        run_backtest(db, task_id=task_id, strategy_id=..., start_date=..., end_date=...)
    except Exception as e:
        # 更新 task status=failed, error_message=str(e)
    finally:
        db.close()

threading.Thread(target=_runner, daemon=True).start()
return JSONResponse(status_code=202, content={...})
```

**task_id 生成规则**：`bt-{strategy_id}-{start_date_compact}-{end_date_compact}-{uuid4_short}`，例如 `bt-chong_gao_hui_luo-20240101-20241231-a1b2c3d4`。

#### 2）回测引擎（`backtest_engine.py`）核心流程

```python
def run_backtest(db: Session, *, task_id: str, strategy_id: str, start_date: date, end_date: date) -> None:
    """后台线程中执行的回测主流程。"""
    strategy = get_strategy(strategy_id)

    # 1. 调用策略的 backtest 方法（策略自行查询数据、产出交易列表）
    result: BacktestResult = strategy.backtest(start_date=start_date, end_date=end_date)

    # 2. 为每笔交易补充买入日大盘温度（引擎职责，非策略职责）
    enrich_trades_with_temperature(db, result.trades)

    # 3. 持久化交易明细
    for trade in result.trades:
        db.add(BacktestTradeModel(...))

    # 4. 计算绩效指标（含按温度级别分组统计）
    report = calculate_report(result.trades)

    # 5. 更新任务状态与指标
    task.status = "completed" if report.unclosed_count == 0 else "incomplete"
    task.total_trades = report.total_trades
    task.win_rate = report.win_rate
    # ... 其余指标 ...
    task.finished_at = datetime.now()

    db.commit()
```

#### 3）策略回测接口扩展

在 `StockStrategy` Protocol 中新增 `backtest` 方法：

```python
class StockStrategy(Protocol):
    strategy_id: str
    version: str

    def describe(self) -> StrategyDescriptor: ...
    def execute(self, *, as_of_date: date | None = None) -> StrategyExecutionResult: ...
    def backtest(self, *, start_date: date, end_date: date) -> BacktestResult: ...
```

#### 4）冲高回落战法的 `backtest()` 实现要点

冲高回落的回测逻辑（二段式：触发→买入→卖出）：

1. **批量查询**：一次性查询 `start_date` 至 `end_date` 范围内全 A 股日线数据
2. **逐日扫描触发条件**：对每个交易日，检查哪些股票满足"大涨 + 冲高回落 + 放量 + 首根"等全部条件（复用 `_select_stage1` 的判定逻辑）
3. **判断买入**：对每个触发信号，检查 T+1 日是否低开至少 3%；若满足则以 T+1 开盘价买入
4. **确定卖出**：T+2 日开盘价卖出
5. **处理边界**：若 T+1 或 T+2 数据缺失（停牌/未覆盖）则跳过；若 T+2 超出 end_date 则标为"unclosed"
6. **返回 `BacktestResult`**：包含所有 `BacktestTrade` + skipped_count

**性能考量**：批量 SQL 查全范围数据（一次查询），内存中遍历计算，避免逐日查询（700+ 次 SQL）。

#### 5）绩效指标计算（`backtest_report.py`）

```python
def calculate_report(trades: list[BacktestTrade]) -> ReportMetrics:
    closed = [t for t in trades if t.trade_type == "closed"]
    unclosed = [t for t in trades if t.trade_type == "unclosed"]

    total = len(closed)
    if total == 0:
        return ReportMetrics(total_trades=0, ...)  # 空报告

    wins = [t for t in closed if t.return_rate > 0]
    losses = [t for t in closed if t.return_rate <= 0]

    return ReportMetrics(
        total_trades=total,
        win_trades=len(wins),
        lose_trades=len(losses),
        win_rate=len(wins) / total,
        total_return=sum(t.return_rate for t in closed),
        avg_return=sum(t.return_rate for t in closed) / total,
        max_win=max((t.return_rate for t in closed), default=0),
        max_loss=min((t.return_rate for t in closed), default=0),
        unclosed_count=len(unclosed),
    )
```

#### 6）大盘温度关联（引擎职责）

回测引擎在策略返回交易列表后，统一为每笔交易补充买入日的大盘温度。这是引擎的通用能力，不需要策略关心。

```python
def enrich_trades_with_temperature(db: Session, trades: list[BacktestTrade]) -> list[BacktestTrade]:
    """批量查询所有买入日的大盘温度，补充到每笔交易中。"""
    buy_dates = list({t.buy_date for t in trades})
    temps = (
        db.query(MarketTemperatureDaily.trade_date, 
                 MarketTemperatureDaily.temperature_score,
                 MarketTemperatureDaily.temperature_level)
        .filter(MarketTemperatureDaily.trade_date.in_(buy_dates))
        .all()
    )
    temp_map = {t.trade_date: (t.temperature_score, t.temperature_level) for t in temps}
    
    enriched = []
    for trade in trades:
        score, level = temp_map.get(trade.buy_date, (None, None))
        enriched.append(replace(trade, market_temp_score=score, market_temp_level=level))
    return enriched
```

#### 7）按大盘温度分组统计

在绩效指标计算中，按 `market_temp_level` 分组统计各温度级别下的胜率与平均收益：

```python
def calculate_temp_level_stats(trades: list[BacktestTrade]) -> list[dict]:
    """按大盘温度级别分组统计。"""
    closed = [t for t in trades if t.trade_type == "closed" and t.market_temp_level]
    groups: dict[str, list] = {}
    for t in closed:
        groups.setdefault(t.market_temp_level, []).append(t)
    
    stats = []
    for level, group in groups.items():
        wins = [t for t in group if t.return_rate > 0]
        stats.append({
            "level": level,
            "total": len(group),
            "wins": len(wins),
            "win_rate": len(wins) / len(group),
            "avg_return": sum(t.return_rate for t in group) / len(group),
        })
    return sorted(stats, key=lambda s: s["total"], reverse=True)
```

此统计结果存入 `backtest_task.assumptions_json` 的 `temp_level_stats` 字段，同时通过 API 返回给前端在报告中展示。

#### 8）盈亏结论生成

```python
def generate_conclusion(total_return: float, start_date: date, end_date: date) -> str:
    if total_return > 0:
        return f"该策略在 {start_date} 至 {end_date} 期间总体盈利 {total_return:.2%}"
    elif total_return < 0:
        return f"该策略在 {start_date} 至 {end_date} 期间总体亏损 {abs(total_return):.2%}"
    else:
        return f"该策略在 {start_date} 至 {end_date} 期间收益持平"
```

#### 9）前端轮询策略

用户发起回测后返回列表。前端以 **5 秒间隔轮询** `GET /api/backtest/tasks`（仅当列表中存在 `status=running` 的任务时轮询，否则停止）。任务完成后停止轮询，用户点击"查看"进入详情。

#### 10）参数校验逻辑

`POST /api/backtest/run` 的校验顺序：

1. `strategy_id` 是否存在（通过 `get_strategy()` 查 registry）
2. `start_date`、`end_date` 格式是否合法
3. `start_date < end_date`
4. 日期范围是否在数据库日线数据覆盖范围内（查 `stock_daily_bar` 的 MIN/MAX trade_date）

## 项目结构

### 本功能文档

```text
specs/010-智能回测/
├── plan.md              # 本文件
├── spec.md              # 功能规格
├── research.md          # Phase 0 调研结论
├── data-model.md        # Phase 1 数据模型
├── quickstart.md        # Phase 1 本地运行与验证
├── contracts/           # Phase 1 接口契约
│   └── backtest-api.md  # API 契约
└── checklists/
    └── requirements.md  # 规格质量检查清单
```

### 源码结构（本功能新增/修改）

```text
backend/
├── app/
│   ├── api/
│   │   └── backtest.py                    # [新增] 回测 API 路由（5 个端点）
│   ├── models/
│   │   ├── __init__.py                    # [修改] 注册新模型
│   │   ├── backtest_task.py               # [新增] 回测任务 ORM 模型
│   │   └── backtest_trade.py              # [新增] 回测交易明细 ORM 模型
│   ├── schemas/
│   │   └── backtest.py                    # [新增] 请求/响应 Pydantic 模型
│   ├── services/
│   │   ├── backtest/
│   │   │   ├── __init__.py                # [新增]
│   │   │   ├── backtest_engine.py         # [新增] 回测引擎（任务执行主流程）
│   │   │   └── backtest_report.py         # [新增] 绩效指标计算
│   │   └── strategy/
│   │       ├── strategy_base.py           # [修改] 新增 BacktestTrade/BacktestResult/backtest() 接口
│   │       └── strategies/
│   │           └── chong_gao_hui_luo.py   # [修改] 实现 backtest() 方法
│   └── main.py                            # [修改] 注册 backtest router
├── scripts/
│   └── add_backtest_tables.sql            # [新增] 建表 SQL
└── tests/
    └── test_backtest.py                   # [新增] 回测核心逻辑测试

frontend/
├── src/
│   ├── router/index.ts                    # [修改] 新增回测路由
│   ├── views/
│   │   ├── Layout.vue                     # [修改] 侧边栏新增"智能回测→历史回测"菜单
│   │   └── HistoryBacktestView.vue        # [新增] 历史回测页面
│   ├── api/
│   │   └── backtest.ts                    # [新增] 回测 API 封装
│   └── components/
│       ├── BacktestConfigPanel.vue        # [新增] 回测配置面板（策略选择+日期范围）
│       ├── BacktestTaskList.vue           # [新增] 回测记录列表
│       └── BacktestResultDetail.vue       # [新增] 回测结果详情（报告+明细表格）
└── ...
```

**结构说明**：
- 后端遵循既有分层（API → Service → Model），回测服务独立为 `services/backtest/` 包，与策略服务（`services/strategy/`）通过 `StockStrategy.backtest()` 接口耦合
- 前端拆为三个独立组件（配置、列表、详情），由 `HistoryBacktestView.vue` 统一编排
- 策略接口的修改是向后兼容的扩展（新增方法，不修改已有方法签名）

## 复杂度与例外

无。
