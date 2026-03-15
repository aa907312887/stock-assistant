-- ============================================================
-- 股票分析助手 - 建库与建表脚本
-- 使用方式：mysql -u root -p < scripts/init.sql
-- 或在客户端中 source /path/to/scripts/init.sql
-- ============================================================

-- 建库
CREATE DATABASE IF NOT EXISTS stock_assistant
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE stock_assistant;

-- ----------------------------------------
-- 1. 用户表
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS user (
  id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  username      VARCHAR(64)  NOT NULL COMMENT '登录用户名',
  password_hash VARCHAR(255) DEFAULT NULL COMMENT '密码哈希，仅用户名登录可空',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ----------------------------------------
-- 2. 用户持仓表
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS user_position (
  id            BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id       BIGINT        NOT NULL COMMENT '用户ID',
  stock_code    VARCHAR(20)   NOT NULL COMMENT '股票代码',
  stock_name    VARCHAR(100)  DEFAULT NULL COMMENT '股票名称',
  quantity      DECIMAL(20,4) NOT NULL COMMENT '持仓数量',
  cost_price    DECIMAL(12,4) DEFAULT NULL COMMENT '成本价',
  profit_amount DECIMAL(16,4) DEFAULT NULL COMMENT '当前收益额(元)',
  yield_rate    DECIMAL(10,4) DEFAULT NULL COMMENT '当前收益率(%)',
  memo          VARCHAR(500)  DEFAULT NULL COMMENT '备注',
  created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_stock (user_id, stock_code),
  KEY idx_user_id (user_id),
  CONSTRAINT fk_position_user FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户持仓表';

-- ----------------------------------------
-- 3. 用户交易明细表（买入/卖出列表）
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS user_trade (
  id         BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id    BIGINT        NOT NULL COMMENT '用户ID',
  stock_code VARCHAR(20)   NOT NULL COMMENT '股票代码',
  trade_type VARCHAR(10)   NOT NULL COMMENT '交易类型: buy/sell',
  quantity   DECIMAL(20,4) NOT NULL COMMENT '成交数量',
  price      DECIMAL(12,4) NOT NULL COMMENT '成交价格',
  trade_time DATETIME      NOT NULL COMMENT '交易时间(购买时间或卖出时间)',
  amount     DECIMAL(16,2) DEFAULT NULL COMMENT '成交金额',
  memo       VARCHAR(500)  DEFAULT NULL COMMENT '备注',
  created_at DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_user_stock_type (user_id, stock_code, trade_type),
  KEY idx_trade_time (trade_time),
  CONSTRAINT fk_trade_user FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户交易明细表';

-- ----------------------------------------
-- 4. 行业维度表（可选）
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS dict_industry (
  id         BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  code       VARCHAR(20)  NOT NULL COMMENT '行业编码',
  name       VARCHAR(100) NOT NULL COMMENT '行业名称',
  sort_order INT          DEFAULT NULL COMMENT '排序',
  PRIMARY KEY (id),
  UNIQUE KEY uk_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='行业维度表';

-- ----------------------------------------
-- 5. 股票基础表
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS stock_basic (
  id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  code          VARCHAR(20)  NOT NULL COMMENT '股票代码',
  name          VARCHAR(100) DEFAULT NULL COMMENT '股票名称',
  market        VARCHAR(20)  DEFAULT NULL COMMENT '市场',
  industry_code VARCHAR(20)  DEFAULT NULL COMMENT '行业编码',
  industry_name VARCHAR(100) DEFAULT NULL COMMENT '行业名称冗余',
  region        VARCHAR(50)  DEFAULT NULL COMMENT '地区',
  list_date     DATE         DEFAULT NULL COMMENT '上市日期',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_code (code),
  KEY idx_market (market),
  KEY idx_industry_code (industry_code),
  KEY idx_list_date (list_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票基础表';

-- ----------------------------------------
-- 6. 股票-概念关联表（可选）
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS stock_concept (
  id           BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  stock_code   VARCHAR(20)   NOT NULL COMMENT '股票代码',
  concept_code VARCHAR(50)   DEFAULT NULL COMMENT '概念编码',
  concept_name VARCHAR(100)  DEFAULT NULL COMMENT '概念名称',
  PRIMARY KEY (id),
  KEY idx_stock_code (stock_code),
  KEY idx_concept_name (concept_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票-概念关联表';

-- ----------------------------------------
-- 7. 股票-风格关联表（可选）
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS stock_style (
  id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  stock_code  VARCHAR(20)  NOT NULL COMMENT '股票代码',
  style_code  VARCHAR(50)  DEFAULT NULL COMMENT '风格编码',
  style_name  VARCHAR(100) DEFAULT NULL COMMENT '风格名称',
  PRIMARY KEY (id),
  KEY idx_stock_code (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票-风格关联表';

-- ----------------------------------------
-- 8. 指数成份表（可选）
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS stock_index_member (
  id          BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  index_code  VARCHAR(20)    NOT NULL COMMENT '指数代码',
  index_name  VARCHAR(100)   DEFAULT NULL COMMENT '指数名称',
  stock_code  VARCHAR(20)    NOT NULL COMMENT '成份股代码',
  weight      DECIMAL(10,4)  DEFAULT NULL COMMENT '权重',
  PRIMARY KEY (id),
  KEY idx_index_code (index_code),
  KEY idx_stock_code (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='指数成份表';

-- ----------------------------------------
-- 9. 股票日行情表
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS stock_daily_quote (
  id               BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  stock_code       VARCHAR(20)    NOT NULL COMMENT '股票代码',
  trade_date       DATE           NOT NULL COMMENT '交易日期',
  open             DECIMAL(12,4)  DEFAULT NULL COMMENT '开盘价',
  close            DECIMAL(12,4)  DEFAULT NULL COMMENT '收盘价',
  high             DECIMAL(12,4)  DEFAULT NULL COMMENT '最高价',
  low              DECIMAL(12,4)  DEFAULT NULL COMMENT '最低价',
  prev_close       DECIMAL(12,4)  DEFAULT NULL COMMENT '前收盘价',
  change_amount    DECIMAL(12,4)  DEFAULT NULL COMMENT '涨跌额',
  pct_change       DECIMAL(10,4)  DEFAULT NULL COMMENT '涨跌幅%',
  volume           DECIMAL(20,2)  DEFAULT NULL COMMENT '成交量',
  amount           DECIMAL(20,2)  DEFAULT NULL COMMENT '成交额',
  amplitude        DECIMAL(10,4)  DEFAULT NULL COMMENT '振幅%',
  turnover_rate    DECIMAL(10,4)  DEFAULT NULL COMMENT '换手率%',
  volume_ratio     DECIMAL(10,4)  DEFAULT NULL COMMENT '量比',
  internal_volume  DECIMAL(20,2)  DEFAULT NULL COMMENT '内盘',
  external_volume  DECIMAL(20,2)  DEFAULT NULL COMMENT '外盘',
  bid_volume       DECIMAL(20,2)  DEFAULT NULL COMMENT '委买量',
  ask_volume       DECIMAL(20,2)  DEFAULT NULL COMMENT '委卖量',
  bid_ask_ratio    DECIMAL(10,4)  DEFAULT NULL COMMENT '委比%',
  total_market_cap DECIMAL(20,2)  DEFAULT NULL COMMENT '总市值',
  float_market_cap DECIMAL(20,2)  DEFAULT NULL COMMENT '流通市值',
  created_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_stock_date (stock_code, trade_date),
  KEY idx_stock_code (stock_code),
  KEY idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票日行情表';

-- ----------------------------------------
-- 10. 股票每日技术分析表
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS stock_daily_tech (
  id            BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  stock_code    VARCHAR(20)    NOT NULL COMMENT '股票代码',
  trade_date    DATE           NOT NULL COMMENT '交易日期',
  kline_pattern VARCHAR(200)   DEFAULT NULL COMMENT 'K线形态',
  macd_dif      DECIMAL(12,6)  DEFAULT NULL COMMENT 'MACD DIF',
  macd_dea      DECIMAL(12,6)  DEFAULT NULL COMMENT 'MACD DEA',
  macd_hist     DECIMAL(12,6)  DEFAULT NULL COMMENT 'MACD柱',
  kdj_k         DECIMAL(10,4)  DEFAULT NULL COMMENT 'KDJ K',
  kdj_d         DECIMAL(10,4)  DEFAULT NULL COMMENT 'KDJ D',
  kdj_j         DECIMAL(10,4)  DEFAULT NULL COMMENT 'KDJ J',
  ma5           DECIMAL(12,4)  DEFAULT NULL COMMENT '5日均线',
  ma10          DECIMAL(12,4)  DEFAULT NULL COMMENT '10日均线',
  ma20          DECIMAL(12,4)  DEFAULT NULL COMMENT '20日均线',
  ma60          DECIMAL(12,4)  DEFAULT NULL COMMENT '60日均线',
  ma_pattern    VARCHAR(50)    DEFAULT NULL COMMENT '均线形态',
  bias5         DECIMAL(10,4)  DEFAULT NULL COMMENT '5日乖离率%',
  bias10        DECIMAL(10,4)  DEFAULT NULL COMMENT '10日乖离率%',
  bias20        DECIMAL(10,4)  DEFAULT NULL COMMENT '20日乖离率%',
  bias60        DECIMAL(10,4)  DEFAULT NULL COMMENT '60日乖离率%',
  rsi           DECIMAL(8,4)   DEFAULT NULL COMMENT 'RSI',
  rsi6          DECIMAL(8,4)   DEFAULT NULL COMMENT 'RSI(6)',
  rsi12         DECIMAL(8,4)   DEFAULT NULL COMMENT 'RSI(12)',
  volume_ma5    DECIMAL(20,2)  DEFAULT NULL COMMENT '5日量均',
  created_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_stock_date (stock_code, trade_date),
  KEY idx_stock_code (stock_code),
  KEY idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票每日技术分析表';

-- ----------------------------------------
-- 11. 股票业绩/估值表
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS stock_financial (
  id            BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  stock_code    VARCHAR(20)    NOT NULL COMMENT '股票代码',
  report_date   DATE           DEFAULT NULL COMMENT '报告期',
  pe_ttm        DECIMAL(12,4)  DEFAULT NULL COMMENT '市盈率TTM',
  pe_static     DECIMAL(12,4)  DEFAULT NULL COMMENT '市盈率静态',
  pe_dynamic    DECIMAL(12,4)  DEFAULT NULL COMMENT '市盈率动态',
  pe            DECIMAL(12,4)  DEFAULT NULL COMMENT '市盈率(通用)',
  pb            DECIMAL(12,4)  DEFAULT NULL COMMENT '市净率',
  ps            DECIMAL(12,4)  DEFAULT NULL COMMENT '市销率',
  roe           DECIMAL(10,4)  DEFAULT NULL COMMENT 'ROE%',
  gross_margin  DECIMAL(10,4)  DEFAULT NULL COMMENT '毛利率%',
  net_margin    DECIMAL(10,4)  DEFAULT NULL COMMENT '净利率%',
  revenue       DECIMAL(20,2)  DEFAULT NULL COMMENT '营收',
  net_profit    DECIMAL(20,2)  DEFAULT NULL COMMENT '净利润',
  eps           DECIMAL(12,4)  DEFAULT NULL COMMENT '每股收益',
  bps           DECIMAL(12,4)  DEFAULT NULL COMMENT '每股净资产',
  created_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_stock_report (stock_code, report_date),
  KEY idx_stock_code (stock_code),
  KEY idx_report_date (report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票业绩估值表';

-- 可选：插入一个演示用户（仅用户名登录时 password_hash 可为 NULL）
-- INSERT INTO user (username, password_hash) VALUES ('demo', NULL);
