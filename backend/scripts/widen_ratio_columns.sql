-- 扩大比率类字段精度，避免极端值溢出（如 ocf_to_profit 在净利润≈0 时可达百万级）
-- 执行方式: mysql -u root -p stock_assistant < scripts/widen_ratio_columns.sql

ALTER TABLE stock_financial_report
    MODIFY COLUMN roe           DECIMAL(20, 4) NULL,
    MODIFY COLUMN roe_dt        DECIMAL(20, 4) NULL,
    MODIFY COLUMN roe_waa       DECIMAL(20, 4) NULL,
    MODIFY COLUMN roa           DECIMAL(20, 4) NULL,
    MODIFY COLUMN debt_to_assets DECIMAL(20, 4) NULL,
    MODIFY COLUMN current_ratio DECIMAL(20, 4) NULL,
    MODIFY COLUMN quick_ratio   DECIMAL(20, 4) NULL,
    MODIFY COLUMN gross_margin  DECIMAL(20, 4) NULL,
    MODIFY COLUMN net_margin    DECIMAL(20, 4) NULL,
    MODIFY COLUMN cfps          DECIMAL(20, 4) NULL,
    MODIFY COLUMN ocf_to_profit DECIMAL(20, 4) NULL;
