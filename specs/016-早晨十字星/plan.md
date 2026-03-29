# 实现计划：早晨十字星（回测内置策略）

**分支**: `main`（本地开发分支名；规格目录 `016-早晨十字星`） | **日期**: 2026-03-29 | **规格**: [`spec.md`](./spec.md)  
**输入**: 功能规格来自 `specs/016-早晨十字星/spec.md`

**说明**: 全文使用中文，粒度达到**可直接按方案实现**。

## 概要

在现有「智能回测 + 策略注册表」架构上，新增内置策略 **早晨十字星**：在**跌势后期**识别 **T−2～T** 三根日线（大阴线 → 锤头 → 放量阳线），并沿用 **「曙光初现」** 的放量/历史高位过滤与 **买入（首次站上 MA5）/ 卖出（**本策略 −8%** 固定止损，**异于**曙光初现之 −10%；收盘 ≥ 买入×1.1 当日止盈）** 仿真逻辑。交付物为**新策略类文件**、**注册表注册**、**查询列增加 high/low**、**类文档与测试**；无新定时任务、无新数据库表。

## 技术背景

- **语言/版本**: Python（与仓库一致，建议 3.11+）、TypeScript / Vue 3（前端仅消费策略列表）
- **主要依赖**: FastAPI、SQLAlchemy 2.x、MySQL；策略层见 `app/services/strategy/`
- **存储**: MySQL，复用 `stock_daily_bar`、`backtest_task`、`backtest_trade`（无表结构变更）
- **测试**: pytest（策略判定建议表驱动单测）
- **目标平台**: 本地 / 服务器部署，浏览器访问前端
- **项目类型**: Web 应用（后端为主；前端回测页依赖 `/api/strategies`）
- **性能目标**: 与单策略全市场日线回测同量级；本策略较「曙光初现」多两日形态与锤头计算，增量可忽略，不设单独 SLA
- **约束**: 仅日线；策略逻辑代码内嵌，用户不可配参（与现有内置策略一致）
- **规模/范围**: A 股全市场扫描模式与 `ShuGuangChuXianStrategy` 相同

## 章程检查

`/.specify/memory/constitution.md` 仍为占位模板，无已核定强制门禁。本计划遵循项目既有约定：**简体中文**规格与注释、Spec 与实现对齐、策略类遵循 `.cursor/rules/strategy-class-documentation.mdc`。

**Phase 1 设计后复检**：无新增违反项。

## 关键设计详述

### 数据流与接口职责

#### 整体数据流

```
注册策略类
    → list_strategies() 含「早晨十字星」
         → GET /api/strategies 前端回测下拉展示
         → GET /api/strategies/{id} 详情页/说明
    → POST /api/strategies/{id}/execute 选股执行
    → POST /api/backtest/run（strategy_id=zao_chen_shi_zi_xing）
         → 回测引擎加载策略实例并调用 backtest(start_date, end_date)
         → 写入 backtest_task / backtest_trade（trigger_date = T）
```

#### 后端分层与文件

| 层级 | 路径 | 职责 |
|------|------|------|
| 策略实现 | `backend/app/services/strategy/strategies/zao_chen_shi_zi_xing.py`（新建） | 实现 `StockStrategy`：`describe`、`execute`、`backtest`；内含 `_run_backtest` 与锤头判定私有函数 |
| 注册表 | `backend/app/services/strategy/registry.py` | `from ... zao_chen_shi_zi_xing import ZaoChenShiZiXingStrategy`，`list_strategies()` 追加实例 |
| 协议与数据类 | `backend/app/services/strategy/strategy_base.py` | **不修改** Protocol；复用 `BacktestTrade.trigger_date` |
| API | `app/api/strategies.py`、`app/api/backtest.py` | **不新增路由**；注册后自动可用 |

#### 策略内核索引约定

- 使用与 `shu_guang_chu_xian.py` 相同的 `stock_bars[code]` 按日升序列表。
- 令 **`bar_t = bars_list[i]` 为信号日 T**（第三根阳线日），则：
  - **T−2** = `i−2`，**T−1** = `i−1`，**T** = `i`
  - 前期 7 日（**T−9 … T−3**）对应 `i−9 … i−3`
  - 累计跌幅：`close[i−3] / close[i−9] − 1 ≤ −10%`
  - 阴线计数：对 `j ∈ [i−9, i−3]` 共 7 根，统计 `close < open` 的天数 ≥ 5
- 循环下界：**`i ≥ 9`**（保证存在 `i−9`）；主循环 `for i in range(9, len(bars_list))`（若与其他常量取 max 则写 `max(9, …)`）。
- **触发区间**：仅当 `bar_t.trade_date ∈ [start_date, end_date]` 时尝试生成信号（与曙光初现一致）。

#### 形态与过滤（顺序建议）

按「廉价→昂贵」排列以减少无效计算：

1. 数据有效性：`open`/`close`/`high`/`low` 在 T−2、T−1、T 及所需历史日非空且为正（按现有代码风格用 float 比较）。
2. **T** 为阳线，实体涨幅 ≥ 3%；**T−2** 为阴线，**(close_{T−2}/close_{T−3}−1) ≤ −2%**。
3. **T−1** 锤头 + **|(close_{T−1}/close_{T−2}−1)| ≤ 1%**（锤头数值规则见 `research.md`）。
4. **T** 日跌势均线 **MA5 < MA10 < MA20** 且 **close < MA20**；**cum_hist_high** 有效且 **close ≤ 0.5×cum_hist_high**。
5. 前期 7 日（T−9…T−3）弱势与累计跌幅（见上）。
6. **T** 日放量：**volume_T ≥ 1.5 × mean(volume_{T−7…T−1})**，且 T 与 T−7…T−1 各日 volume 均有效（逻辑同 `shu_guang_chu_xian`，索引区间不变）。
7. **买入索引**：自 `i` 起向后找首次 `close > MA5`；若 `buy_date > end_date` 则本段不记交易。
8. **卖出仿真**：自 `buy_idx+1` 起逐日，**顺序**与曙光初现相同（先止损后止盈），但**止损比例为本策略 8%**（卖价固定 `买入价×0.92`，`stop_loss_8pct`），勿与曙光初现的 10%/`×0.90` 混用；否则若 `close ≥ 买入价×1.10` → 按当日收盘价止盈；未触发则 `unclosed`。
9. **同一标的单仓**：`last_block` 与曙光初现相同，未平仓则 `break` 跳出该标的后续扫描。

#### 数据查询（`_run_backtest`）

- `select` 字段在曙光初现基础上**必须增加** `StockDailyBar.high`、`StockDailyBar.low`。
- `where trade_date.between(extended_start, extended_end)` 与现有策略相同；`extended_start = start_date − timedelta(days=60)` 可保留（覆盖 T−9 与均线预热）；若边界案例不足，可改为 90 天，与产品经理确认前**优先 60 天与曙光一致**。

#### 前端职责

| 区域 | 行为 |
|------|------|
| 历史回测 `BacktestConfigPanel.vue` | 自 `/api/strategies` 填充下拉，**无需**为每个策略硬编码 |
| 侧栏「策略选股」 | **可选**：新增「早晨十字星」菜单项与视图（见 `research.md`）；**P1 不阻塞** |
| `BacktestResultDetail.vue` | 触发日 Tooltip 已泛化「如曙光初现」，可改为「如曙光初现、早晨十字星」——**文案小改，可选** |

#### 错误与异常

- 数据库缺列 `cum_hist_high`：与曙光初现相同，抛出带迁移指引的 `RuntimeError`（可选：本策略与曙光共用同一提示文案）。
- `strategy_id` 错误：由回测 API 返回 404 `STRATEGY_NOT_FOUND`（现有行为）。

### 定时任务与部署设计

**本功能不涉及定时任务。** 回测与策略执行均为用户或接口按需触发。

### 其他关键设计

1. **strategy_id**：`zao_chen_shi_zi_xing`；**类名**：`ZaoChenShiZiXingStrategy`；**version**：建议 `v1.0.0` 起。
2. **`describe().route_path`**：`/strategy/zao-chen-shi-zi-xing`，与 `shu_guang_chu_xian` 命名风格一致；前端路由未接时仅为占位。
3. **`execute()`**：复制曙光初现模式：`as_of_date` 单日回测，筛 `buy_date == as_of_date` 的 `BacktestTrade` 转 `StrategyCandidate`。
4. **`extra` 建议字段**：`pattern_first_date`、`pattern_hammer_date`、`pattern_yang_date`（ISO 日期）、`hammer_ok`、`prior_bearish_days`、`prior_cum_drop_pct`、`exit_reason` 等，便于 SC-003 核对。
5. **文档**：新建策略文件顶部与类 docstring 按 `strategy-class-documentation.mdc` 写满「口径、阈值公式、边界、示例」。

## 项目结构

### 本功能文档

```text
specs/016-早晨十字星/
├── plan.md              # 本文件
├── research.md          # Phase 0 调研结论
├── data-model.md        # Phase 1 数据模型（复用说明）
├── quickstart.md        # Phase 1 验证步骤
├── contracts/
│   └── strategy-api.md # 既有 API 的增量契约
└── spec.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── api/
│   │   ├── strategies.py      # 无改或仅 import 副作用（注册新类后自动）
│   │   └── backtest.py
│   ├── models/
│   │   └── stock_daily_bar.py # high/low 已存在
│   └── services/
│       └── strategy/
│           ├── registry.py           # 注册新策略
│           ├── strategy_base.py      # 复用
│           └── strategies/
│               ├── shu_guang_chu_xian.py  # 卖出逻辑对齐参考
│               └── zao_chen_shi_zi_xing.py # 新建

frontend/
├── src/
│   ├── components/
│   │   ├── BacktestConfigPanel.vue
│   │   └── BacktestResultDetail.vue  # 可选 Tooltip 文案
│   ├── router/index.ts             # 可选：新策略说明页
│   └── views/Layout.vue            # 可选：侧栏
```

**结构说明**：策略以**单文件类**交付，与 `shu_guang_chu_xian.py` 平行，便于独立版本管理与测试。

## 复杂度与例外

无。未引入新中间件或并行框架。

---

## Phase 2 说明

任务拆解由 `/speckit.tasks` 生成 `tasks.md`，本命令不生成实现代码。
