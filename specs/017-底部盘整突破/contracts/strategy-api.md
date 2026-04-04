# 策略 API 契约：底部盘整突破

**日期**：2026-03-30  
**功能规格**：`specs/017-底部盘整突破/spec.md`

## 概述

本策略复用现有策略 API 端点，无需新增 API。以下列出涉及的接口及其与策略的对应关系。

## 复用的 API 端点

### 1. 获取策略列表

**端点**：`GET /api/strategies`  
**说明**：返回所有可用策略列表，包含底部盘整突破

**响应示例**：
```json
{
  "items": [
    {
      "strategy_id": "chong_gao_hui_luo",
      "name": "冲高回落战法",
      "version": "v1.0.0",
      "short_description": "识别盘中强势拉升但收盘从最高回落的个股",
      "route_path": "/strategy/chong-gao-hui-luo"
    },
    {
      "strategy_id": "bottom_consolidation_breakout",
      "name": "底部盘整突破",
      "version": "v1.0.0",
      "short_description": "识别低位盘整后向上突破的个股",
      "route_path": "/strategy/bottom-consolidation-breakout"
    }
  ]
}
```

### 2. 获取单个策略详情

**端点**：`GET /api/strategies/{strategy_id}`  
**说明**：返回指定策略的详细信息

**请求示例**：
```
GET /api/strategies/bottom_consolidation_breakout
```

**响应示例**：
```json
{
  "strategy_id": "bottom_consolidation_breakout",
  "name": "底部盘整突破",
  "version": "v1.0.0",
  "description": "在A股中识别处于相对低位、经历充分盘整后向上突破的个股，在突破确认后买入，通过止盈止损规则控制风险收益比。",
  "assumptions": [
    "当前股价必须在历史最高价的二分之一以下",
    "盘整持续天数必须不少于15个交易日",
    "止盈止损采用条件单模式模拟"
  ],
  "risks": [
    "盘整形态可能继续延续，突破信号可能延迟出现",
    "极端行情下止损可能无法精确以触发价成交",
    "本策略用于历史验证，不构成投资建议"
  ]
}
```

### 3. 执行策略选股

**端点**：`POST /api/strategies/{strategy_id}/execute`  
**说明**：执行策略选股，返回当日满足条件的候选股票列表

**请求示例**：
```json
POST /api/strategies/bottom_consolidation_breakout/execute
Content-Type: application/json

{
  "as_of_date": "2026-03-28"
}
```

**响应示例**：
```json
{
  "execution": {
    "execution_id": "exec-bcb-20260328-abc123",
    "strategy_id": "bottom_consolidation_breakout",
    "strategy_version": "v1.0.0",
    "market": "A股",
    "as_of_date": "2026-03-28",
    "timeframe": "daily",
    "assumptions": {
      "consolidation_days": 15,
      "consolidation_range": 0.03,
      "low_position_ratio": 0.5,
      "profit_monitor_threshold": 0.15,
      "profit_trailing_pct": 0.05,
      "stop_loss_pct": 0.03
    }
  },
  "items": [
    {
      "stock_code": "000001",
      "stock_name": "平安银行",
      "exchange": "SZSE",
      "market": "主板",
      "trigger_date": "2026-03-28",
      "summary": {
        "base_price": 10.50,
        "consolidation_days": 18,
        "breakout_price": 10.85,
        "hist_high_ratio": 0.45,
        "buy_date": "2026-03-31"
      }
    }
  ],
  "signals": [
    {
      "stock_code": "000001",
      "event_date": "2026-03-28",
      "event_type": "trigger",
      "payload": {
        "base_price": 10.50,
        "consolidation_days": 18,
        "breakout_price": 10.85,
        "deviation_pct": 3.33
      }
    }
  ]
}
```

### 4. 创建回测任务

**端点**：`POST /api/backtest/run`  
**说明**：创建回测任务，底部盘整突破策略出现在策略下拉选项中

**请求示例**：
```json
POST /api/backtest/run
Content-Type: application/json

{
  "strategy_id": "bottom_consolidation_breakout",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "holding_amount": 100000,
  "reserve_amount": 100000
}
```

**响应示例**：
```json
{
  "task_id": "bt-bottom_consolidation_breakout-20240101-20241231-xyz789",
  "strategy_id": "bottom_consolidation_breakout",
  "status": "running",
  "created_at": "2026-03-30T10:00:00Z"
}
```

### 5. 查询回测交易明细

**端点**：`GET /api/backtest/tasks/{task_id}/trades`  
**说明**：分页查询交易明细

**响应示例**：
```json
{
  "items": [
    {
      "id": 1,
      "stock_code": "000001",
      "stock_name": "平安银行",
      "buy_date": "2024-03-18",
      "buy_price": 10.52,
      "sell_date": "2024-04-05",
      "sell_price": 12.16,
      "return_rate": 0.1559,
      "trade_type": "closed",
      "exchange": "SZSE",
      "market": "主板",
      "market_temp_score": 45.0,
      "market_temp_level": "低温",
      "trigger_date": "2024-03-15",
      "extra": {
        "base_price": 10.50,
        "consolidation_days": 18,
        "stop_loss_price": 10.19,
        "highest_close": 12.80,
        "in_profit_monitor": true,
        "take_profit_trigger": 12.16,
        "exit_reason": "止盈（最高价回落5%）"
      }
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

## 错误响应

### 数据未就绪

```json
{
  "detail": "策略执行失败：数据未就绪，最新交易日数据尚未同步完成"
}
```

**HTTP 状态码**：425 Too Early

### 策略不存在

```json
{
  "detail": "策略不存在：unknown_strategy"
}
```

**HTTP 状态码**：404 Not Found

### 参数校验失败

```json
{
  "detail": "日期范围校验失败：start_date 不能晚于 end_date"
}
```

**HTTP 状态码**：422 Unprocessable Entity

## 前端集成

### 策略选股页面

- 路由：`/strategy/bottom-consolidation-breakout`
- 菜单路径：策略选股 → 底部盘整突破
- 页面内容：
  - 策略说明卡片（描述、假设、风险）
  - 执行按钮
  - 候选股票列表表格

### 回测页面

- 策略下拉框包含"底部盘整突破"选项
- 回测结果展示交易明细时，`extra.exit_reason` 显示卖出原因
