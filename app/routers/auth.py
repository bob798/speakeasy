"""认证路由 — /auth/register · /auth/login · /auth/me"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel

from app.services.auth_service import (
    register_and_login,
    login as auth_login,
    get_user_by_id,
    decode_access_token,
)
from app.logger import get_logger

logger = get_logger("auth")

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


# ── Routes ───────────────────────────────────────────────────

@router.post("/auth/register", status_code=201)
async def register(req: RegisterRequest):
    try:
        token, user = register_and_login(
            email=req.email,
            password=req.password,
            display_name=req.display_name,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"token": token, "user": user}


@router.post("/auth/login")
async def login(req: LoginRequest):
    result = auth_login(req.email, req.password)
    if not result:
        raise HTTPException(401, "邮箱或密码错误")
    token, user = result
    return {"token": token, "user": user}


# ── 依赖注入 ─────────────────────────────────────────────────

async def get_current_user_id(
    authorization: Optional[str] = Header(None),
) -> str:
    """从 Authorization: Bearer <token> 解析 user_id；无效则 401"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "未认证，请先登录")
    token = authorization.split(None, 1)[1].strip()
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(401, "登录已过期，请重新登录")
    return user_id


async def get_current_user_id_optional(
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """同上但未提供 token 时返回 None 而不抛异常"""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(None, 1)[1].strip()
    return decode_access_token(token)


@router.get("/auth/me")
async def me(user_id: str = Depends(get_current_user_id)):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "用户不存在")
    return {"user": user}
