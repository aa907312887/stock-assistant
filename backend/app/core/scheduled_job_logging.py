"""
定时任务失败时的统一告警日志。

要求：失败场景使用 ERROR，并清晰标明调度任务、入口函数、业务函数、外部接口（若有）与错误原因。
"""

from __future__ import annotations

import logging
import re
from typing import Any

# 与运维检索、告警规则对接时可用固定前缀
ALERT_PREFIX = "[定时任务告警]"


def log_scheduled_job_failure(
    logger: logging.Logger,
    *,
    job_id: str,
    scheduler_entry: str,
    business_callable: str,
    external_api: str | None,
    exc: BaseException,
) -> None:
    """
    记录一次定时任务失败（ERROR + 完整堆栈）。

    :param job_id: APScheduler job id，如 ``stock_sync``。
    :param scheduler_entry: 调度器调用的入口函数全名，如 ``app.core.scheduler._job_sync_stock``。
    :param business_callable: 实际执行业务的可调用对象描述，如 ``app.services.stock_sync_service.run_sync``。
    :param external_api: 已识别出的外部接口名，如 ``Tushare pro.stock_basic``；无法识别时可为 None。
    :param exc: 异常实例。
    """
    api_text = external_api if external_api else "（未能从本次异常中单独定位接口，请结合业务方法与堆栈判断）"
    logger.error(
        "%s job_id=%s | 调度入口=%s | 业务方法=%s | 外部接口=%s | 异常类型=%s | 原因=%s",
        ALERT_PREFIX,
        job_id,
        scheduler_entry,
        business_callable,
        api_text,
        type(exc).__name__,
        exc,
        exc_info=exc,
    )


def log_sync_step_failure(
    logger: logging.Logger,
    *,
    business_callable: str,
    step: str,
    external_api: str,
    exc: BaseException,
    extra: str | None = None,
) -> None:
    """
    同步链路中某一步失败（仍会被上层定时任务捕获时再打一条总告警）。

    :param step: 步骤说明，如 ``拉取股票列表``。
    :param extra: 可选附加上下文，如 ``ts_code=600000.SH``。
    """
    suffix = f" | {extra}" if extra else ""
    logger.error(
        "%s [同步步骤失败] 业务方法=%s | 步骤=%s | 外部接口=%s | 异常类型=%s | 原因=%s%s",
        ALERT_PREFIX,
        business_callable,
        step,
        external_api,
        type(exc).__name__,
        exc,
        suffix,
        exc_info=exc,
    )


def guess_tushare_api_from_exception(exc: BaseException) -> str | None:
    """从 TushareClientError 等消息的常见格式里尽量解析接口名。"""
    text = str(exc)
    m = re.search(r"Tushare\s+(\S+)\s+失败", text)
    if m:
        return f"Tushare pro.{m.group(1)}（推断自异常文案）"
    if "TUSHARE_TOKEN" in text:
        return "Tushare 初始化（token 配置）"
    return None
