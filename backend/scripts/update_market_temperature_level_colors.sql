-- 将五档温度的 visual_token 更新为十六进制颜色（与 backend 常量一致）
-- 若表已由 ensure_default_rules 自动同步，可跳过本脚本

UPDATE market_temperature_level_rule SET visual_token = '#1e3a8a' WHERE level_name = '极冷';
UPDATE market_temperature_level_rule SET visual_token = '#3b82f6' WHERE level_name = '偏冷';
UPDATE market_temperature_level_rule SET visual_token = '#9ca3af' WHERE level_name = '中性';
UPDATE market_temperature_level_rule SET visual_token = '#f59e0b' WHERE level_name = '偏热';
UPDATE market_temperature_level_rule SET visual_token = '#ef4444' WHERE level_name = '过热';
