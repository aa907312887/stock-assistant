-- 回测交易明细增加交易所与板块维度
ALTER TABLE backtest_trade
  ADD COLUMN exchange VARCHAR(10) NULL COMMENT '交易所：SSE/SZSE/BSE',
  ADD COLUMN market VARCHAR(20) NULL COMMENT '板块：主板/创业板/科创板/北交所';

ALTER TABLE backtest_trade
  ADD INDEX idx_bt_trade_exchange (task_id, exchange),
  ADD INDEX idx_bt_trade_market (task_id, market);
