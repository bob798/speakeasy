"""
Stats API · V0.9.1
GET /stats/today · 首页 dashboard 数据

字段:
  streak_days:       连续有 session 的天数（到今天为止，UTC）
  today_message_count: 今日（本地日边界用 UTC 近似）用户发送的消息数
  today_session_count: 今日有活动的 session 数
  total_sessions:    用户累计 session 数
  due_cards:         待复习的 pronunciation_cards 数量
"""

from datetime import datetime, timedelta, timezone
import json

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import Session as ChatSession, Message, PronunciationCard
from app.routers.auth import get_current_user_id

router = APIRouter()


def _utc_today_start() -> datetime:
    """UTC 当天 00:00:00"""
    now = datetime.utcnow()
    return datetime(now.year, now.month, now.day)


async def _compute_streak(db: AsyncSession, user_id: str) -> int:
    """从今天往回数连续有 session 创建的天数（UTC 日）。"""
    rows = await db.execute(
        select(ChatSession.created_at)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.created_at.desc())
    )
    dates = sorted({dt.date() for (dt,) in rows.all()}, reverse=True)
    if not dates:
        return 0

    today = datetime.utcnow().date()
    streak = 0
    cursor = today

    # 允许今天没 session 也算（只要昨天有），从昨天起算
    if dates[0] != today:
        cursor = today - timedelta(days=1)

    for d in dates:
        if d == cursor:
            streak += 1
            cursor -= timedelta(days=1)
        elif d < cursor:
            break
    return streak


async def _count_due_cards(db: AsyncSession, user_id: str) -> int:
    """因为 fsrs_card_data 是 JSON 字符串，这里退化为拉全量再过滤"""
    rows = await db.execute(
        select(PronunciationCard.fsrs_card_data)
        .where(
            PronunciationCard.user_id == user_id,
            PronunciationCard.status == "active",
            PronunciationCard.fsrs_card_data != "",
        )
    )
    now = datetime.now(timezone.utc)
    count = 0
    for (data,) in rows.all():
        if not data:
            continue
        try:
            parsed = json.loads(data)
            due_str = parsed.get("due")
            if not due_str:
                continue
            due_dt = datetime.fromisoformat(due_str)
            if due_dt.tzinfo is None:
                due_dt = due_dt.replace(tzinfo=timezone.utc)
            if due_dt <= now:
                count += 1
        except (ValueError, json.JSONDecodeError):
            continue
    return count


@router.get("/stats/today")
async def stats_today(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    today_start = _utc_today_start()

    # 今日消息数
    today_msgs = await db.execute(
        select(func.count(Message.id))
        .join(ChatSession, Message.session_id == ChatSession.id)
        .where(
            ChatSession.user_id == user_id,
            Message.role == "user",
            Message.created_at >= today_start,
        )
    )
    today_message_count = today_msgs.scalar() or 0

    # 今日活跃 session 数
    today_sess = await db.execute(
        select(func.count(func.distinct(ChatSession.id)))
        .join(Message, Message.session_id == ChatSession.id)
        .where(
            ChatSession.user_id == user_id,
            Message.created_at >= today_start,
        )
    )
    today_session_count = today_sess.scalar() or 0

    # 累计 session 总数
    total_sess = await db.execute(
        select(func.count(ChatSession.id)).where(ChatSession.user_id == user_id)
    )
    total_sessions = total_sess.scalar() or 0

    streak_days = await _compute_streak(db, user_id)
    due_cards = await _count_due_cards(db, user_id)

    return {
        "streak_days": streak_days,
        "today_message_count": today_message_count,
        "today_session_count": today_session_count,
        "total_sessions": total_sessions,
        "due_cards": due_cards,
    }
