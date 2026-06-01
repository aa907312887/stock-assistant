# 实现计划：早晨十字星（简化版）

**分支**: `main` | **日期**: 2026-05-03 | **规格**: [spec.md](./spec.md)  
**输入**: 功能规格来自 `/Users/yangjiaxing/Coding/CursorProject/stock-assistant/specs/026-早晨十字星简化版/spec.md`

**说明**: 全文中文；达到可直接落地的实现粒度。

## 概要

新增内置策略「早晨十字星（简化版）」（建议 `strategy_id=zao_chen_shi_zi_xing_jian_hua`）：**形态与跌势判定**与现有「早晨十字星」实现字节级对齐（复用同一套锤头、三根 K 线、T−9…T−3 窗口、`cum_hist_high` 参与判定）；**价位过滤**将「收盘相对累计历史高」由主策略的 **50%** 改为 **80%（4/5）**；**买入**改为触发日 **T** 的下一交易日**开盘价**（`bars_list[i+1].open`，停牌顺延逻辑见 `research.md`）；**卖出**改为相对买入价的 **固定 +8% 止盈**与 **−6% 止损**，取消主策略的移动止盈（15%+5%）。  

交付物：新策略模块、注册表登记、`strategy_descriptions` 文案、**策略选股页 + 路由 + 侧栏**、**APScheduler 定时选股**（与「早晨十字星」同模式错开 1 分钟）、回测/执行/列表接口经注册自动生效；**不新增数据库表/列**。

## 技术背景

**Language/Version**: Python 3.12（后端）、TypeScript 5.x + Vue 3（前端）

**Primary Dependencies**: FastAPI、SQLAlchemy、APScheduler、Element Plus、Vite、Pinia（与仓库一致）

**Storage**: MySQL（复用既有表，本功能不新增表）

**Project Type**: Web 应用（前后端分离）

- **测试**: `pytest`；关键形态与边界建议表驱动单测（可对照 `zao_chen_shi_zi_xing` 中锤头/窗口用例风格）  
- **目标平台**: 现有后端服务 + 浏览器前端  
- **性能目标**: 与全市场日线扫描的「早晨十字星」同量级；单策略回测不在此功能单独提高指标  
- **约束**: 依赖 `cum_hist_high` 已计算；缺列时与主策略相同类错误提示  
- **规模/范围**: A 股非 ST 全市场；日线；索引下界与主策略相同（`i ≥ 9`）

## 章程检查

- **当前状态**: 仓库内 `.specify/memory/constitution.md` 仍为模板占位，**未核定**；不视为自动门禁。  
- **按项目 CLAUDE.md / 规则**复验：  
  - 策略类须含**详细中文 docstring**（见 `.cursor/rules/strategy-class-documentation.mdc`）。  
  - 本功能**涉及策略选股页能力变更**，前端须在对应页面提供**悬浮能力说明**（Tooltip/Popover），与 `spec.md` 口径一致。  
  - 实现阶段须**同步本目录 `spec.md` 若因实现发现必要口径修正**（按 spec 驱动原则）。  
- **Phase 1 设计后复检**: 无新增违反项；定时任务与主项目既有模式一致。

## 关键设计详述

### 数据流与接口职责

1. **回测**  
   - 用户 → `POST /api/backtest/run`（`strategy_id=zao_chen_shi_zi_xing_jian_hua`）→ 回测服务根据 `strategy_id` 分派至新策略类 `run_backtest` → 从 `stock_daily_bar` 拉取与 `run_morning_star_backtest` 相同字段与扩展日期区间（`extended_start/end` 与主策略一致，保证 T+1 后仍有足够 K 线做卖出仿真）→ 产出 `BacktestResult` / `BacktestTrade`（`trigger_date=T`，`buy_date` 为 T+1 或顺延后的首个有效开盘日）。  
2. **策略列表/详情**  
   - `GET /api/strategies`、`GET /api/strategies/{id}` 经注册表自动包含新策略；**无新路由文件**，仅注册实例。  
3. **选股执行**  
   - `POST /api/strategies/{strategy_id}/execute`、`GET .../latest` 与现有一致；`execute` 内调用与回测**同一套**形态 + 80% 过滤，**信号日 = T** 的候选在业务上表示「若按规则将在下一交易日开盘买入」的提醒（与 `di_wei_lian_yang` 的 T+1 开盘语义一致）。  
4. **前端**  
   - 新页面展示策略说明、手动执行按钮、最近结果；数据来自上述 API；**不**把形态计算放前端。  
5. **错误约定**  
   - 与 `specs/010-智能回测` 及现有策略一致：`STRATEGY_NOT_FOUND` 404、回测参数非法 4xx 等；缺 `cum_hist_high` 时策略内 `RuntimeError` 文案可复用主策略前缀风格，便于运维识别。

### 定时任务与部署设计

本功能**涉及**每日自动选股落库，与「早晨十字星」「低位连阳」同范式。

- **使用的组件**: **APScheduler**（`AsyncIOScheduler`），任务入口定义于 **`backend/app/core/scheduler.py`**，应用生命周期中 **`start_scheduler()`** 注册（与现有策略 Job 一致）。  
- **注册方式**: 在 `start_scheduler()` 内新增 `_job_strategy_zao_chen_shi_zi_xing_jian_hua_daily`（函数名可略缩短），用 **`CronTrigger`** 绑定上海时区；在现有 `_job_strategy_zao_chen_shi_zi_xing_daily`（17:20）之后注册，建议 **17:23** 执行，避免与 17:20–17:22 批量扫描同一进程锁竞争（与 `specs/021-低位连阳/plan.md` 错开思路一致）。  
- **调度策略**: **每个交易日 17:23（Asia/Shanghai）**（或项目统一微调后的相邻分钟，文档与代码保持一致）。  
- **部署时是否执行一次**: **否**（与早晨十字星一致；无启动时 `DateTrigger` 立即全量执行）。  
- **手动触发方式**:  
  - [x] **HTTP**：`POST /api/strategies/zao_chen_shi_zi_xing_jian_hua/execute`（路径参数以实际 `strategy_id` 为准），请求体可含 `as_of_date`；鉴权与现有策略执行接口相同（Bearer Token）。  
  - [ ] 单独管理命令：不强制新增（除非团队惯例要求脚本封装 curl）。  
- **失败与重试**: 不因单次失败自动无限重试；记录 **error 日志**（含 `StrategyDataNotReadyError` 等原因）；与现有 ``execute_strategy`` 捕获方式对齐；**无单独告警渠道**（与现有策略 Job 一致）。  
- **日志与可观测**: Job 入口打 **INFO**：交易日跳过原因、执行完成、`as_of_date`；异常 stack 走现有 logging。

### 其他关键设计

1. **代码复用策略（核心）**  
   - **方案 A（推荐）**: 在新文件 `zao_chen_shi_zi_xing_jian_hua.py` 中实现 **`run_morning_star_jian_hua_backtest`**（或等价命名）：将 `zao_chen_shi_zi_xing.py` 中 **从「形态通过」到 `last_block` 更新** 的逻辑复制并改写参数（`max_close_to_cum_hist_high_ratio=0.8`）、买入分支（`buy_idx = i+1` 且 `buy_price = open`，若停牌则 `while` 顺延至下一有效 bar）、卖出分支（仅 **stop_loss_6pct** / **take_profit_8pct**，循环内先判止损再判止盈，与规格「同日优先止损」一致）。通过 **复制+注释对齐行号** 避免与 `pe_zao_chen_shi_zi_xing` 的 `run_morning_star_backtest` 循环依赖，降低耦合。  
   - **方案 B**: 给 `run_morning_star_backtest` 增加大量参数（买入模式、卖出模式）——**不推荐**，易破坏主策略稳定性。  

2. **卖出成交价口径**（见 `research.md`）  
   - 止损：收盘价触发 **`≤ 买入×(1−6%)`** 时，卖出价 **固定** `买入×0.94`（与主策略 8% 止损固定价写法一致）。  
   - 止盈：收盘价 **`≥ 买入×(1+8%)`** 时，卖出价为**当日收盘价**（实际收益率 ≥8%）。  

3. **`extra` 字段**  
   - 保留与主策略类似的可追溯字段（三日日期、`cum_hist_high`、`yang_close_to_cum_hist_high_ratio` 等）；增加 `max_close_to_cum_hist_high_ratio: 0.8`、`buy_rule: t_plus_one_open`、`sell_rule: fixed_tp_8pct_sl_6pct`、`exit_reason` 枚举新值。  

4. **选股结果落库**  
   - 沿用 `execute_strategy` 既有写入路径（与早晨十字星相同表/实体）；仅 `strategy_id` 区分。  

5. **前端路由**  
   - 建议 `route_path`: `/strategy/zao-chen-shi-zi-xing-jian-hua`，菜单置于「早晨十字星」邻近。

## 项目结构

### 本功能文档

```text
specs/026-早晨十字星简化版/
├── plan.md              # 本文件
├── research.md          # Phase 0 调研结论
├── data-model.md        # Phase 1 数据模型
├── quickstart.md        # Phase 1 本地验证
├── contracts/
│   └── strategy-api.md  # Phase 1 接口契约（增量）
└── tasks.md             # 由 /speckit.tasks 生成
```

### 源码结构（预期改动）

```text
backend/app/services/strategy/
├── registry.py                          # 注册 ZaoChenShiZiXingJianHuaStrategy
├── strategy_descriptions.py             # 可选：集中文案
└── strategies/
    └── zao_chen_shi_zi_xing_jian_hua.py # 新策略 + run_*_backtest

backend/app/core/scheduler.py            # 新增 17:23 Job

frontend/src/
├── router/index.ts（或等价）             # 路由
├── views/Layout.vue                     # 侧栏菜单
└── views/ZaoChenShiZiXingJianHuaView.vue # 新选股页（可复制早晨十字星视图改文案）
```

**结构说明**: 与「市盈率早晨十字星」「低位连阳」等内置策略一致：**策略类单文件 + 注册表 + 选股视图 + 定时任务**。

## 复杂度与例外

无需额外复杂度豁免；未引入新中间件或新存储。
