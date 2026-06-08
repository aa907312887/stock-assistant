# 实现计划：手动模拟交易

**分支**: `main` | **日期**: 2026-06-06 | **规格**: [spec.md](./spec.md)

## 概要

在「智能回测」下新增**最后一项**子菜单「手动模拟交易」，提供**用户手填价格 + 比例跟盘**的轻量验算工具：自定义标的名称、按日买入、快捷推进（天/周/月/年）后录入收盘价，系统计算持仓名义金额与盈亏，**落盘**至 MySQL，支持结束复盘。

架构：**FastAPI REST（JWT + user_id 隔离）+ Vue 3 列表/详情页**；与 020「历史模拟交易」数据与 API **完全独立**，无 K 线、无定时任务。

---

## 技术背景

- **语言/版本**：Python 3.12，TypeScript 5.x
- **主要依赖**：FastAPI、SQLAlchemy 2.0、MySQL、`python-dateutil`；Vue 3、Vite、Element Plus、Pinia
- **存储**：MySQL 新增 2 表（`manual_trading_session`、`manual_trading_operation`）
- **测试**：pytest（后端服务层 + API）；前端手工验收
- **目标平台**：现代浏览器 + 现有后端部署
- **性能目标**：单会话操作 API P95 &lt; 500ms；列表页 &lt; 1s
- **约束**：不算股数；不计手续费；比例跟盘误差 &lt; 0.01 元
- **规模**：单用户会话数十级、单会话流水数百条

---

## 章程检查

项目 constitution 为占位模板；按仓库既有规范执行：**中文文档与注释**、Spec 驱动、范围不蔓延至 K 线/020 改造、前端页须**悬浮能力说明**。

**Phase 1 复检**：无章程冲突；未引入定时任务或额外中间件。

---

## 关键设计详述

### 数据流与接口职责

#### 会话状态机

```text
active, awaiting_reval=0  ──买入/发起推进──►  active, awaiting_reval=1
       ▲                                              │
       │                                              │ POST /reval（录收盘价）
       └──────────────────────────────────────────────┘

active, awaiting_reval=0  ──POST /end（须已有 buy）──►  ended（只读）
```

#### 比例跟盘（后端 `manual_trading_service`）

```text
买入：position_value += amount；total_invested += amount
      若 reference_price 为空 → reference_price = price

录价：若 position_value > 0 且 reference_price > 0：
        position_after = position_before × (close_price / reference_price)
        segment_pnl = position_after − position_before
      reference_price = close_price；awaiting_reval = false
```

#### 整体数据流

```text
用户操作                 前端（Vue 3）                         后端（FastAPI）
────────                ─────────────                        ──────────────
新建会话        →  POST /api/manual-trading/sessions     →  写 session（user_id）
列表/续作       →  GET  /sessions                        →  按 user_id 过滤
进入详情        →  /backtest/manual-trading/:sessionId
                →  GET  /sessions/:id + /operations

买入            →  POST /sessions/:id/buy               →  累加金额 + buy 流水
推进            →  POST /sessions/:id/advance           →  current_date += step
                                                         →  awaiting_reval=true
录价            →  POST /sessions/:id/reval             →  比例更新 + reval 流水
结束            →  POST /sessions/:id/end               →  status=ended + end 流水
删除            →  DELETE /sessions/:id                 →  级联删流水
```

#### 前后端职责

| 职责 | 后端 | 前端 |
|------|------|------|
| 比例跟盘 Decimal 计算 | ✓ | |
| awaiting_reval 门禁 | ✓ | ✓（按钮禁用） |
| user_id 隔离 | ✓ | 携带 JWT |
| 流水间隔天数、总交易时间 | ✓（列表 API 计算） | 展示 |
| 快捷推进 step 选择 | | ✓ |
| 待录价表单 | | ✓ |
| 复盘表格 | | ✓ |
| 悬浮能力说明 | | ✓ |
| 会话列表/新建/删除确认 | | ✓ |

### 定时任务与部署设计

**本功能不涉及定时任务。** 无 APScheduler 注册、无 cron、无部署时一次性拉数。

### 其他关键设计

- **路由前缀**：`/api/manual-trading`；在 `backend/app/main.py` 注册 `manual_trading_router`。
- **鉴权**：全部端点 `Depends(get_current_user)`；查询/变更须校验 `session.user_id == current_user.id`。
- **session_id**：`mt-{uuid8}`，与 020 `pt-` 区分。
- **删除**：硬删除会话 + 流水；前端 `ElMessageBox.confirm` 二次确认。
- **菜单**：`Layout.vue` 在「复利模拟」后追加「手动模拟交易」；路由 `/backtest/manual-trading`。
- **日期推进**：`dateutil.relativedelta` 处理 month/year。

---

## 项目结构

### 本功能文档

```text
specs/031-手动模拟交易/
├── spec.md
├── plan.md              # 本文件
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/api.md
└── tasks.md             # /speckit.tasks 生成
```

### 源码结构（新增/修改）

```text
backend/
├── app/
│   ├── api/manual_trading.py           # 路由
│   ├── models/manual_trading.py        # SQLAlchemy 模型
│   ├── schemas/manual_trading.py       # Pydantic
│   └── services/manual_trading_service.py
├── scripts/add_manual_trading_tables.sql
└── tests/test_manual_trading.py

frontend/
├── src/
│   ├── api/manualTrading.ts
│   ├── views/ManualTradingListView.vue      # 列表 + 新建
│   ├── views/ManualTradingSessionView.vue   # 详情操作 + 复盘
│   ├── router/index.ts                      # 2 条路由
│   └── views/Layout.vue                     # 菜单项
```

---

## 实现阶段

### 阶段一：后端数据层与核心服务（P1）

1. **`add_manual_trading_tables.sql`**：2 表 + 索引（含 `last_advance_step`）。
2. **`models/manual_trading.py`**：`ManualTradingSession`、`ManualTradingOperation`。
3. **`schemas/manual_trading.py`**：与 contracts 对齐的请求/响应模型。
4. **`services/manual_trading_service.py`**：
   - `create_session` / `list_sessions` / `get_session` / `delete_session`
   - `buy` / `advance` / `reval` / `end`
   - `list_operations`（含 `days_since_prev`、汇总）
   - 私有：`_assert_active`、`_assert_owner`、`_calc_reval`
5. **`api/manual_trading.py`**：9 个端点；注册到 `main.py`。
6. **`tests/test_manual_trading.py`**：
   - 10 万 × (1800/2000) = 9 万
   - awaiting_reval 门禁
   - 无买入不可 end
   - 用户 A 不可访问用户 B 会话

### 阶段二：前端页面（P1）

1. **`api/manualTrading.ts`**：封装 HTTP 调用。
2. **`ManualTradingListView.vue`**：
   - 会话表格（标的、模拟日、持仓、总盈亏、状态）
   - 新建对话框（标的名称、起始日期）
   - 删除、进入详情
   - 悬浮能力说明（手动价格、比例跟盘、落盘、非投资建议）
3. **`ManualTradingSessionView.vue`**（进行中）：
   - 汇总卡片：持仓金额、累计买入、总盈亏、当前模拟日、参考价
   - 买入表单（金额 + 成交价）— `awaiting_reval` 时禁用
   - 推进按钮组：+1 天 / +1 周 / +1 月 / +1 年
   - 待录价区：`awaiting_reval` 时展示收盘价输入 + 确认
   - 结束交易按钮
   - 流水表（实时 GET operations）
4. **已结束会话**：同上只读，隐藏操作按钮，突出复盘汇总。
5. **`router/index.ts`** + **`Layout.vue`** 菜单。

### 阶段三：联调与文档（P1）

1. 按 [quickstart.md](./quickstart.md) 走通 SC-001～SC-004。
2. 更新 [spec.md](./spec.md) 状态为「已实现」（实现完成后）。

---

## 复杂度与例外

无章程例外；刻意**不**复用 `paper_trading_service` 以降低耦合与口径污染。

---

## 生成工件

| 工件 | 路径 |
|------|------|
| 调研 | [research.md](./research.md) |
| 数据模型 | [data-model.md](./data-model.md) |
| API 契约 | [contracts/api.md](./contracts/api.md) |
| 快速验证 | [quickstart.md](./quickstart.md) |

**下一步**：执行 `/speckit.tasks` 生成 `tasks.md` 并按任务实现。
