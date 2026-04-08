-- 历史模拟交易明细：补充买入日大盘温度，与回测分析维度对齐（specs/018-历史模拟优化）
ALTER TABLE simulation_trade
  ADD COLUMN market_temp_score DECIMAL(5, 2) NULL COMMENT '买入日大盘温度分数' AFTER market,
  ADD COLUMN market_temp_level VARCHAR(16) NULL COMMENT '买入日大盘温度级别' AFTER market_temp_score;

CREATE INDEX idx_sim_trade_temp ON simulation_trade (task_id, market_temp_level);
