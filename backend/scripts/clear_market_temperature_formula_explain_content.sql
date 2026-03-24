-- 大盘温度「?」长文已改由接口内嵌（formula_explain_text + rule_service）返回。
-- 若库中 formula_explain 仍残留旧版短正文，执行本脚本可避免弹层底部「补充说明」重复。
UPDATE market_temperature_copywriting
SET content = ''
WHERE content_type = 'formula_explain'
  AND formula_version = 'v1.0.0'
  AND is_active = 1;
