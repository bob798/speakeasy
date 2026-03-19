from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, UserProfile, UserFact, GrammarCard
from app.services.profile_service import get_profile, upsert_profile, assess_cefr
from app.logger import get_logger

router = APIRouter()
logger = get_logger("memory")


# ── Schemas ────────────────────────────────────────────────────────────────

class ProfileUpdate(BaseModel):
    profession:        Optional[str] = None
    industry:          Optional[str] = None
    topic_preferences: Optional[str] = None
    learning_goal:     Optional[str] = None
    personality_note:  Optional[str] = None
    cefr_level:        Optional[str] = None


class AssessmentRequest(BaseModel):
    user_id: str
    answers: list  # list of "can" | "partially" | "cannot", length 5


# ── Profile endpoints ──────────────────────────────────────────────────────

@router.get("/memory/profile")
async def get_memory_profile(user_id: str = Query(...)):
    profile = get_profile(user_id)
    if not profile:
        return {
            "user_id": user_id,
            "cefr_level": None,
            "profession": None,
            "industry": None,
            "topic_preferences": None,
            "learning_goal": None,
            "personality_note": None,
        }
    return {
        "user_id": profile.user_id,
        "cefr_level": profile.cefr_level,
        "profession": profile.profession,
        "industry": profile.industry,
        "topic_preferences": profile.topic_preferences,
        "learning_goal": profile.learning_goal,
        "personality_note": profile.personality_note,
    }


@router.put("/memory/profile")
async def update_memory_profile(user_id: str = Query(...), body: ProfileUpdate = ...):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    profile = upsert_profile(user_id, updates)
    return {
        "user_id": profile.user_id,
        "cefr_level": profile.cefr_level,
        "profession": profile.profession,
        "industry": profile.industry,
        "topic_preferences": profile.topic_preferences,
        "learning_goal": profile.learning_goal,
        "personality_note": profile.personality_note,
    }


# ── Assessment endpoint ────────────────────────────────────────────────────

@router.post("/assessment/self")
async def self_assessment(req: AssessmentRequest):
    if len(req.answers) != 5:
        raise HTTPException(status_code=400, detail="answers must have exactly 5 items")
    valid = {"can", "partially", "cannot"}
    for a in req.answers:
        if a not in valid:
            raise HTTPException(status_code=400, detail=f"invalid answer: {a}")

    cefr = assess_cefr(req.answers)
    profile = upsert_profile(req.user_id, {"cefr_level": cefr})
    return {"cefr_level": cefr, "user_id": req.user_id}


# ── Facts endpoints ────────────────────────────────────────────────────────

@router.get("/memory/facts")
async def get_memory_facts(
    user_id: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    with OrmSession(engine) as s:
        total = s.query(UserFact).filter_by(user_id=user_id).count()
        facts = (
            s.query(UserFact)
            .filter_by(user_id=user_id)
            .order_by(UserFact.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "total": total,
            "facts": [
                {
                    "id": f.id,
                    "content": f.content,
                    "source_session_id": f.source_session_id,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                }
                for f in facts
            ],
        }


@router.delete("/memory/facts/{fact_id}")
async def delete_memory_fact(fact_id: int, user_id: str = Query(...)):
    with OrmSession(engine) as s:
        fact = s.query(UserFact).filter_by(id=fact_id, user_id=user_id).first()
        if not fact:
            raise HTTPException(status_code=404, detail="Fact not found")
        s.delete(fact)
        s.commit()
    return {"deleted": True, "id": fact_id}


# ── Grammar cards endpoints ────────────────────────────────────────────────

@router.get("/memory/cards")
async def get_memory_cards(
    user_id: str = Query(...),
    status: Optional[str] = Query(None),
):
    with OrmSession(engine) as s:
        q = s.query(GrammarCard).filter_by(user_id=user_id)
        if status:
            q = q.filter(GrammarCard.status == status)
        else:
            q = q.filter(GrammarCard.status.in_(["active", "pending"]))
        cards = q.order_by(GrammarCard.updated_at.desc()).all()
        return {
            "cards": [
                {
                    "id": c.id,
                    "key": c.key,
                    "content": c.content,
                    "example_wrong": c.example_wrong,
                    "example_right": c.example_right,
                    "explanation_zh": c.explanation_zh,
                    "frequency": c.frequency,
                    "status": c.status,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in cards
            ]
        }


@router.delete("/memory/cards/{card_id}")
async def delete_memory_card(card_id: int, user_id: str = Query(...)):
    # V0.3 Step 5: soft-delete grammar card (status='deleted')
    with OrmSession(engine) as s:
        card = s.query(GrammarCard).filter_by(id=card_id, user_id=user_id).first()
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        card.status = "deleted"
        s.commit()
    return {"deleted": True, "id": card_id}
