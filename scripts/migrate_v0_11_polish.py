#!/usr/bin/env python3
"""
V0.11 · 新增 polish_cards 表（写作教练）

幂等：表存在则跳过。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect
from app.models.db import engine, Base, PolishCard  # noqa: F401


def main() -> None:
    print(f"🗄  使用数据库: {engine.url}")
    before = set(inspect(engine).get_table_names())
    Base.metadata.create_all(engine)
    after = set(inspect(engine).get_table_names())
    new_tables = sorted(after - before)
    if new_tables:
        print(f"✅ 新建表: {new_tables}")
    elif "polish_cards" in after:
        print("ℹ️  polish_cards 已存在")
    else:
        raise RuntimeError("polish_cards 表创建失败")


if __name__ == "__main__":
    main()
