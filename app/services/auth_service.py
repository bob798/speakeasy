"""认证服务 — bcrypt 密码哈希 + JWT 签发/校验"""

import os
import re
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

import bcrypt
import jwt
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, User
from app.logger import get_logger

logger = get_logger("auth_service")

# ── 配置 ────────────────────────────────────────────────────

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 60          # V0.9.2：14 → 60 天，避免频繁登录
_DEV_SECRET_FILE = ".jwt_secret.local"   # gitignored；dev 跨进程持久化
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def _get_jwt_secret() -> str:
    """
    读 JWT_SECRET 的优先级：
      1. 环境变量 JWT_SECRET（生产推荐）
      2. .jwt_secret.local 文件（dev 跨 uvicorn 重启持久化 · gitignored）
      3. 进程内生成随机密钥（最后兜底）
    """
    secret = os.environ.get("JWT_SECRET")
    if secret:
        return secret

    # 进程内缓存
    global _DEV_SECRET
    try:
        return _DEV_SECRET  # type: ignore[name-defined]
    except NameError:
        pass

    # 尝试从文件读
    try:
        if os.path.isfile(_DEV_SECRET_FILE):
            with open(_DEV_SECRET_FILE, "r", encoding="utf-8") as f:
                disk = f.read().strip()
            if disk:
                _DEV_SECRET = disk
                logger.info(
                    "JWT_SECRET 从 %s 读取（dev 模式持久化）", _DEV_SECRET_FILE
                )
                return _DEV_SECRET
    except Exception as e:
        logger.warning("读取 %s 失败: %s", _DEV_SECRET_FILE, e)

    # 生成并持久化
    _DEV_SECRET = secrets.token_urlsafe(32)
    try:
        with open(_DEV_SECRET_FILE, "w", encoding="utf-8") as f:
            f.write(_DEV_SECRET)
        os.chmod(_DEV_SECRET_FILE, 0o600)
        logger.warning(
            "JWT_SECRET 未设置，已生成并写入 %s（dev 模式跨重启保活）；"
            "生产环境请在 .env.production 中配置固定的 JWT_SECRET",
            _DEV_SECRET_FILE,
        )
    except Exception as e:
        logger.error(
            "无法持久化 JWT_SECRET 到 %s: %s；本次进程关闭后 token 失效",
            _DEV_SECRET_FILE,
            e,
        )
    return _DEV_SECRET


# ── 密码 ────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("密码长度至少 8 位")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# ── JWT ─────────────────────────────────────────────────────

def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """返回 user_id；无效/过期返回 None"""
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        return sub if isinstance(sub, str) else None
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ── User CRUD ──────────────────────────────────────────────

def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def register_user(
    email: str,
    password: str,
    display_name: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    """
    注册新用户。
    :param user_id: 可选，指定稳定 ID（迁移脚本使用）；默认用 uuid4
    :raises ValueError: 邮箱格式非法 / 已存在 / 密码过短
    """
    email = _normalize_email(email)
    if not email or not EMAIL_RE.match(email):
        raise ValueError("邮箱格式不合法")

    pwd_hash = hash_password(password)
    uid = (user_id or "").strip() or f"u_{uuid.uuid4().hex[:16]}"

    with OrmSession(engine) as s:
        existing = s.query(User).filter_by(email=email).first()
        if existing:
            raise ValueError("该邮箱已注册")
        if s.query(User).filter_by(id=uid).first():
            raise ValueError(f"user_id {uid} 已存在")

        user = User(
            id=uid,
            email=email,
            password_hash=pwd_hash,
            display_name=display_name,
        )
        s.add(user)
        s.commit()
        s.refresh(user)
        return _user_to_public_dict(user)


def authenticate(email: str, password: str) -> Optional[dict]:
    """登录校验；成功返回 user dict，失败返回 None"""
    email = _normalize_email(email)
    if not email:
        return None
    with OrmSession(engine) as s:
        user = s.query(User).filter_by(email=email).first()
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        user.last_login_at = datetime.utcnow()
        s.commit()
        return _user_to_public_dict(user)


def get_user_by_id(user_id: str) -> Optional[dict]:
    with OrmSession(engine) as s:
        user = s.query(User).filter_by(id=user_id).first()
        return _user_to_public_dict(user) if user else None


def _user_to_public_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


# ── 登录 + Token 一体 ──────────────────────────────────────

def login(email: str, password: str) -> Optional[Tuple[str, dict]]:
    """返回 (token, user) 或 None"""
    user = authenticate(email, password)
    if not user:
        return None
    token = create_access_token(user["id"])
    return token, user


def register_and_login(
    email: str,
    password: str,
    display_name: Optional[str] = None,
) -> Tuple[str, dict]:
    user = register_user(email, password, display_name)
    token = create_access_token(user["id"])
    return token, user
