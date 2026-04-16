"""发音练习服务 — 卡片 CRUD + FSRS 调度"""

import re
from typing import List, Dict, Optional

from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.exc import IntegrityError
from fsrs import Rating

from app.models.db import engine, PronunciationCard
from app.services.fsrs_utils import create_card, review_card, RATING_MAP
from app.logger import get_logger

logger = get_logger("practice_service")

_SPACE_NORM = re.compile(r"\s+")


def _normalize_text(text: str) -> str:
    return _SPACE_NORM.sub(" ", text.strip().lower())


def create_pronunciation_cards(
    user_id: str,
    items: List[Dict],
) -> Dict:
    created = 0
    skipped = 0
    with OrmSession(engine) as s:
        for item in items:
            raw_text = item.get("text", "")
            norm_text = _normalize_text(raw_text)
            if not norm_text:
                continue
            existing = s.query(PronunciationCard).filter_by(
                user_id=user_id, text=norm_text,
            ).first()
            if existing and existing.status != "deleted":
                skipped += 1
                continue
            if existing and existing.status == "deleted":
                existing.status = "active"
                existing.context = item.get("context", existing.context)
                existing.source_url = item.get("source_url", existing.source_url)
                existing.source_title = item.get("source_title", existing.source_title)
                existing.fsrs_card_data = create_card(Rating.Again)
                existing.practice_count = 0
                created += 1
            else:
                card = PronunciationCard(
                    user_id=user_id,
                    text=norm_text,
                    context=item.get("context", ""),
                    source_url=item.get("source_url"),
                    source_title=item.get("source_title"),
                    fsrs_card_data=create_card(Rating.Again),
                    status="active",
                )
                s.add(card)
                created += 1
        s.commit()
    return {"created": created, "skipped": skipped}


def get_pronunciation_cards(
    user_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    with OrmSession(engine) as s:
        q = s.query(PronunciationCard).filter_by(user_id=user_id)
        if status:
            q = q.filter_by(status=status)
        else:
            q = q.filter(PronunciationCard.status != "deleted")
        cards = q.order_by(PronunciationCard.created_at.desc()).offset(offset).limit(limit).all()
        return [_card_to_dict(c) for c in cards]


def review_pronunciation_card(
    card_id: int,
    user_id: str,
    rating_str: str,
) -> Optional[Dict]:
    rating = RATING_MAP.get(rating_str)
    if rating is None:
        return None
    with OrmSession(engine) as s:
        card = s.query(PronunciationCard).filter_by(
            id=card_id, user_id=user_id,
        ).first()
        if not card or card.status != "active":
            return None
        new_json, new_data = review_card(card.fsrs_card_data, rating)
        card.fsrs_card_data = new_json
        card.practice_count += 1
        s.commit()
        s.refresh(card)
        return {
            "id": card.id,
            "new_due": new_data.get("due"),
            "practice_count": card.practice_count,
        }


def delete_pronunciation_card(card_id: int, user_id: str) -> bool:
    with OrmSession(engine) as s:
        card = s.query(PronunciationCard).filter_by(
            id=card_id, user_id=user_id,
        ).first()
        if not card:
            return False
        card.status = "deleted"
        s.commit()
        return True


def get_due_pronunciation_cards(
    user_id: str,
    limit: int = 10,
) -> List[Dict]:
    import json
    from datetime import datetime, timezone

    with OrmSession(engine) as s:
        cards = (
            s.query(PronunciationCard)
            .filter_by(user_id=user_id, status="active")
            .filter(PronunciationCard.fsrs_card_data != "")
            .all()
        )
        due_cards = []
        for c in cards:
            try:
                card_data = json.loads(c.fsrs_card_data)
                due_str = card_data.get("due")
                if not due_str:
                    continue
                due_dt = datetime.fromisoformat(due_str)
                if due_dt.tzinfo is None:
                    due_dt = due_dt.replace(tzinfo=timezone.utc)
                if due_dt <= datetime.now(timezone.utc):
                    stability = card_data.get("stability", 0)
                    due_cards.append((stability, c))
            except (json.JSONDecodeError, ValueError):
                continue

        due_cards.sort(key=lambda x: x[0])
        return [_card_to_dict(c) for _, c in due_cards[:limit]]


def _card_to_dict(card: PronunciationCard) -> Dict:
    return {
        "id": card.id,
        "user_id": card.user_id,
        "text": card.text,
        "context": card.context,
        "source_url": card.source_url,
        "source_title": card.source_title,
        "fsrs_card_data": card.fsrs_card_data,
        "status": card.status,
        "practice_count": card.practice_count,
        "created_at": card.created_at.isoformat() if card.created_at else None,
        "updated_at": card.updated_at.isoformat() if card.updated_at else None,
    }
