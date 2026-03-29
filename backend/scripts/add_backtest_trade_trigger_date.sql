-- 回测交易明细：形态/信号触发日（可与买入日不同，策略可选）
ALTER TABLE backtest_trade
  ADD COLUMN trigger_date DATE NULL COMMENT '形态或信号触发日';
