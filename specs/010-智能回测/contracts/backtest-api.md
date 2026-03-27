# 接口契约：智能回测 API

**日期**: 2026-03-26 | **路由前缀**: `/api/backtest`

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
  "end_date": "2024-12-31"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `strategy_id` | string | 是 | 策略标识 |
| `start_date` | string (YYYY-MM-DD) | 是 | 回测起始日期 |
| `end_date` | string (YYYY-MM-DD) | 是 | 回测结束日期 |

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
    ]
  },
  "assumptions": {
    "price_type": "日线开盘价/收盘价",
    "data_source": "tushare",
    "fee_model": "无手续费",
    "position_model": "单笔独立计算"
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
| `trade_type` | string | 否 | - | 筛选交易类型：`closed` / `unclosed`；不传则返回全部 |
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

## 5. 可用数据范围

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
