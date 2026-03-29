# 接口契约：智能回测 API

**日期**: 2026-03-26（2026-03-29 修订：`report.portfolio_capital`、总收益率资金口径）| **路由前缀**: `/api/backtest`

所有接口挂载在 `backend/app/api/backtest.py` 路由模块下，通过 `app/main.py` 注册。

---

## 1. 发起回测

**`POST /api/backtest/run`**

用户选择策略与时间范围后发起回测。后台异步执行，接口立即返回 202。

### 请求

```json
{
  "strategy_id": "chong_gao_hui_luo",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "position_amount": 100000,
  "reserve_amount": 100000
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `strategy_id` | string | 是 | 策略标识（如 `chong_gao_hui_luo`、`panic_pullback`、`shu_guang_chu_xian`） |
| `start_date` | string (YYYY-MM-DD) | 是 | 回测起始日期 |
| `end_date` | string (YYYY-MM-DD) | 是 | 回测结束日期 |
| `position_amount` | number | 否 | 持仓金额（元），默认 `100000`；每笔固定名义本金，初始可操作现金等于该值；须 > 0 |
| `reserve_amount` | number | 否 | 补仓金额（元），默认 `100000`；预备资金池初始额度，本金不足持仓额时从此池划入，用尽则不再补仓；可填 `0` |

### 响应（202 Accepted）

```json
{
  "task_id": "bt-chong_gao_hui_luo-20240101-20241231-a1b2c3",
  "status": "running",
  "message": "回测任务已创建，后台执行中"
}
```

### 错误

| 状态码 | code | 场景 |
|--------|------|------|
| 400 | `INVALID_PARAMS` | 日期格式错误、start_date > end_date |
| 400 | `DATE_OUT_OF_RANGE` | 日期超出数据库可用范围 |
| 404 | `STRATEGY_NOT_FOUND` | strategy_id 不存在 |

---

## 2. 回测任务列表

**`GET /api/backtest/tasks`**

查询所有回测任务（按创建时间倒序），支持分页。

### 请求参数（Query）

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `strategy_id` | string | 否 | - | 按策略筛选 |
| `page` | int | 否 | 1 | 页码 |
| `page_size` | int | 否 | 20 | 每页条数（最大 100） |

### 响应（200）

```json
{
  "total": 15,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "task_id": "bt-chong_gao_hui_luo-20240101-20241231-a1b2c3",
      "strategy_id": "chong_gao_hui_luo",
      "strategy_name": "冲高回落战法",
      "strategy_version": "v1.1.3",
      "start_date": "2024-01-01",
      "end_date": "2024-12-31",
      "status": "completed",
      "total_trades": 87,
      "win_rate": 0.4253,
      "total_return": 0.1523,
      "created_at": "2026-03-26T14:30:00",
      "finished_at": "2026-03-26T14:33:42"
    }
  ]
}
```

---

## 3. 回测任务详情（含绩效报告）

**`GET /api/backtest/tasks/{task_id}`**

获取某次回测的完整绩效报告。

### 响应（200）

```json
{
  "task_id": "bt-chong_gao_hui_luo-20240101-20241231-a1b2c3",
  "strategy_id": "chong_gao_hui_luo",
  "strategy_name": "冲高回落战法",
  "strategy_version": "v1.1.3",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "status": "completed",
  "report": {
    "total_trades": 87,
    "win_trades": 37,
    "lose_trades": 50,
    "win_rate": 0.4253,
    "total_return": 0.1523,
    "avg_return": 0.0018,
    "max_win": 0.0856,
    "max_loss": -0.0632,
    "unclosed_count": 0,
    "skipped_count": 3,
    "conclusion": "该策略在 2024-01-01 至 2024-12-31 期间总体盈利 15.23%",
    "temp_level_stats": [
      {
        "level": "冰点",
        "total": 12,
        "wins": 8,
        "win_rate": 0.6667,
        "avg_return": 0.0234
      },
      {
        "level": "低温",
        "total": 25,
        "wins": 10,
        "win_rate": 0.4000,
        "avg_return": 0.0012
      },
      {
        "level": "温和",
        "total": 30,
        "wins": 12,
        "win_rate": 0.4000,
        "avg_return": 0.0005
      },
      {
        "level": "高温",
        "total": 15,
        "wins": 5,
        "win_rate": 0.3333,
        "avg_return": -0.0089
      },
      {
        "level": "沸腾",
        "total": 5,
        "wins": 2,
        "win_rate": 0.4000,
        "avg_return": -0.0045
      }
    ],
    "exchange_stats": [
      {
        "name": "SSE",
        "total": 45,
        "wins": 24,
        "win_rate": 0.5333,
        "avg_return": 0.0031
      }
    ],
    "market_stats": [
      {
        "name": "主板",
        "total": 40,
        "wins": 20,
        "win_rate": 0.5000,
        "avg_return": 0.0022
      }
    ],
    "portfolio_capital": {
      "position_size": 100000,
      "initial_principal": 100000,
      "initial_reserve": 100000,
      "final_principal": 108200,
      "final_reserve": 100000,
      "total_wealth_end": 208200,
      "total_profit": 8200,
      "total_return_on_initial_total": 0.041,
      "strategy_raw_closed_count": 120,
      "executed_closed_count": 87,
      "skipped_closed_count": 33,
      "same_day_not_traded_count": 12,
      "description": "单仓位 10 万：同日仅一笔；卖出日后方可再买入；本金不足时由预备池补足至 10 万后再开仓"
    }
  },
  "assumptions": {
    "price_type": "日线开盘价/收盘价",
    "data_source": "tushare",
    "fee_model": "无手续费",
    "position_model": "单仓位 10 万：同一买入日仅成交一笔；卖出日后方可再开仓；本金不足时由预备金池（初始 10 万）补足后再开仓"
  },
  "created_at": "2026-03-26T14:30:00",
  "finished_at": "2026-03-26T14:33:42"
}
```

### 错误

| 状态码 | code | 场景 |
|--------|------|------|
| 404 | `TASK_NOT_FOUND` | task_id 不存在 |

---

## 4. 回测交易明细

**`GET /api/backtest/tasks/{task_id}/trades`**

获取某次回测的交易明细列表，支持分页与筛选。

### 请求参数（Query）

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `trade_type` | string | 否 | - | 筛选交易类型：`closed`（已成交平仓）/ `not_traded`（选中未交易）/ `unclosed`（未平仓）；不传则返回全部 |
| `market_temp_level` | string | 否 | - | **兼容**：单个大盘温度级别 |
| `market` | string | 否 | - | **兼容**：单个板块 |
| `exchange` | string | 否 | - | **兼容**：单个交易所 |
| `market_temp_levels` | string | 否 | - | 多选温度，**逗号分隔** |
| `markets` | string | 否 | - | 多选板块，逗号分隔；空板块用 **`__EMPTY__`**（对应 DB 中 `market` 为空） |
| `exchanges` | string | 否 | - | 多选交易所，逗号分隔（如 `SSE,SZSE`） |
| `year` | int | 否 | - | 按**买入日**自然年筛选（1990–2100） |
| `page` | int | 否 | 1 | 页码 |
| `page_size` | int | 否 | 50 | 每页条数（最大 200） |

### 响应（200）

```json
{
  "total": 87,
  "page": 1,
  "page_size": 50,
  "items": [
    {
      "stock_code": "000001.SZ",
      "stock_name": "平安银行",
      "buy_date": "2024-03-15",
      "buy_price": 10.52,
      "sell_date": "2024-03-18",
      "sell_price": 10.78,
      "return_rate": 0.0247,
      "trade_type": "closed",
      "exchange": "SZSE",
      "market": "主板",
      "market_temp_score": 35.20,
      "market_temp_level": "低温",
      "extra": {
        "trigger_date": "2024-03-14",
        "surge_pct": 0.1123,
        "pullback_pct": 0.0356
      }
    },
    {
      "stock_code": "600519.SH",
      "stock_name": "贵州茅台",
      "buy_date": "2024-12-28",
      "buy_price": 1580.00,
      "sell_date": null,
      "sell_price": null,
      "return_rate": null,
      "trade_type": "unclosed",
      "exchange": "SSE",
      "market": "主板",
      "market_temp_score": 62.50,
      "market_temp_level": "温和",
      "extra": {
        "trigger_date": "2024-12-27"
      }
    }
  ]
}
```

### 错误

| 状态码 | code | 场景 |
|--------|------|------|
| 404 | `TASK_NOT_FOUND` | task_id 不存在 |

---

## 5. 筛选后复算指标

**`GET /api/backtest/tasks/{task_id}/filtered-report`**

在**不重新执行回测**的前提下，按与交易明细相同的筛选条件，对已落库明细复算胜率、总收益率等。

### 请求参数（Query）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `market_temp_levels` | string | 否 | 逗号分隔 |
| `markets` | string | 否 | 逗号分隔；`__EMPTY__` 表示空板块 |
| `exchanges` | string | 否 | 逗号分隔 |
| `year` | int | 否 | 买入自然年 |

### 响应（200）

- `filters`：回显生效条件（含 `year` 字段，可能为 `null`）
- `metrics`：`total_trades`（已平仓）、`win_trades`、`lose_trades`、`win_rate`、`total_return`、`avg_return`、`max_win`、`max_loss`、`unclosed_count`、`matched_count`（匹配总行数）

---

## 6. 分年度分析

**`GET /api/backtest/tasks/{task_id}/yearly-analysis`**

按**买入日自然年**聚合；筛选条件与 `filtered-report` / `trades` 一致（温度、交易所、板块、`year` 均为 AND）。

### 请求参数（Query）

同第 5 节（`market_temp_levels`、`markets`、`exchanges`、`year`）。

### 响应（200）

- `filters`：回显
- `items[]`：`year`、`matched_count`、`total_trades`（已平仓）、`win_trades`、`lose_trades`、`win_rate`、`total_return`、`avg_return`

未指定 `year` 时返回任务内所有出现年份各一行；指定 `year` 时通常仅一行。

---

## 7. 最佳筛选组合（胜率 / 总收益）

**`GET /api/backtest/tasks/{task_id}/best-options`**

枚举「温度 × 交易所 × 板块」各自「不限或单值（含 `__EMPTY__`）」的组合，在内存中计算：

- `best_win_rate`：胜率最高；要求该组合**已平仓笔数** ≥ 任务**总已平仓笔数**的 **⌈N/10⌉**（至少 1）。若无任何组合满足，**回退**为全量不限条件的结果。
- `best_total_return`：总收益率最高（无上述样本量门槛）。

每项含 `filters` 与 `metrics`（结构同 `filtered-report` 的 `metrics`）。

---

## 8. 可用数据范围

**`GET /api/backtest/data-range`**

获取数据库中日线数据的最早与最晚日期，供前端回测日期选择器约束范围。

### 响应（200）

```json
{
  "min_date": "2023-01-03",
  "max_date": "2026-03-25"
}
```

---

## 通用错误格式

所有错误响应统一格式：

```json
{
  "detail": {
    "code": "ERROR_CODE",
    "message": "中文错误描述"
  }
}
```
