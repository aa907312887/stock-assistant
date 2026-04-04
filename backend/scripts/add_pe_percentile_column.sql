-- 为 stock_daily_bar 表新增 PE 历史百分位列
-- 含义：当前 PE 在该股自 2019 年以来（不含当日）历史 PE 中的 min-max 百分位，范围 [0, 100]
-- 执行方式: mysql -u root -p stock_assistant < scripts/add_pe_percentile_column.sql

ALTER TABLE stock_daily_bar
    ADD COLUMN pe_percentile DECIMAL(6, 2) NULL
    COMMENT '当前PE在该股自2019年以来历史PE中的百分位(0-100)，仅使用严格早于当日的数据'
    AFTER cum_hist_low;
