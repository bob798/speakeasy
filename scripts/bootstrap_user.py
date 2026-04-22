#!/usr/bin/env python3
"""
创建用户 + 把历史 default_user 的数据归到该用户下。

用法：
  python scripts/bootstrap_user.py \
    --user-id bob \
    --email bob@example.com \
    --password 'my-strong-pass' \
    --from-user-id default_user \
    [--dry-run]

参数说明：
  --user-id        新用户的稳定 ID（会写入其他表的 user_id 字段），建议简短如 bob
  --email          登录邮箱
  --password       密码（至少 8 位）
  --display-name   可选昵称
  --from-user-id   要迁移的历史 user_id；默认 default_user；传 '' 跳过迁移
  --dry-run        只打印将执行的 SQL，不实际写入

注意：脚本直接操作 SPEAKEASY_DB_PATH 指向的 DB（默认 ./speakeasy.db）。
在 VPS 上请先备份：cp speakeasy.db speakeasy.db.bak
"""
import argparse
import os
import sys
from pathlib import Path

# 允许作为脚本直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, User, Base  # type: ignore
from app.services.auth_service import (  # type: ignore
    register_user,
    get_user_by_id,
)

# 需要更新 user_id 的表（按 user_id 列直接改）
USER_ID_TABLES = [
    "sessions",
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
    p.add_argument("--user-id", required=True, help="新用户稳定 ID")
    p.add_argument("--email", required=True, help="登录邮箱")
    p.add_argument("--password", required=True, help="密码（至少 8 位）")
    p.add_argument("--display-name", default=None, help="昵称（可选）")
    p.add_argument("--from-user-id", default="default_user",
                   help="要迁移的历史 user_id（默认 default_user，传空字符串跳过）")
    p.add_argument("--dry-run", action="store_true", help="只打印，不执行")
    return p.parse_args()


def main():
    args = parse_args()
    db_path = os.environ.get("SPEAKEASY_DB_PATH", "./speakeasy.db")
    print(f"Using DB: {db_path}")

    # 确保表结构存在
    Base.metadata.create_all(engine)

    existing = get_user_by_id(args.user_id)
    if existing:
        print(f"✅ 用户已存在：{existing}")
    else:
        if args.dry_run:
            print(f"[dry-run] 会创建用户 id={args.user_id} email={args.email}")
        else:
            user = register_user(
                email=args.email,
                password=args.password,
                display_name=args.display_name,
                user_id=args.user_id,
            )
            print(f"✅ 用户已创建：{user}")

    if not args.from_user_id:
        print("未指定 --from-user-id，跳过数据迁移")
        return

    from_uid = args.from_user_id
    to_uid = args.user_id

    if from_uid == to_uid:
        print("⚠️  from-user-id 与 user-id 相同，跳过数据迁移")
        return

    with OrmSession(engine) as s:
        print(f"\n将把 user_id='{from_uid}' 的数据全部改为 user_id='{to_uid}'")
        total = 0
        for tbl in USER_ID_TABLES:
            try:
                res = s.execute(
                    f"SELECT COUNT(*) FROM {tbl} WHERE user_id = :uid",
                    {"uid": from_uid},
                ).scalar() if False else None
            except Exception:
                pass
            # 使用参数化 SQL
            from sqlalchemy import text as _t
            count = s.execute(
                _t(f"SELECT COUNT(*) FROM {tbl} WHERE user_id = :uid"),
                {"uid": from_uid},
            ).scalar() or 0
            if count:
                print(f"  {tbl:25s} {count:5d} 行待迁移")
                total += count
                if not args.dry_run:
                    s.execute(
                        _t(f"UPDATE {tbl} SET user_id = :new WHERE user_id = :old"),
                        {"new": to_uid, "old": from_uid},
                    )
        if args.dry_run:
            print(f"\n[dry-run] 共 {total} 行将被迁移")
        else:
            s.commit()
            print(f"\n✅ 已迁移 {total} 行")


if __name__ == "__main__":
    main()
