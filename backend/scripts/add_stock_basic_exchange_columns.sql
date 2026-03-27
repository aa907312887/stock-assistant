-- stock_basic 增加交易所/板块维度字段（与 Tushare stock_basic 对齐）
ALTER TABLE stock_basic
  ADD COLUMN exchange VARCHAR(10) NULL COMMENT '交易所：SSE/SZSE/BSE';

ALTER TABLE stock_basic
  ADD INDEX idx_stock_basic_exchange (exchange);

-- 兼容旧数据：若 exchange 为空，按 code 后缀回填
UPDATE stock_basic
SET exchange = CASE
  WHEN code LIKE '%.SH' THEN 'SSE'
  WHEN code LIKE '%.SZ' THEN 'SZSE'
  WHEN code LIKE '%.BJ' THEN 'BSE'
  ELSE exchange
END
WHERE exchange IS NULL OR exchange = '';
