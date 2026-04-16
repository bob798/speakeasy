"""FSRS 共享工具 — grammar_cards 和 pronunciation_cards 共用"""

import json
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict

from fsrs import FSRS, Card, Rating

_scheduler = FSRS()

RATING_MAP = {
    "again": Rating.Again,
    "hard": Rating.Hard,
    "good": Rating.Good,
    "easy": Rating.Easy,
}


def create_card(initial_rating: Rating = Rating.Again) -> str:
    card = Card()
    card, _ = _scheduler.review_card(card, initial_rating)
    return json.dumps(card.to_dict())


def review_card(card_json: str, rating: Rating) -> Tuple[str, Dict]:
    card = Card.from_dict(json.loads(card_json))
    card, _ = _scheduler.review_card(card, rating)
    new_json = json.dumps(card.to_dict())
    return new_json, card.to_dict()


def get_due_date(card_json: str) -> Optional[str]:
    if not card_json:
        return None
    return json.loads(card_json).get("due")


def is_due(card_json: str) -> bool:
    due = get_due_date(card_json)
    if not due:
        return False
    due_dt = datetime.fromisoformat(due)
    if due_dt.tzinfo is None:
        due_dt = due_dt.replace(tzinfo=timezone.utc)
    return due_dt <= datetime.now(timezone.utc)
