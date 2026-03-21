"""投资逻辑：校验、当前条目解析。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.investment_logic_entry import InvestmentLogicEntry

# MySQL TEXT 上限（字节），应用层按 UTF-8 字节长度保守校验
_MAX_TEXT_BYTES = 65535
# extra_json.insights：重要感悟，条数与单条长度上限
_MAX_INSIGHTS = 50
_MAX_INSIGHT_BYTES = 8000


def _byte_len(s: str) -> int:
    return len(s.encode("utf-8"))


def strip_optional(s: str | None) -> str | None:
    if s is None:
        return None
    t = s.strip()
    return t if t else None


def validate_contents(
    technical: str | None,
    fundamental: str | None,
    message: str | None,
) -> tuple[str | None, str | None, str | None]:
    t, f, m = strip_optional(technical), strip_optional(fundamental), strip_optional(message)
    if not (t or f or m):
        raise ValueError("技术面、基本面、消息面至少填写一面")
    for label, val in (
        ("技术面", t),
        ("基本面", f),
        ("消息面", m),
    ):
        if val is not None and _byte_len(val) > _MAX_TEXT_BYTES:
            raise ValueError(f"{label}正文过长")
    return t, f, m


def validate_weights(wt: int, wf: int, wm: int) -> None:
    if wt + wf + wm != 100:
        raise ValueError("技术面、基本面、消息面权重之和须为 100")
    for name, v in (
        ("技术面", wt),
        ("基本面", wf),
        ("消息面", wm),
    ):
        if v < 0 or v > 100:
            raise ValueError(f"{name}权重须在 0–100 之间")


def validate_extra_json(extra: dict[str, Any] | None) -> None:
    if extra is None:
        return
    if not isinstance(extra, dict):
        raise ValueError("extra_json 须为 JSON 对象")
    if "insights" not in extra:
        return
    raw = extra["insights"]
    if raw is None:
        return
    if not isinstance(raw, list):
        raise ValueError("重要感悟（insights）须为数组")
    if len(raw) > _MAX_INSIGHTS:
        raise ValueError(f"重要感悟最多 {_MAX_INSIGHTS} 条")
    for i, item in enumerate(raw, start=1):
        if not isinstance(item, str):
            raise ValueError(f"第{i}条感悟须为字符串")
        if _byte_len(item) > _MAX_INSIGHT_BYTES:
            raise ValueError(f"第{i}条感悟过长")


def get_current_entry(db: Session, user_id: int) -> InvestmentLogicEntry | None:
    """取 updated_at 最大，并列取 id 最大。"""
    return (
        db.query(InvestmentLogicEntry)
        .filter(InvestmentLogicEntry.user_id == user_id)
        .order_by(desc(InvestmentLogicEntry.updated_at), desc(InvestmentLogicEntry.id))
        .first()
    )


def list_entries(
    db: Session,
    user_id: int,
    order: str = "created_desc",
) -> list[InvestmentLogicEntry]:
    q = db.query(InvestmentLogicEntry).filter(InvestmentLogicEntry.user_id == user_id)
    if order == "created_asc":
        q = q.order_by(InvestmentLogicEntry.created_at, InvestmentLogicEntry.id)
    else:
        q = q.order_by(desc(InvestmentLogicEntry.created_at), desc(InvestmentLogicEntry.id))
    return list(q.all())
