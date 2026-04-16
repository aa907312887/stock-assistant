-- 前复权迁移：清空约定表行数据，不删表结构。
-- 执行前：全库备份；在维护窗口执行；执行后按 migration-runbook 回灌。
-- MySQL：如存在外键可暂时关闭检查。

SET FOREIGN_KEY_CHECKS = 0;

-- 策略与同步审计（先清依赖旧行情的输出）
TRUNCATE TABLE strategy_signal_event;
TRUNCATE TABLE strategy_selection_item;
TRUNCATE TABLE strategy_execution_snapshot;
TRUNCATE TABLE sync_task;
TRUNCATE TABLE sync_job_run;

-- 大盘温度与指数副本
TRUNCATE TABLE market_temperature_factor_daily;
TRUNCATE TABLE market_temperature_daily;
TRUNCATE TABLE market_index_daily_quote;

-- 行情与股票主档（历史累计高低在 stock_daily_bar.cum_hist_*，清空后须重跑极值任务）
TRUNCATE TABLE stock_daily_bar;
TRUNCATE TABLE stock_adj_factor;
TRUNCATE TABLE stock_weekly_bar;
TRUNCATE TABLE stock_monthly_bar;
TRUNCATE TABLE stock_basic;

-- 说明：user / investment_logic / backtest_* / stock_financial_report 等默认不在此脚本清空，见 data-model.md

SET FOREIGN_KEY_CHECKS = 1;
