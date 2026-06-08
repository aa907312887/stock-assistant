#!/usr/bin/env python3
"""执行数据库迁移脚本（paper_trading + manual_trading）。"""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text

from app.database import engine
from app.config import settings


def _load_statements(sql_file: Path) -> list[str]:
    content = sql_file.read_text(encoding="utf-8")
    lines = [ln for ln in content.splitlines() if not ln.strip().startswith("--")]
    body = "\n".join(lines)
    return [s.strip() for s in body.split(";") if s.strip()]


def run_sql_file(sql_file: Path) -> bool:
    if not sql_file.exists():
        print(f"❌ SQL 文件不存在: {sql_file}")
        return False
    statements = _load_statements(sql_file)
    try:
        with engine.connect() as conn:
            for stmt in statements:
                preview = stmt.split("(")[0].replace("CREATE TABLE IF NOT EXISTS", "").strip().strip("`")
                print(f"执行: {preview} ...")
                conn.execute(text(stmt))
            conn.commit()
        print(f"✅ {sql_file.name} 迁移成功")
        return True
    except Exception as e:
        print(f"❌ {sql_file.name} 迁移失败: {e}")
        return False


def run_migration() -> bool:
    scripts_dir = Path(__file__).resolve().parent
    ok = True
    for name in ("add_paper_trading_tables.sql", "add_manual_trading_tables.sql"):
        sql_file = scripts_dir / name
        if sql_file.exists():
            ok = run_sql_file(sql_file) and ok
    return ok


if __name__ == "__main__":
    print(f"数据库连接: {settings.database_url}")
    success = run_migration()
    sys.exit(0 if success else 1)
