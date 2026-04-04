-- 为 stock_financial_report 表新增 fina_indicator 相关字段
-- 执行方式: mysql -u <user> -p <database> < backend/scripts/add_fina_indicator_columns.sql

ALTER TABLE stock_financial_report
  ADD COLUMN ann_date DATE NULL COMMENT '公告日期' AFTER report_type,
  ADD COLUMN roe_dt DECIMAL(10,4) NULL COMMENT '净资产收益率(扣除非经常性损益)' AFTER roe,
  ADD COLUMN roe_waa DECIMAL(10,4) NULL COMMENT '加权平均净资产收益率' AFTER roe_dt,
  ADD COLUMN roa DECIMAL(10,4) NULL COMMENT '总资产报酬率' AFTER roe_waa,
  ADD COLUMN debt_to_assets DECIMAL(10,4) NULL COMMENT '资产负债率' AFTER roa,
  ADD COLUMN current_ratio DECIMAL(10,4) NULL COMMENT '流动比率' AFTER debt_to_assets,
  ADD COLUMN quick_ratio DECIMAL(10,4) NULL COMMENT '速动比率' AFTER current_ratio,
  ADD COLUMN cfps DECIMAL(12,4) NULL COMMENT '每股经营活动现金流' AFTER bps,
  ADD COLUMN ebit DECIMAL(20,2) NULL COMMENT '息税前利润' AFTER cfps,
  ADD COLUMN ocf_to_profit DECIMAL(10,4) NULL COMMENT '经营现金流/营业利润' AFTER ebit;
