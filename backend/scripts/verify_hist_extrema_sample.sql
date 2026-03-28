-- 对比 000001 的日线极值 vs stock_basic 里存的 hist（平安银行一般为 000001.SZ）
SELECT
  b.code,
  b.name,
  (SELECT MAX(d.high) FROM stock_daily_bar d WHERE d.stock_code = b.code) AS 日线最高,
  b.hist_high AS basic最高,
  (SELECT MIN(d.low) FROM stock_daily_bar d WHERE d.stock_code = b.code) AS 日线最低,
  b.hist_low AS basic最低
FROM stock_basic b
WHERE b.code LIKE '000001%'
LIMIT 1;
