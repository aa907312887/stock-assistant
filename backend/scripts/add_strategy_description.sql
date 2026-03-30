-- 为 backtest_task 表添加 strategy_description 字段，用于持久化存储每次回测时的策略逻辑说明
-- 执行方式: mysql -u root -p stock_assistant < add_strategy_description.sql

ALTER TABLE backtest_task
ADD COLUMN strategy_description TEXT NULL COMMENT '策略逻辑说明（回测时快照）' AFTER assumptions_json;
