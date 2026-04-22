#!/usr/bin/env python3
"""
把"第二台电脑"的 speakeasy DB 合并进当前 DB。

用法：
  python scripts/merge_db.py \
    --source /path/to/second_computer.db \
    --source-user-id default_user \
    --target-user-id bob \
    [--dry-run]

策略：
  - ATTACH 源 DB 到当前连接
  - 对 USER_ID_TABLES 中每张表，把 source.user_id=source-user-id 的数据
    INSERT OR IGNORE 到当前 DB（改 user_id → target-user-id）
  - UniqueConstraint 冲突行自动跳过（保留主 DB 里已有的那条）
  - session_reviews / messages / vocabulary 这类有自增 id 的表，合并后 ID 可能冲突
    脚本会做 id 重映射：源库的 id 剥离，让目标库重新自增

注意：
  - 合并前强烈建议备份：cp speakeasy.db speakeasy.db.bak
  - 请确保 target 用户已通过 bootstrap_user.py 创建
"""
import argparse
import os
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 列出表及其主键列（INSERT OR IGNORE 时用的唯一性依据）
# 有 autoincrement id 的表：合并时要跳过源 id，让目标库重新分配
AUTO_ID_TABLES = {
    "messages",
    "grammar_cards",
    "session_reviews",
    "user_facts",
    "pronunciation_cards",
    "subtitle_sources",
    "vocabulary",
    "translation_cache",
    "explanation_cache",
}

# user_id 相关表（只合并指定 source-user-id 的行）
USER_SCOPED_TABLES = [
    "sessions",
    "messages",             # 通过 session 关联
    "grammar_cards",
    "session_reviews",
    "user_settings",
    "user_profile",
    "user_facts",
    "pronunciation_cards",
    "subtitle_sources",
    "vocabulary",
]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", required=True, help="第二台电脑的 speakeasy.db 路径")
    p.add_argument("--source-user-id", default="default_user")
    p.add_argument("--target-user-id", required=True)
    p.add_argument("--target-db", default=None, help="目标 DB 路径（默认从 SPEAKEASY_DB_PATH / ./speakeasy.db）")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def get_columns(conn: sqlite3.Connection, table: str) -> list:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [r[1] for r in rows]


def main():
    args = parse_args()
    target_db = args.target_db or os.environ.get("SPEAKEASY_DB_PATH", "./speakeasy.db")

    if not os.path.exists(args.source):
        print(f"❌ 源 DB 不存在: {args.source}")
        sys.exit(1)
    if not os.path.exists(target_db):
        print(f"❌ 目标 DB 不存在: {target_db}")
        sys.exit(1)

    if not args.dry_run:
        backup = target_db + ".prebak"
        shutil.copy2(target_db, backup)
        print(f"📦 目标 DB 已备份到: {backup}")

    conn = sqlite3.connect(target_db)
    conn.execute(f"ATTACH DATABASE '{args.source}' AS src")
    conn.row_factory = sqlite3.Row

    try:
        total_inserted = 0
        total_skipped = 0
        for tbl in USER_SCOPED_TABLES:
            try:
                cols = get_columns(conn, tbl)
            except sqlite3.DatabaseError as e:
                print(f"⚠️  跳过 {tbl}：{e}")
                continue

            # messages 表没有 user_id 字段，通过 sessions.user_id 级联（先合并 sessions 后再按 session_id 合并 messages）
            if tbl == "messages":
                # 选出属于源 user 的 session id
                sid_rows = conn.execute(
                    "SELECT id FROM src.sessions WHERE user_id = ?",
                    (args.source_user_id,),
                ).fetchall()
                if not sid_rows:
                    continue
                sids = tuple(r["id"] for r in sid_rows)
                placeholders = ",".join("?" for _ in sids)

                # 去掉自增 id
                insert_cols = [c for c in cols if c != "id"]
                select_expr = ", ".join(insert_cols)
                sql = (
                    f"INSERT OR IGNORE INTO main.messages ({select_expr}) "
                    f"SELECT {select_expr} FROM src.messages WHERE session_id IN ({placeholders})"
                )
                before = conn.execute("SELECT COUNT(*) FROM main.messages").fetchone()[0]
                if args.dry_run:
                    count = conn.execute(
                        f"SELECT COUNT(*) FROM src.messages WHERE session_id IN ({placeholders})",
                        sids,
                    ).fetchone()[0]
                    print(f"  [dry-run] messages {count} 行待插入")
                    continue
                conn.execute(sql, sids)
                after = conn.execute("SELECT COUNT(*) FROM main.messages").fetchone()[0]
                inserted = after - before
                total_inserted += inserted
                print(f"  messages {inserted:5d} 行插入")
                continue

            # 其他表：通过 user_id 过滤
            insert_cols = [c for c in cols if not (tbl in AUTO_ID_TABLES and c == "id")]
            select_expr_parts = []
            for c in insert_cols:
                if c == "user_id":
                    select_expr_parts.append(f"'{args.target_user_id.replace(chr(39), chr(39)+chr(39))}' AS user_id")
                else:
                    select_expr_parts.append(c)
            select_expr = ", ".join(select_expr_parts)
            col_list = ", ".join(insert_cols)

            if args.dry_run:
                count = conn.execute(
                    f"SELECT COUNT(*) FROM src.{tbl} WHERE user_id = ?",
                    (args.source_user_id,),
                ).fetchone()[0]
                print(f"  [dry-run] {tbl:25s} {count:5d} 行候选")
                continue

            before = conn.execute(f"SELECT COUNT(*) FROM main.{tbl}").fetchone()[0]
            conn.execute(
                f"INSERT OR IGNORE INTO main.{tbl} ({col_list}) "
                f"SELECT {select_expr} FROM src.{tbl} WHERE user_id = ?",
                (args.source_user_id,),
            )
            after = conn.execute(f"SELECT COUNT(*) FROM main.{tbl}").fetchone()[0]
            inserted = after - before
            total_inserted += inserted
            print(f"  {tbl:25s} {inserted:5d} 行插入")

        if not args.dry_run:
            conn.commit()
            print(f"\n✅ 合并完成，共插入 {total_inserted} 行（重复行已自动跳过）")
        else:
            print(f"\n[dry-run] 未执行任何写入")

    finally:
        conn.execute("DETACH DATABASE src")
        conn.close()


if __name__ == "__main__":
    main()
