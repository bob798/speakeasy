#!/usr/bin/env python3
"""
V0.10 · 生词本接入 FSRS + 文章级 SRS 迁移。

新增列（vocabulary）：
  - item_type        TEXT  default 'sentence'
  - source_type      TEXT  default 'translate'
  - source_ref       TEXT  null
  - explanation_json TEXT  null
  - fsrs_card_data   TEXT  default ''
  - last_reviewed_at TIMESTAMP null

新增唯一索引（vocabulary）：
  - uq_vocab_user_text_ref  (user_id, source_text, source_ref)

新增表：
  - bbc_article_cards
  - bbc_article_questions

用法：
  python3 scripts/migrate_v0_10_vocab_srs.py
  SPEAKEASY_DB_PATH=./speakeasy.db python3 scripts/migrate_v0_10_vocab_srs.py

幂等：列/索引/表已存在则跳过。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text
from app.models.db import engine, Base, BbcArticleCard, BbcArticleQuestion  # noqa: F401


VOCAB_NEW_COLUMNS = [
    ("item_type",        "TEXT NOT NULL DEFAULT 'sentence'"),
    ("source_type",      "TEXT NOT NULL DEFAULT 'translate'"),
    ("source_ref",       "TEXT"),
    ("explanation_json", "TEXT"),
    ("fsrs_card_data",   "TEXT NOT NULL DEFAULT ''"),
    ("last_reviewed_at", "TIMESTAMP"),
]


def existing_columns(table: str) -> set[str]:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def add_columns_if_missing() -> list[str]:
    have = existing_columns("vocabulary")
    if not have:
        print("ℹ️  vocabulary 表不存在 · 跳过 ALTER（create_all 会建好新表）")
        return []
    added = []
    with engine.begin() as conn:
        for name, ddl in VOCAB_NEW_COLUMNS:
            if name in have:
                continue
            conn.execute(text(f"ALTER TABLE vocabulary ADD COLUMN {name} {ddl}"))
            added.append(name)
    return added


def create_unique_index() -> bool:
    insp = inspect(engine)
    if "vocabulary" not in insp.get_table_names():
        return False
    indexes = {idx["name"] for idx in insp.get_indexes("vocabulary")}
    if "uq_vocab_user_text_ref" in indexes:
        return False
    with engine.begin() as conn:
        # source_ref 可为 NULL，SQLite 多个 NULL 不冲突，刚好满足"无来源不去重"
        conn.execute(
            text(
                "CREATE UNIQUE INDEX uq_vocab_user_text_ref "
                "ON vocabulary (user_id, source_text, source_ref)"
            )
        )
    return True


def create_new_tables() -> list[str]:
    before = set(inspect(engine).get_table_names())
    Base.metadata.create_all(engine)
    after = set(inspect(engine).get_table_names())
    return sorted(after - before)


def main() -> None:
    print(f"🗄  使用数据库: {engine.url}")
    added_cols = add_columns_if_missing()
    if added_cols:
        print(f"✅ vocabulary 新增列: {added_cols}")
    else:
        print("ℹ️  vocabulary 列已齐全")

    if create_unique_index():
        print("✅ 创建唯一索引: uq_vocab_user_text_ref")
    else:
        print("ℹ️  唯一索引已存在或跳过")

    new_tables = create_new_tables()
    if new_tables:
        print(f"✅ 新建表: {new_tables}")
    else:
        print("ℹ️  bbc_article_* 表已存在")


if __name__ == "__main__":
    main()
