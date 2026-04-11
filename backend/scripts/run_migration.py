#!/usr/bin/env python3
"""
执行数据库迁移脚本
"""
import sys
from pathlib import Path

# 添加 backend 目录到 Python 路径
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.database import engine
from app.config import settings

def run_migration():
    """执行 SQL 迁移脚本"""
    sql_file = Path(__file__).resolve().parent / "add_paper_trading_tables.sql"

    if not sql_file.exists():
        print(f"❌ SQL 文件不存在: {sql_file}")
        return False

    try:
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # 分割 SQL 语句（简单处理，按 ; 分割）
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]

        with engine.connect() as conn:
            for stmt in statements:
                if stmt and not stmt.startswith('--'):
                    print(f"执行: {stmt[:60]}...")
                    conn.execute(text(stmt))
            conn.commit()

        print("✅ 数据库迁移成功！")
        return True
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        return False

if __name__ == "__main__":
    print(f"数据库连接: {settings.database_url}")
    success = run_migration()
    sys.exit(0 if success else 1)
