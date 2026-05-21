#!/usr/bin/env python3
"""
Issue #42 · source_type 与表名重构为 article-* 通用语义

迁移内容：
  1. bbc_eaw_episodes 表重命名为 article_episodes
  2. article_episodes 新增 series 列（default 'bbc_eaw'）
  3. vocabulary 新增 series 列
  4. vocabulary 中 source_type='bbc_eaw' → 'article'，series 回填 'bbc_eaw'

用法：
  python3 scripts/migrate_article_refactor.py
  SPEAKEASY_DB_PATH=./speakeasy.db python3 scripts/migrate_article_refactor.py

幂等：每步操作前检查当前状态，已完成则跳过。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text
from app.models.db import engine


def _table_exists(name: str) -> bool:
    return name in inspect(engine).get_table_names()


def _column_exists(table: str, column: str) -> bool:
    if not _table_exists(table):
        return False
    return column in {c["name"] for c in inspect(engine).get_columns(table)}


def rename_episodes_table() -> str:
    """bbc_eaw_episodes → article_episodes"""
    if _table_exists("article_episodes"):
        return "article_episodes 已存在，跳过"
    if not _table_exists("bbc_eaw_episodes"):
        return "bbc_eaw_episodes 不存在，跳过（可能是全新库）"
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE bbc_eaw_episodes RENAME TO article_episodes"))
    return "bbc_eaw_episodes → article_episodes 完成"


def add_episodes_series_column() -> str:
    """article_episodes 新增 series 列"""
    if not _table_exists("article_episodes"):
        return "article_episodes 不存在，跳过"
    if _column_exists("article_episodes", "series"):
        return "article_episodes.series 已存在，跳过"
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE article_episodes ADD COLUMN series TEXT NOT NULL DEFAULT 'bbc_eaw'"
        ))
    return "article_episodes.series 列新增完成"


def add_vocab_series_column() -> str:
    """vocabulary 新增 series 列"""
    if not _table_exists("vocabulary"):
        return "vocabulary 不存在，跳过"
    if _column_exists("vocabulary", "series"):
        return "vocabulary.series 已存在，跳过"
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE vocabulary ADD COLUMN series TEXT"))
    return "vocabulary.series 列新增完成"


def migrate_vocab_source_type() -> str:
    """vocabulary.source_type='bbc_eaw' → 'article' + series='bbc_eaw'"""
    if not _table_exists("vocabulary"):
        return "vocabulary 不存在，跳过"
    with engine.begin() as conn:
        result = conn.execute(text(
            "UPDATE vocabulary SET source_type='article', series='bbc_eaw' "
            "WHERE source_type='bbc_eaw'"
        ))
        count = result.rowcount
    if count == 0:
        return "无 source_type='bbc_eaw' 记录需迁移"
    return f"已迁移 {count} 条 vocabulary 记录：bbc_eaw → article + series=bbc_eaw"


def main() -> None:
    print(f"🗄  数据库: {engine.url}")
    print()

    steps = [
        ("1. 重命名 episodes 表", rename_episodes_table),
        ("2. episodes 加 series 列", add_episodes_series_column),
        ("3. vocabulary 加 series 列", add_vocab_series_column),
        ("4. vocabulary source_type 迁移", migrate_vocab_source_type),
    ]

    for label, fn in steps:
        result = fn()
        print(f"  {label}: {result}")

    print()
    print("✅ 迁移完成")


if __name__ == "__main__":
    main()
