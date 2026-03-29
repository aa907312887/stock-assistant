-- 回测交易明细：用户对策略决策的人工评价（主观正确率统计）
ALTER TABLE backtest_trade
  ADD COLUMN user_decision VARCHAR(16) NULL COMMENT 'excellent=优秀决策 wrong=错误决策' AFTER extra_json,
  ADD COLUMN user_decision_reason VARCHAR(2000) NULL COMMENT '评价理由' AFTER user_decision,
  ADD COLUMN user_decision_at DATETIME NULL COMMENT '评价时间' AFTER user_decision_reason;
