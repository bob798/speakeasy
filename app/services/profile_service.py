from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.db import engine, UserProfile
from app.logger import get_logger

logger = get_logger("profile_service")

# ── CEFR assessment ────────────────────────────────────────────────────────
# 5 questions, each answer: "can"=2 / "partially"=1 / "cannot"=0
# total score 0-10 → CEFR level
_SCORE_TO_CEFR = [
    (0, 2,  "A1"),
    (3, 4,  "A2"),
    (5, 6,  "B1"),
    (7, 8,  "B2"),
    (9, 10, "C1"),
]

ANSWER_SCORES = {"can": 2, "partially": 1, "cannot": 0}


def assess_cefr(answers: list) -> str:
    """
    接受一个 list，每项为 "can" / "partially" / "cannot"。
    返回对应 CEFR 级别字符串。
    """
    total = sum(ANSWER_SCORES.get(a, 0) for a in answers)
    for lo, hi, level in _SCORE_TO_CEFR:
        if lo <= total <= hi:
            return level
    return "B1"  # fallback


# ── Profile CRUD ───────────────────────────────────────────────────────────

def get_profile(user_id: str) -> Optional[UserProfile]:
    with Session(engine) as s:
        return s.query(UserProfile).filter_by(user_id=user_id).first()


def upsert_profile(user_id: str, updates: dict) -> UserProfile:
    """
    创建或更新 user_profile 记录。
    只修改 updates 中提供的字段，其余保持不变。
    """
    allowed = {
        "cefr_level", "profession", "industry",
        "topic_preferences", "learning_goal", "personality_note",
    }
    with Session(engine) as s:
        row = s.query(UserProfile).filter_by(user_id=user_id).first()
        if row is None:
            row = UserProfile(user_id=user_id)
            s.add(row)
        for key, val in updates.items():
            if key in allowed:
                setattr(row, key, val)
        row.updated_at = datetime.utcnow()
        s.commit()
        s.refresh(row)
        # Detach from session before returning (for use outside session context)
        s.expunge(row)
        return row
