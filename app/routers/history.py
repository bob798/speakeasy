from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.db import Session, Message
from app.routers.auth import get_current_user_id

router = APIRouter()
STALE = timedelta(hours=2)


@router.get("/history")
async def get_history(
    limit:   int = Query(default=20, ge=1, le=100),
    offset:  int = Query(default=0,  ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    # 懒更新：超 2 小时的活跃 session 补齐 ended_at
    stale_result = await db.execute(
        select(Session)
        .where(Session.user_id == user_id, Session.ended_at == None)
        .options(selectinload(Session.messages))
    )
    now = datetime.utcnow()
    for s in stale_result.scalars():
        if s.messages:
            last = max(m.created_at for m in s.messages)
            if now - last > STALE:
                s.ended_at = last
    await db.commit()

    total_result = await db.execute(
        select(func.count()).select_from(Session).where(Session.user_id == user_id)
    )
    total = total_result.scalar()

    rows_result = await db.execute(
        select(Session)
        .where(Session.user_id == user_id)
        .options(selectinload(Session.messages))
        .order_by(Session.created_at.desc())
        .limit(limit).offset(offset)
    )
    rows = rows_result.scalars().all()

    def preview(s):
        first = next((m for m in s.messages if m.role == "user"), None)
        if first:
            t = first.content[:20]
            return t + ("..." if len(first.content) > 20 else "")
        return f"对话 · {s.created_at.strftime('%H:%M')}"

    return {
        "sessions": [
            {
                "id":         s.id,
                "created_at": s.created_at.isoformat() + "Z",
                "ended_at":   (s.ended_at.isoformat() + "Z") if s.ended_at else None,
                "preview":    preview(s)
            } for s in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/history/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(
        select(Session)
        .where(Session.id == session_id)
        .options(selectinload(Session.messages))
    )
    session = result.scalar_one_or_none()
    if not session:
        return {"session_id": session_id, "messages": []}
    # 鉴权：session 必须属于当前用户
    if session.user_id != user_id:
        raise HTTPException(403, "无权访问该会话")

    return {
        "session_id": session_id,
        "messages": [
            {
                "id":         m.id,
                "role":       m.role,
                "content":    m.content,
                "created_at": m.created_at.isoformat() + "Z"
            } for m in session.messages
        ]
    }
