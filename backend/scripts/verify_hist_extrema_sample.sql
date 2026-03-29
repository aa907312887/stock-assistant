-- 抽样核对：最新一根日线上的累计极值 vs 手工 MAX/MIN（全历史）
-- 将 :code 换成 ts_code，如 000001.SZ

SELECT
  d.trade_date AS 最新交易日,
  d.cum_hist_high AS 日线累计最高,
  d.cum_hist_low AS 日线累计最低,
  agg.mh AS 全表MAX_high,
  agg.ml AS 全表MIN_low
FROM stock_daily_bar d
JOIN (
  SELECT stock_code, MAX(high) AS mh, MIN(low) AS ml
  FROM stock_daily_bar
  WHERE stock_code = '000001.SZ'
) agg ON agg.stock_code = d.stock_code
WHERE d.stock_code = '000001.SZ'
ORDER BY d.trade_date DESC
LIMIT 1;
