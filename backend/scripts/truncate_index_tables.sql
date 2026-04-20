-- 清空指数专题相关表全部数据（保留表结构）
-- 执行前请 USE 到你的业务库（如 stock_assistant）
-- 执行后请用「白名单」重新同步，例如：
--   python -m app.scripts.sync_index --preset common --mode backfill --modules basic daily --start-date 2015-01-01 --end-date 2026-04-26

SET FOREIGN_KEY_CHECKS = 0;

TRUNCATE TABLE index_weight;
TRUNCATE TABLE index_daily_bar;
TRUNCATE TABLE index_weekly_bar;
TRUNCATE TABLE index_monthly_bar;
TRUNCATE TABLE index_basic;

SET FOREIGN_KEY_CHECKS = 1;
