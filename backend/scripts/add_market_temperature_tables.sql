-- 大盘温度相关表

CREATE TABLE IF NOT EXISTS market_index_daily_quote (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  index_code VARCHAR(16) NOT NULL,
  trade_date DATE NOT NULL,
  open DECIMAL(12,4) NULL,
  high DECIMAL(12,4) NULL,
  low DECIMAL(12,4) NULL,
  close DECIMAL(12,4) NULL,
  vol DECIMAL(20,4) NULL,
  amount DECIMAL(20,4) NULL,
  source VARCHAR(32) NOT NULL DEFAULT 'tushare',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_market_index_date (index_code, trade_date),
  KEY idx_market_index_trade_date (trade_date)
);

CREATE TABLE IF NOT EXISTS market_temperature_daily (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  trade_date DATE NOT NULL,
  temperature_score DECIMAL(5,2) NOT NULL,
  temperature_level VARCHAR(16) NOT NULL,
  trend_flag VARCHAR(8) NOT NULL,
  delta_score DECIMAL(5,2) NOT NULL DEFAULT 0,
  strategy_hint VARCHAR(255) NOT NULL,
  data_status VARCHAR(16) NOT NULL DEFAULT 'normal',
  formula_version VARCHAR(32) NOT NULL DEFAULT 'v1.0.0',
  generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_temp_trade_date_version (trade_date, formula_version),
  KEY idx_temp_trade_date (trade_date)
);

CREATE TABLE IF NOT EXISTS market_temperature_factor_daily (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  trade_date DATE NOT NULL,
  trend_score DECIMAL(5,2) NOT NULL,
  liquidity_score DECIMAL(5,2) NOT NULL,
  risk_score DECIMAL(5,2) NOT NULL,
  trend_weight DECIMAL(4,2) NOT NULL DEFAULT 0.40,
  liquidity_weight DECIMAL(4,2) NOT NULL DEFAULT 0.30,
  risk_weight DECIMAL(4,2) NOT NULL DEFAULT 0.30,
  formula_version VARCHAR(32) NOT NULL DEFAULT 'v1.0.0',
  generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_factor_trade_date_version (trade_date, formula_version)
);

CREATE TABLE IF NOT EXISTS market_temperature_level_rule (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  level_name VARCHAR(16) NOT NULL,
  score_min DECIMAL(5,2) NOT NULL,
  score_max DECIMAL(5,2) NOT NULL,
  strategy_action VARCHAR(32) NOT NULL,
  strategy_hint VARCHAR(255) NOT NULL,
  visual_token VARCHAR(32) NOT NULL,
  is_active TINYINT NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_level_name (level_name)
);

CREATE TABLE IF NOT EXISTS market_temperature_copywriting (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  content_type VARCHAR(32) NOT NULL,
  level_name VARCHAR(16) NULL,
  title VARCHAR(64) NOT NULL,
  content TEXT NOT NULL,
  formula_version VARCHAR(32) NULL,
  is_active TINYINT NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
