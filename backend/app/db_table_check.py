"""与库结构相关的轻量检测。

指数专题等 DDL 未在目标库执行时，ORM 查询不存在的表会触发 MySQL 1146，
进而导致整页接口 500。在读取 index_* 前应先检测表是否存在。
"""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.orm import Session


def db_has_table(db: Session, table_name: str) -> bool:
    """检测当前连接库中是否存在给定物理表名。"""
    try:
        return bool(inspect(db.get_bind()).has_table(table_name))
    except Exception:
        return False
