# 实现计划：历史模拟交易

**分支**: `main` | **日期**: 2026-04-09 | **规格**: `./spec.md`

## 概要

本期交付「历史模拟交易」功能：用户选择历史日期和初始资金，进入全屏交互式交易界面，逐日推进模拟时间，手动买入/卖出股票，查看 K 线图表，体验 A 股真实交易规则（T+1、涨跌停、手续费）。

每个交易日分**开盘**和**收盘**两个时间节点，流程为：
```
进入新交易日（开盘）→ 查看/操作 → 推进到收盘 → 查看/操作 → 进入下一交易日（开盘）→ …
```

核心架构：**后端提供无状态 REST API（持久化到 MySQL）+ 前端全屏交易页面（ECharts 图表 + Element Plus 交互）**。与现有「历史模拟」（策略自动回测）完全独立，新建 `/api/paper-trading` 路由和独立数据表。

---

## 技术背景

- **语言/版本**：Python 3.12，TypeScript 5.x
- **主要依赖**：FastAPI、SQLAlchemy 2.0、MySQL；Vue 3、Vite、Element Plus、Pinia、ECharts
- **存储**：MySQL（新增 3 张表）
- **目标平台**：本地部署 + 现代浏览器
- **性能目标**：图表数据加载 < 3 秒（300 条日线），筛选接口 < 5 秒
- **约束**：仅日线数据，无分时数据；买卖价格用户手动输入

---

## 章程检查

项目宪法为占位模板，按项目既有规范执行：中文文档、Spec 驱动、不超范围交付、策略类写详细中文注释。

---

## 关键设计详述

### 数据流与接口职责

#### 时间节点状态机

```
会话 current_phase: 'open'（开盘）| 'close'（收盘）

进入新交易日 → current_phase = 'open'
  图表：最新 K 线只有 open（high/low/close 显示为 null）
  快捷按钮：仅「开盘价」
  可操作：买入、卖出（T+1 可卖批次）

点击「推进到收盘」→ current_phase = 'close'
  图表：最新 K 线补全 high/low/close
  快捷按钮：「开盘价」+「收盘价」
  持仓市值：按收盘价更新

点击「进入下一交易日」→ current_phase = 'open'，current_date 推进
  （仅在 current_phase = 'close' 时可用）
```

#### 整体数据流

```
用户操作                    前端（Vue 3）                    后端（FastAPI）
────────                   ──────────────                   ──────────────
选择日期+资金  →  POST /api/paper-trading/sessions  →  创建 session（current_phase='open'）
                   ← 201 { session_id, current_date, current_phase }

进入交易界面   →  路由跳转 /paper-trading/:session_id
               →  GET /sessions/:id（持仓+账户+phase）
               →  GET /recommend（推荐股票）

查看图表       →  GET /chart-data?stock_code=&end_date=&phase=open|close
                   phase=open：最新 K 线 close/high/low 返回 null
                   phase=close：返回完整 K 线
                   ← 300 条数据

买入/卖出      →  POST /sessions/:id/buy | /sell
                   ← 200 { order_id, cash_after }

推进到收盘     →  POST /sessions/:id/advance-to-close
                   ← 200 { current_phase: 'close', positions（市值按收盘价更新）}

进入下一交易日 →  POST /sessions/:id/next-day（仅 phase=close 时允许）
                   ← 200 { current_date, current_phase: 'open', positions }

自定义筛选     →  GET /screen?trade_date=&pct_change_min=&...
                   ← 分页股票列表
```

### 前后端职责划分

| 职责 | 后端 | 前端 |
|------|------|------|
| 持仓批次存储（FIFO） | ✓ | |
| T+1 规则验证 | ✓ | |
| 涨跌停价格计算 | ✓ | |
| 手续费计算 | ✓ | |
| 资金充足验证 | ✓ | |
| 持仓聚合（加权均价） | ✓（API 返回聚合结果） | |
| 图表数据截止日期过滤 | ✓ | |
| 开盘状态时隐藏 close/high/low | ✓（API 返回 null） | ✓（图表不绘制） |
| 均线金叉/MACD 金叉筛选 | ✓ | |
| current_phase 状态维护 | ✓ | |
| ECharts 图表渲染 | | ✓ |
| 开盘/收盘价快捷填充按钮（按 phase 显示） | | ✓ |
| 「推进到收盘」「进入下一交易日」按钮状态控制 | | ✓ |
| 买卖表单验证（前端提示） | | ✓（后端也验证） |

---

## 实现阶段

### 阶段一：后端数据库与基础 API（P1）

#### 1.1 新建数据库表

新建 `backend/app/models/paper_trading.py`，包含三个 SQLAlchemy 模型：

**`PaperTradingSession`**（表 `paper_trading_session`）：
- 字段：`id`(BIGINT PK)、`session_id`(VARCHAR 64, UNIQUE)、`name`(VARCHAR 100)、`start_date`(DATE)、`current_date`(DATE)、`current_phase`(VARCHAR 10, DEFAULT 'open'，取值 `open`/`close`)、`initial_cash`(DECIMAL 20,2)、`available_cash`(DECIMAL 20,2)、`status`(VARCHAR 20, DEFAULT 'active')、`created_at`、`updated_at`
- 索引：`uk_pts_session_id`(UNIQUE, session_id)、`idx_pts_status`(status, created_at)

**`PaperTradingPosition`**（表 `paper_trading_position`）：
- 字段：`id`(BIGINT PK)、`session_id`(VARCHAR 64)、`stock_code`(VARCHAR 20)、`stock_name`(VARCHAR 50)、`buy_date`(DATE)、`buy_price`(DECIMAL 12,4)、`quantity`(INT)、`remaining_quantity`(INT)、`commission`(DECIMAL 12,4)、`status`(VARCHAR 20, DEFAULT 'holding')、`created_at`
- 索引：`idx_ptp_session_stock`(session_id, stock_code, buy_date)、`idx_ptp_session_status`(session_id, status)

**`PaperTradingOrder`**（表 `paper_trading_order`）：
- 字段：`id`(BIGINT PK)、`session_id`(VARCHAR 64)、`order_type`(VARCHAR 10)、`stock_code`(VARCHAR 20)、`stock_name`(VARCHAR 50)、`trade_date`(DATE)、`price`(DECIMAL 12,4)、`quantity`(INT)、`amount`(DECIMAL 20,2)、`commission`(DECIMAL 12,4)、`cash_after`(DECIMAL 20,2)、`position_id`(BIGINT, NULL)、`created_at`
- 索引：`idx_pto_session`(session_id, trade_date)、`idx_pto_session_stock`(session_id, stock_code)

执行 `alembic revision --autogenerate -m "add paper trading tables"` 生成迁移，`alembic upgrade head` 应用。

#### 1.2 新建 Pydantic Schemas

新建 `backend/app/schemas/paper_trading.py`，定义：
- `CreateSessionRequest`：start_date, initial_cash, name(可选)
- `SessionResponse`：session_id, name, start_date, current_date, initial_cash, available_cash, status, positions, total_asset, total_profit_loss, total_profit_loss_pct, created_at
- `PositionSummary`：stock_code, stock_name, total_quantity, avg_cost_price, current_price, market_value, profit_loss, profit_loss_pct, can_sell_quantity
- `BuyRequest`：stock_code, price, quantity
- `SellRequest`：stock_code, price, quantity
- `OrderResponse`：order_id, order_type, stock_code, stock_name, price, quantity, amount, commission, cash_after
- `ChartDataResponse`：stock_code, stock_name, period, data(list), limit_up, limit_down
- `ChartBar`：date, open, high, low, close, volume, prev_close, pct_change, ma5, ma10, ma20, ma60, macd_dif, macd_dea, macd_hist
- `RecommendResponse`：trade_date, items(list of StockQuote)
- `ScreenResponse`：trade_date, total, page, page_size, items

#### 1.3 新建 Service 层

新建 `backend/app/services/paper_trading_service.py`，实现：

**`create_session(db, start_date, initial_cash, name)`**：
- 验证 start_date 是否为交易日（查 stock_daily_bar 是否有该日数据）
- 验证 initial_cash >= 1000
- 生成 session_id = `pt-{uuid4().hex[:8]}`
- 写入 PaperTradingSession，`current_phase='open'`

**`get_session_detail(db, session_id)`**：
- 查询会话基本信息（含 current_phase）
- 查询所有 status='holding' 的持仓批次
- 按 stock_code 聚合：加权均价、总数量、can_sell_quantity（排除当日买入批次）
- 持仓市值参考价：phase='open' 时用开盘价，phase='close' 时用收盘价
- 计算市值、盈亏、总资产

**`advance_to_close(db, session_id)`**：
- 验证 session.status='active' 且 current_phase='open'
- 更新 session.current_phase = 'close'
- 返回更新后的持仓列表（市值改用收盘价重算）

**`next_day(db, session_id)`**：
- 验证 session.current_phase='close'（开盘状态不允许跳日）
- 查询 stock_daily_bar 中 > current_date 的最小 trade_date
- 若无则返回 NO_MORE_DATES 错误
- 更新 session.current_date = 下一交易日，current_phase = 'open'

**`buy(db, session_id, stock_code, price, quantity)`**：
- 验证会话 status='active'
- 查询当日 stock_daily_bar（验证非停牌、获取 prev_close、open、close）
- 验证价格在涨跌停范围内（prev_close × 0.9 ~ prev_close × 1.1）
- 验证 quantity % 100 == 0
- 计算 commission = max(price × quantity × 0.0003, 5.0)
- 验证 available_cash >= price × quantity + commission
- 写入 PaperTradingPosition（remaining_quantity = quantity，buy_phase = session.current_phase）
- 写入 PaperTradingOrder
- 更新 session.available_cash -= (price × quantity + commission)

**`sell(db, session_id, stock_code, price, quantity)`**：
- 验证会话 status='active'
- 查询当日 stock_daily_bar（验证非停牌、获取 prev_close）
- 验证价格在涨跌停范围内
- 验证 quantity % 100 == 0
- 查询可卖批次（status='holding' AND buy_date != current_date），按 buy_date ASC, id ASC
- 验证可卖总量 >= quantity
- FIFO 扣减 remaining_quantity，归零则 status='closed'
- 计算 commission = max(price × quantity × 0.0013, 5.0)
- 写入 PaperTradingOrder
- 更新 session.available_cash += (price × quantity - commission)

**`get_chart_data(db, stock_code, end_date, phase, period, limit)`**：
- period='daily'：查 stock_daily_bar WHERE stock_code=? AND trade_date <= end_date ORDER BY trade_date DESC LIMIT limit，反转后返回
- period='weekly'：查 stock_weekly_bar WHERE trade_week_end <= end_date
- period='monthly'：查 stock_monthly_bar WHERE trade_month_end <= end_date
- **phase 处理**：最新一条（trade_date == end_date）若 phase='open'，则将 high/low/close/macd_dif/macd_dea/macd_hist 置为 null 返回（前端不绘制这些值）
- 同时返回 end_date 当日的 limit_up = round(prev_close × 1.1, 2)，limit_down = round(prev_close × 0.9, 2)
- 同时返回当日 open_price 和 close_price（phase='open' 时 close_price 为 null）

**`recommend_stocks(db, trade_date, phase, count)`**：
- 查询 stock_daily_bar WHERE trade_date=? 的所有股票
- 随机抽取 count 条（Python random.sample）
- phase='open' 时 close/pct_change 返回 null（收盘前不知道涨跌幅）
- 返回 stock_code, stock_name, open, close, pct_change, volume, limit_up, limit_down

**`screen_stocks(db, trade_date, filters, page, page_size)`**：
- 基础查询：stock_daily_bar WHERE trade_date=?
- 若 pct_change_min/max：AND pct_change BETWEEN ? AND ?
- 若 volume_min/max：AND volume BETWEEN ? AND ?
- 若 ma_golden_cross='ma5_ma10'：AND ma5 > ma10，同时 JOIN 前一日验证 prev.ma5 <= prev.ma10
- 若 macd_golden_cross=True：AND macd_dif > macd_dea，同时 JOIN 前一日验证 prev.macd_dif <= prev.macd_dea
- 分页返回

> 均线金叉/MACD 金叉需要前一日数据，实现方式：子查询或 JOIN stock_daily_bar AS prev WHERE prev.stock_code = cur.stock_code AND prev.trade_date = (SELECT MAX(trade_date) FROM stock_daily_bar WHERE stock_code = cur.stock_code AND trade_date < trade_date)

#### 1.4 新建 API 路由

新建 `backend/app/api/paper_trading.py`，注册路由 prefix='/paper-trading'，实现 **13 个端点**（详见 contracts/api.md）：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/sessions` | POST | 创建会话 |
| `/sessions` | GET | 会话列表 |
| `/sessions/{id}` | GET | 会话详情（含持仓聚合） |
| `/sessions/{id}/advance-to-close` | POST | 推进到收盘（phase: open→close） |
| `/sessions/{id}/next-day` | POST | 进入下一交易日（phase: close→open，date+1） |
| `/sessions/{id}/end` | POST | 结束会话 |
| `/sessions/{id}/buy` | POST | 买入 |
| `/sessions/{id}/sell` | POST | 卖出 |
| `/sessions/{id}/orders` | GET | 交易记录 |
| `/chart-data` | GET | 图表数据（含 phase 参数） |
| `/recommend` | GET | 随机推荐股票 |
| `/screen` | GET | 自定义筛选股票 |
| `/trading-dates` | GET | 交易日列表 |

在 `backend/app/main.py` 中注册：
```python
from app.api import paper_trading
app.include_router(paper_trading.router, prefix="/api")
```

---

### 阶段二：前端交易入口页（P1）

#### 2.1 新建会话列表/创建页

新建 `frontend/src/views/PaperTradingView.vue`：
- 顶部：「开始新模拟」按钮，点击弹出 `el-dialog`
  - 日期选择器（`el-date-picker`，限制在数据范围内）
  - 初始资金输入框（默认 100000）
  - 会话名称输入框（可选）
  - 确认后调用 POST /sessions，跳转到 `/paper-trading/:session_id`
- 下方：已有会话列表（`el-table`），显示名称、起始日期、当前日期、总资产、盈亏、状态
- 每行「继续」按钮跳转到交易界面

在 `frontend/src/router/index.ts` 新增路由：
```typescript
{ path: 'paper-trading', name: 'paper-trading', component: () => import('@/views/PaperTradingView.vue') },
{ path: 'paper-trading/:sessionId', name: 'paper-trading-session', component: () => import('@/views/PaperTradingSessionView.vue') },
```

在 `frontend/src/views/Layout.vue` 侧边栏新增「历史模拟交易」菜单项。

#### 2.2 新建 API 调用文件

新建 `frontend/src/api/paperTrading.ts`，封装所有 12 个接口的 axios 调用，定义完整 TypeScript 类型。

---

### 阶段三：前端交易界面（P1）

新建 `frontend/src/views/PaperTradingSessionView.vue`，全屏布局分三栏：

**左栏（宽 280px）：账户与持仓面板**
- 账户信息卡片：
  - 当前模拟日期 + 时间节点标签（`el-tag`：开盘 / 收盘，不同颜色区分）
  - 总资产、可用资金、总盈亏（金额+百分比，红绿色）
- 持仓列表（`el-table`）：股票名称、均价、现价、数量、市值、盈亏%
  - 点击持仓行 → 中栏图表切换到该股票
  - 「卖出」按钮 → 弹出卖出表单
- 底部操作区（两个按钮，互斥显示）：
  - phase='open' 时：显示「推进到收盘 →」按钮（调用 advance-to-close）
  - phase='close' 时：显示「进入下一交易日 →」按钮（调用 next-day）

**中栏（flex-grow）：K 线图表区**
- 股票搜索框（输入代码/名称）
- 日/周/月 切换 Tab
- ECharts 图表，上下分三个子图：
  1. K 线图 + MA5/MA10/MA20/MA60 均线（占 60% 高度）
  2. 成交量柱状图（占 20% 高度，涨红跌绿）
  3. MACD 图（DIF 线 + DEA 线 + HIST 柱，占 20% 高度）
- 三图共享 X 轴，dataZoom 联动缩放
- tooltip 悬停显示当日 OHLCV + 指标数据
- **phase='open' 时**：最新 K 线只绘制开盘价（显示为十字线或仅 open 点），high/low/close 为 null 不绘制；MACD 最新值也不绘制
- **phase='close' 时**：最新 K 线完整绘制

**右栏（宽 320px）：选股与交易面板**
- Tab 切换：「推荐」/ 「筛选」
  - 推荐 Tab：10 支随机推荐股票列表，「换一批」按钮
    - phase='open' 时涨跌幅列显示「-」（收盘前未知）
  - 筛选 Tab：涨跌幅范围、成交量范围、均线金叉选择、MACD 金叉开关，「筛选」按钮，结果列表
- 股票列表每行：代码、名称、涨跌幅、「查看」（加载图表）、「买入」（弹出买入表单）
- 买入表单（`el-dialog`）：
  - 股票名称（只读）
  - 价格输入框 + 快捷按钮：
    - phase='open'：仅显示「开盘价」按钮
    - phase='close'：显示「开盘价」+「收盘价」两个按钮
  - 数量输入框（步进 100）
  - 预计金额 + 手续费（实时计算）
  - 确认买入按钮
- 卖出表单（`el-dialog`）：
  - 股票名称、可卖数量（只读）
  - 价格输入框 + 快捷按钮（同买入，按 phase 显示）
  - 数量输入框（步进 100，最大 = can_sell_quantity）
  - 预计金额 + 手续费（实时计算）
  - 确认卖出按钮

**能力说明悬浮提示**（页面标题旁 `?` 图标，`el-tooltip`）：
> 历史模拟交易：选择历史节点逐日推进，手动买卖股票，体验 A 股 T+1 规则。图表数据截止到当前模拟日期，不展示未来信息。

---

### 阶段四：前端 Pinia Store（P1）

新建 `frontend/src/stores/paperTrading.ts`，管理：
- `currentSession`：当前会话详情（含持仓聚合、current_phase）
- `chartData`：当前查看股票的图表数据
- `recommendList`：推荐股票列表
- `screenResult`：筛选结果
- Actions：`loadSession`、`advanceToClose`、`nextDay`、`buyStock`、`sellStock`、`loadChartData`、`loadRecommend`、`screenStocks`
- Getters：`isOpenPhase`（current_phase === 'open'）、`canNextDay`（current_phase === 'close'）

---

### 阶段五：同步更新 spec.md（P1）

实现完成后同步更新 `specs/020-历史模拟交易/spec.md` 状态为「已实现」，记录实现日期。

---

## 文件变更清单

### 新增文件

| 文件路径 | 说明 |
|----------|------|
| `backend/app/models/paper_trading.py` | 三个 SQLAlchemy 模型 |
| `backend/app/schemas/paper_trading.py` | Pydantic 请求/响应 Schema |
| `backend/app/services/paper_trading_service.py` | 业务逻辑（买卖/FIFO/筛选等） |
| `backend/app/api/paper_trading.py` | FastAPI 路由（12 个端点） |
| `frontend/src/api/paperTrading.ts` | 前端 API 调用封装 |
| `frontend/src/stores/paperTrading.ts` | Pinia Store |
| `frontend/src/views/PaperTradingView.vue` | 会话列表/创建页 |
| `frontend/src/views/PaperTradingSessionView.vue` | 全屏交易界面 |

### 修改文件

| 文件路径 | 修改内容 |
|----------|----------|
| `backend/app/main.py` | 注册 paper_trading 路由 |
| `frontend/src/router/index.ts` | 新增两条路由 |
| `frontend/src/views/Layout.vue` | 侧边栏新增菜单项 |

### 数据库迁移

```bash
cd backend
alembic revision --autogenerate -m "add paper trading tables"
alembic upgrade head
```

---

## 风险与注意事项

1. **均线金叉筛选性能**：需要 JOIN 前一日数据，全市场 5000+ 股票可能较慢，建议加索引 `(stock_code, trade_date)` 并限制返回数量。
2. **图表数据量**：300 条日线数据约 300 × 15 字段，JSON 响应约 50KB，在 3 秒内可接受。
3. **ECharts 多图联动**：三图共享 dataZoom 需要在同一 ECharts 实例中配置，使用 `grid` 分区布局。
4. **停牌判断**：以当日 stock_daily_bar 是否有数据为准，若某股票当日无数据则视为停牌。
