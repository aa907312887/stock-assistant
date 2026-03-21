-- =========================================================
-- stock_assistant V2: 清库重建脚本
-- 用途：
-- 1) 删除旧表（包含旧版 stock_financial）
-- 2) 创建新表（含日估值/财报拆分 + 同步审计字段）
-- 3) 写入初始化数据
-- 4) 提供导入模板（UPSERT）
-- 执行：
--   mysql -u root -p < backend/scripts/reset_and_init_v2.sql
-- =========================================================

CREATE DATABASE IF NOT EXISTS stock_assistant
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE stock_assistant;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS sync_job_run;
DROP TABLE IF EXISTS stock_financial_report;
DROP TABLE IF EXISTS stock_valuation_daily;
DROP TABLE IF EXISTS stock_daily_tech;
DROP TABLE IF EXISTS stock_daily_quote;
DROP TABLE IF EXISTS stock_index_member;
DROP TABLE IF EXISTS stock_style;
DROP TABLE IF EXISTS stock_concept;
DROP TABLE IF EXISTS dict_industry;
DROP TABLE IF EXISTS stock_basic;
DROP TABLE IF EXISTS stock_financial; -- 旧版兼容删除
DROP TABLE IF EXISTS user_trade;
DROP TABLE IF EXISTS user_position;
DROP TABLE IF EXISTS user;

SET FOREIGN_KEY_CHECKS = 1;

-- ----------------------------------------
-- 1. 用户表
-- ----------------------------------------
CREATE TABLE user (
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
CREATE TABLE user_position (
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
-- 3. 用户交易明细表
-- ----------------------------------------
CREATE TABLE user_trade (
  id         BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id    BIGINT        NOT NULL COMMENT '用户ID',
  stock_code VARCHAR(20)   NOT NULL COMMENT '股票代码',
  trade_type VARCHAR(10)   NOT NULL COMMENT '交易类型: buy/sell',
  quantity   DECIMAL(20,4) NOT NULL COMMENT '成交数量',
  price      DECIMAL(12,4) NOT NULL COMMENT '成交价格',
  trade_time DATETIME      NOT NULL COMMENT '交易时间',
  amount     DECIMAL(16,2) DEFAULT NULL COMMENT '成交金额',
  memo       VARCHAR(500)  DEFAULT NULL COMMENT '备注',
  created_at DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_user_stock_type (user_id, stock_code, trade_type),
  KEY idx_trade_time (trade_time),
  CONSTRAINT fk_trade_user FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户交易明细表';

-- ----------------------------------------
-- 4. 行业维度表
-- ----------------------------------------
CREATE TABLE dict_industry (
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
CREATE TABLE stock_basic (
  id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  code          VARCHAR(20)  NOT NULL COMMENT '股票代码',
  name          VARCHAR(100) DEFAULT NULL COMMENT '股票名称',
  market        VARCHAR(20)  DEFAULT NULL COMMENT '市场',
  industry_code VARCHAR(20)  DEFAULT NULL COMMENT '行业编码',
  industry_name VARCHAR(100) DEFAULT NULL COMMENT '行业名称冗余',
  region        VARCHAR(50)  DEFAULT NULL COMMENT '地区',
  list_date     DATE         DEFAULT NULL COMMENT '上市日期',
  data_source   VARCHAR(32)  NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  sync_batch_id VARCHAR(64)  DEFAULT NULL COMMENT '同步批次',
  synced_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  extra_json    JSON         DEFAULT NULL COMMENT '扩展字段',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_code (code),
  KEY idx_market (market),
  KEY idx_industry_code (industry_code),
  KEY idx_list_date (list_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票基础表';

-- ----------------------------------------
-- 6. 股票-概念关联表
-- ----------------------------------------
CREATE TABLE stock_concept (
  id           BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  stock_code   VARCHAR(20)   NOT NULL COMMENT '股票代码',
  concept_code VARCHAR(50)   DEFAULT NULL COMMENT '概念编码',
  concept_name VARCHAR(100)  DEFAULT NULL COMMENT '概念名称',
  data_source  VARCHAR(32)   NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  sync_batch_id VARCHAR(64)  DEFAULT NULL COMMENT '同步批次',
  synced_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  PRIMARY KEY (id),
  KEY idx_stock_code (stock_code),
  KEY idx_concept_name (concept_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票-概念关联表';

-- ----------------------------------------
-- 7. 股票-风格关联表
-- ----------------------------------------
CREATE TABLE stock_style (
  id           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  stock_code   VARCHAR(20)  NOT NULL COMMENT '股票代码',
  style_code   VARCHAR(50)  DEFAULT NULL COMMENT '风格编码',
  style_name   VARCHAR(100) DEFAULT NULL COMMENT '风格名称',
  data_source  VARCHAR(32)  NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  sync_batch_id VARCHAR(64) DEFAULT NULL COMMENT '同步批次',
  synced_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  PRIMARY KEY (id),
  KEY idx_stock_code (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票-风格关联表';

-- ----------------------------------------
-- 8. 指数成份表
-- ----------------------------------------
CREATE TABLE stock_index_member (
  id           BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  index_code   VARCHAR(20)    NOT NULL COMMENT '指数代码',
  index_name   VARCHAR(100)   DEFAULT NULL COMMENT '指数名称',
  stock_code   VARCHAR(20)    NOT NULL COMMENT '成份股代码',
  weight       DECIMAL(10,4)  DEFAULT NULL COMMENT '权重',
  data_source  VARCHAR(32)    NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  sync_batch_id VARCHAR(64)   DEFAULT NULL COMMENT '同步批次',
  synced_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  PRIMARY KEY (id),
  KEY idx_index_code (index_code),
  KEY idx_stock_code (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='指数成份表';

-- ----------------------------------------
-- 9. 股票日行情表（核心：全市场日级）
-- ----------------------------------------
CREATE TABLE stock_daily_quote (
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
  data_source      VARCHAR(32)    NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  sync_batch_id    VARCHAR(64)    DEFAULT NULL COMMENT '同步批次',
  synced_at        DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  extra_json       JSON           DEFAULT NULL COMMENT '扩展字段',
  created_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_stock_date (stock_code, trade_date),
  KEY idx_stock_code (stock_code),
  KEY idx_trade_date (trade_date),
  KEY idx_trade_stock (trade_date, stock_code),
  KEY idx_trade_pct (trade_date, pct_change),
  KEY idx_trade_turnover (trade_date, turnover_rate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票日行情表';

-- ----------------------------------------
-- 10. 股票日估值表（筛选主用）
-- ----------------------------------------
CREATE TABLE stock_valuation_daily (
  id            BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  stock_code    VARCHAR(20)    NOT NULL COMMENT '股票代码',
  trade_date    DATE           NOT NULL COMMENT '交易日期',
  pe_ttm        DECIMAL(12,4)  DEFAULT NULL COMMENT '市盈率TTM',
  pe_static     DECIMAL(12,4)  DEFAULT NULL COMMENT '市盈率静态',
  pe_dynamic    DECIMAL(12,4)  DEFAULT NULL COMMENT '市盈率动态',
  pe            DECIMAL(12,4)  DEFAULT NULL COMMENT '市盈率通用',
  pb            DECIMAL(12,4)  DEFAULT NULL COMMENT '市净率',
  ps            DECIMAL(12,4)  DEFAULT NULL COMMENT '市销率',
  roe           DECIMAL(10,4)  DEFAULT NULL COMMENT 'ROE%',
  gross_margin  DECIMAL(10,4)  DEFAULT NULL COMMENT '毛利率%',
  net_margin    DECIMAL(10,4)  DEFAULT NULL COMMENT '净利率%',
  data_source   VARCHAR(32)    NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  sync_batch_id VARCHAR(64)    DEFAULT NULL COMMENT '同步批次',
  synced_at     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  extra_json    JSON           DEFAULT NULL COMMENT '扩展字段',
  created_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_stock_trade (stock_code, trade_date),
  KEY idx_trade_stock (trade_date, stock_code),
  KEY idx_trade_pe (trade_date, pe),
  KEY idx_trade_pb (trade_date, pb),
  KEY idx_trade_roe (trade_date, roe),
  KEY idx_trade_gm (trade_date, gross_margin)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票日估值表';

-- ----------------------------------------
-- 11. 股票财报历史表（跨期分析）
-- ----------------------------------------
CREATE TABLE stock_financial_report (
  id            BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  stock_code    VARCHAR(20)    NOT NULL COMMENT '股票代码',
  report_date   DATE           NOT NULL COMMENT '报告期',
  report_type   VARCHAR(16)    DEFAULT NULL COMMENT 'Q1/H1/Q3/FY',
  revenue       DECIMAL(20,2)  DEFAULT NULL COMMENT '营收',
  net_profit    DECIMAL(20,2)  DEFAULT NULL COMMENT '净利润',
  eps           DECIMAL(12,4)  DEFAULT NULL COMMENT '每股收益',
  bps           DECIMAL(12,4)  DEFAULT NULL COMMENT '每股净资产',
  roe           DECIMAL(10,4)  DEFAULT NULL COMMENT 'ROE%',
  gross_margin  DECIMAL(10,4)  DEFAULT NULL COMMENT '毛利率%',
  net_margin    DECIMAL(10,4)  DEFAULT NULL COMMENT '净利率%',
  data_source   VARCHAR(32)    NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  sync_batch_id VARCHAR(64)    DEFAULT NULL COMMENT '同步批次',
  synced_at     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  extra_json    JSON           DEFAULT NULL COMMENT '扩展字段',
  created_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_stock_report (stock_code, report_date),
  KEY idx_stock_report (stock_code, report_date),
  KEY idx_report_date (report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票财报历史表';

-- ----------------------------------------
-- 12. 股票每日技术分析表
-- ----------------------------------------
CREATE TABLE stock_daily_tech (
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
  data_source   VARCHAR(32)    NOT NULL DEFAULT 'calc' COMMENT '数据源',
  sync_batch_id VARCHAR(64)    DEFAULT NULL COMMENT '同步批次',
  synced_at     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  extra_json    JSON           DEFAULT NULL COMMENT '扩展字段',
  created_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_stock_date (stock_code, trade_date),
  KEY idx_stock_code (stock_code),
  KEY idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票每日技术分析表';

-- ----------------------------------------
-- 13. 同步任务运行日志表（审计）
-- ----------------------------------------
CREATE TABLE sync_job_run (
  id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  job_name         VARCHAR(64)  NOT NULL COMMENT '任务名，如 stock_sync_daily',
  trade_date       DATE         DEFAULT NULL COMMENT '业务日期',
  batch_id         VARCHAR(64)  NOT NULL COMMENT '批次号',
  status           VARCHAR(16)  NOT NULL COMMENT 'running/success/failed',
  started_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '开始时间',
  finished_at      DATETIME     DEFAULT NULL COMMENT '结束时间',
  stock_total      INT          DEFAULT NULL COMMENT '计划处理股票数',
  quote_rows       INT          DEFAULT 0 COMMENT '写入行情数',
  valuation_rows   INT          DEFAULT 0 COMMENT '写入估值数',
  report_rows      INT          DEFAULT 0 COMMENT '写入财报数',
  error_message    VARCHAR(1000) DEFAULT NULL COMMENT '错误摘要',
  extra_json       JSON         DEFAULT NULL COMMENT '扩展字段',
  PRIMARY KEY (id),
  UNIQUE KEY uk_batch_id (batch_id),
  KEY idx_job_date (job_name, trade_date),
  KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='同步任务运行日志';

-- =========================================================
-- 初始化数据（可按需修改）
-- =========================================================

INSERT INTO user (username, password_hash)
VALUES ('admin', NULL)
ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;

-- =========================================================
-- 导入模板语句（示例）
-- 说明：业务代码可按批次号 batch_id 执行 UPSERT
-- =========================================================

-- [模板] 股票基础批量 UPSERT
-- INSERT INTO stock_basic
--   (code, name, market, industry_code, industry_name, region, list_date, data_source, sync_batch_id, synced_at, extra_json)
-- VALUES
--   ('000001.SZ', '平安银行', 'SZ', NULL, NULL, NULL, NULL, 'tushare', '20260317_170000', NOW(), NULL)
-- ON DUPLICATE KEY UPDATE
--   name = VALUES(name),
--   market = VALUES(market),
--   industry_code = VALUES(industry_code),
--   industry_name = VALUES(industry_name),
--   region = VALUES(region),
--   list_date = VALUES(list_date),
--   data_source = VALUES(data_source),
--   sync_batch_id = VALUES(sync_batch_id),
--   synced_at = VALUES(synced_at),
--   extra_json = VALUES(extra_json),
--   updated_at = CURRENT_TIMESTAMP;

-- [模板] 日行情 UPSERT
-- INSERT INTO stock_daily_quote
--   (stock_code, trade_date, open, close, high, low, prev_close, change_amount, pct_change, volume, amount,
--    amplitude, turnover_rate, volume_ratio, internal_volume, external_volume, bid_volume, ask_volume, bid_ask_ratio,
--    total_market_cap, float_market_cap, data_source, sync_batch_id, synced_at, extra_json)
-- VALUES
--   ('000001.SZ', '2026-03-17', 12.31, 12.55, 12.60, 12.20, 12.10, 0.45, 3.7190, 12345678, 345678901.23,
--    NULL, 1.2300, NULL, NULL, NULL, NULL, NULL, NULL, 123456789012.00, 9876543210.00, 'tushare', '20260317_170000', NOW(), NULL)
-- ON DUPLICATE KEY UPDATE
--   open = VALUES(open),
--   close = VALUES(close),
--   high = VALUES(high),
--   low = VALUES(low),
--   prev_close = VALUES(prev_close),
--   change_amount = VALUES(change_amount),
--   pct_change = VALUES(pct_change),
--   volume = VALUES(volume),
--   amount = VALUES(amount),
--   amplitude = VALUES(amplitude),
--   turnover_rate = VALUES(turnover_rate),
--   volume_ratio = VALUES(volume_ratio),
--   internal_volume = VALUES(internal_volume),
--   external_volume = VALUES(external_volume),
--   bid_volume = VALUES(bid_volume),
--   ask_volume = VALUES(ask_volume),
--   bid_ask_ratio = VALUES(bid_ask_ratio),
--   total_market_cap = VALUES(total_market_cap),
--   float_market_cap = VALUES(float_market_cap),
--   data_source = VALUES(data_source),
--   sync_batch_id = VALUES(sync_batch_id),
--   synced_at = VALUES(synced_at),
--   extra_json = VALUES(extra_json),
--   updated_at = CURRENT_TIMESTAMP;

-- [模板] 日估值 UPSERT
-- INSERT INTO stock_valuation_daily
--   (stock_code, trade_date, pe_ttm, pe_static, pe_dynamic, pe, pb, ps, roe, gross_margin, net_margin, data_source, sync_batch_id, synced_at, extra_json)
-- VALUES
--   ('000001.SZ', '2026-03-17', 9.1000, 9.3000, 8.9000, 9.1000, 1.2300, NULL, 10.2000, 32.1000, 18.5000, 'tushare', '20260317_170000', NOW(), NULL)
-- ON DUPLICATE KEY UPDATE
--   pe_ttm = VALUES(pe_ttm),
--   pe_static = VALUES(pe_static),
--   pe_dynamic = VALUES(pe_dynamic),
--   pe = VALUES(pe),
--   pb = VALUES(pb),
--   ps = VALUES(ps),
--   roe = VALUES(roe),
--   gross_margin = VALUES(gross_margin),
--   net_margin = VALUES(net_margin),
--   data_source = VALUES(data_source),
--   sync_batch_id = VALUES(sync_batch_id),
--   synced_at = VALUES(synced_at),
--   extra_json = VALUES(extra_json),
--   updated_at = CURRENT_TIMESTAMP;

-- [模板] 财报 UPSERT
-- INSERT INTO stock_financial_report
--   (stock_code, report_date, report_type, revenue, net_profit, eps, bps, roe, gross_margin, net_margin, data_source, sync_batch_id, synced_at, extra_json)
-- VALUES
--   ('000001.SZ', '2025-12-31', 'FY', 100000000000.00, 30000000000.00, 3.1200, 18.4500, 12.3000, 35.2000, 22.6000, 'tushare', '20260317_170000', NOW(), NULL)
-- ON DUPLICATE KEY UPDATE
--   report_type = VALUES(report_type),
--   revenue = VALUES(revenue),
--   net_profit = VALUES(net_profit),
--   eps = VALUES(eps),
--   bps = VALUES(bps),
--   roe = VALUES(roe),
--   gross_margin = VALUES(gross_margin),
--   net_margin = VALUES(net_margin),
--   data_source = VALUES(data_source),
--   sync_batch_id = VALUES(sync_batch_id),
--   synced_at = VALUES(synced_at),
--   extra_json = VALUES(extra_json),
--   updated_at = CURRENT_TIMESTAMP;

