-- 综合选股相关表：与 docs/数据库设计.md 一致
-- 使用方式：mysql -u user -p stock_assistant < backend/scripts/init_stock_tables.sql
-- 或连接 MySQL 后 source 本文件

-- 3.1 股票基础表
CREATE TABLE IF NOT EXISTS stock_basic (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,
    market VARCHAR(20) NULL,
    industry_code VARCHAR(20) NULL,
    industry_name VARCHAR(100) NULL,
    region VARCHAR(50) NULL,
    list_date DATE NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_code (code),
    KEY idx_market (market),
    KEY idx_industry_code (industry_code),
    KEY idx_list_date (list_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3.6 股票日行情表
CREATE TABLE IF NOT EXISTS stock_daily_quote (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    open DECIMAL(12,4) NULL,
    close DECIMAL(12,4) NULL,
    high DECIMAL(12,4) NULL,
    low DECIMAL(12,4) NULL,
    prev_close DECIMAL(12,4) NULL,
    change_amount DECIMAL(12,4) NULL,
    pct_change DECIMAL(10,4) NULL,
    volume DECIMAL(20,2) NULL,
    amount DECIMAL(20,2) NULL,
    amplitude DECIMAL(10,4) NULL,
    turnover_rate DECIMAL(10,4) NULL,
    volume_ratio DECIMAL(10,4) NULL,
    internal_volume DECIMAL(20,2) NULL,
    external_volume DECIMAL(20,2) NULL,
    bid_volume DECIMAL(20,2) NULL,
    ask_volume DECIMAL(20,2) NULL,
    bid_ask_ratio DECIMAL(10,4) NULL,
    total_market_cap DECIMAL(20,2) NULL,
    float_market_cap DECIMAL(20,2) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_stock_date (stock_code, trade_date),
    KEY idx_stock_code (stock_code),
    KEY idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3.7 股票业绩/估值表（按报告期可存历史）
CREATE TABLE IF NOT EXISTS stock_financial (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL,
    report_date DATE NULL,
    pe_ttm DECIMAL(12,4) NULL,
    pe_static DECIMAL(12,4) NULL,
    pe_dynamic DECIMAL(12,4) NULL,
    pe DECIMAL(12,4) NULL,
    pb DECIMAL(12,4) NULL,
    ps DECIMAL(12,4) NULL,
    roe DECIMAL(10,4) NULL,
    gross_margin DECIMAL(10,4) NULL,
    net_margin DECIMAL(10,4) NULL,
    revenue DECIMAL(20,2) NULL,
    net_profit DECIMAL(20,2) NULL,
    eps DECIMAL(12,4) NULL,
    bps DECIMAL(12,4) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_stock_report (stock_code, report_date),
    KEY idx_stock_code (stock_code),
    KEY idx_report_date (report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
