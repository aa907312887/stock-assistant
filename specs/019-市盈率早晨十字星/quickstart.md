# 快速上手：市盈率早晨十字星

**创建日期**: 2026-04-07

## 实现步骤

### 1. 创建策略文件

```bash
touch backend/app/services/strategy/strategies/pe_zao_chen_shi_zi_xing.py
```

### 2. 注册策略

在 [registry.py](../../../backend/app/services/strategy/registry.py) 中添加：

```python
from app.services.strategy.strategies.pe_zao_chen_shi_zi_xing import PeZaoChenShiZiXingStrategy

def list_strategies() -> list[StockStrategy]:
    return [
        ...
        ZaoChenShiZiXingStrategy(),
        PeZaoChenShiZiXingStrategy(),  # 新增，紧跟早晨十字星之后
        ...
    ]
```

### 3. 添加策略描述

在 [strategy_descriptions.py](../../../backend/app/services/strategy/strategy_descriptions.py) 中添加 `"pe_zao_chen_shi_zi_xing"` 键。

### 4. 验证

```bash
cd backend
# 检查策略是否注册成功
python -c "from app.services.strategy.registry import list_strategies; print([s.strategy_id for s in list_strategies()])"

# 运行测试
pytest tests/ -k "pe_zao_chen"
```

## 关键实现要点

1. **形态判断**：复用 `zao_chen_shi_zi_xing.py` 中的 `is_hammer_bar()` 函数和 `_run_backtest()` 核心逻辑
2. **PE 过滤**：读取 `stock_daily_bar.pe_percentile`，严格 < 10.0
3. **ROE 过滤**：查询 `stock_financial_report`，取 `report_date <= 触发日T` 的最近一期，严格 > 15.0
4. **买卖规则**：与「早晨十字星」完全一致（止损 8%，移动止盈 15%+5%）

## 数据前置检查

```sql
-- 检查 PE 百分位字段覆盖率
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN pe_percentile IS NOT NULL THEN 1 ELSE 0 END) as has_pe_pct,
    SUM(CASE WHEN pe_percentile < 10 THEN 1 ELSE 0 END) as below_10pct
FROM stock_daily_bar
WHERE trade_date = (SELECT MAX(trade_date) FROM stock_daily_bar);

-- 检查财报 ROE 数据覆盖率
SELECT COUNT(DISTINCT stock_code) as stocks_with_roe
FROM stock_financial_report
WHERE roe IS NOT NULL;
```
