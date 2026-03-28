"""管理端 Tushare 探测接口响应模型（与 specs/014-前复权数据迁移/contracts/admin-tushare-probe.md 对齐）。"""

from typing import Any

from pydantic import BaseModel, Field


class TushareProbeProBarResponse(BaseModel):
    """日线前复权 pro_bar 探测响应。"""

    ok: bool = Field(description="是否调用成功")
    ts_code: str = Field(description="证券代码")
    adj: str = Field(default="qfq", description="复权类型")
    freq: str = Field(default="D", description="周期")
    row_count: int = Field(description="返回行数")
    sample: list[dict[str, Any]] = Field(default_factory=list, description="样例行（原始字段）")
    error: str | None = Field(default=None, description="错误信息")


class TushareProbeWeekMonthAdjResponse(BaseModel):
    """周/月线 stk_week_month_adj 探测响应。"""

    ok: bool = True
    trade_date: str = Field(description="查询用的 trade_date（YYYYMMDD）")
    freq: str = Field(description="week 或 month")
    row_count: int = 0
    sample: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
