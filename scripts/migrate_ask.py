#!/usr/bin/env python3
"""
V0.7 · 创建 ask_threads / ask_messages 表。

用法：
  python scripts/migrate_ask.py             # 直接执行
  SPEAKEASY_DB_PATH=./speakeasy.db python scripts/migrate_ask.py

说明：
  依赖 SQLAlchemy Base.metadata.create_all()，只创建不存在的表，安全可重跑。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect
from app.models.db import engine, Base, AskThread, AskMessage  # noqa: F401


def main() -> None:
    before = set(inspect(engine).get_table_names())
    Base.metadata.create_all(engine)
    after = set(inspect(engine).get_table_names())
    new_tables = sorted(after - before)
    needed = {"ask_threads", "ask_messages"}
    present = needed & after
    if new_tables:
        print(f"✅ 新建表: {new_tables}")
    elif present == needed:
        print(f"ℹ️  表已存在，跳过: {sorted(present)}")
    else:
        missing = needed - after
        raise RuntimeError(f"迁移失败，缺少表: {sorted(missing)}")


if __name__ == "__main__":
    main()
