import json

from fastapi import APIRouter, HTTPException, Depends

from fsrs import FSRS, Card, Rating

from app.models.db import GrammarCard
from app.schemas.chat import RateRequest
from app.services.review_service import (
    get_session_review,
    get_card_by_key,
    update_card_fsrs,
    mark_session_user_rated,
)
from app.routers.auth import get_current_user_id
from app.logger import get_logger

router = APIRouter()
logger = get_logger("review")

_scheduler = FSRS()


@router.get("/review/{session_id}")
async def get_review(session_id: str, user_id: str = Depends(get_current_user_id)):
    review = await get_session_review(session_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    # Ownership validation to prevent IDOR
    if review.user_id != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to review")
    return {
        "session_id": review.session_id,
        "errors": json.loads(review.errors),
        "highlights": json.loads(review.highlights),
        "stats": json.loads(review.stats),
    }


@router.post("/review/{session_id}/rate")
async def rate_review(
    session_id: str,
    request: RateRequest,
    user_id: str = Depends(get_current_user_id),
):
    rating = Rating.Good if request.rating == "good" else Rating.Again

    card_row = await get_card_by_key(user_id, request.card_key)
    if not card_row:
        raise HTTPException(status_code=404, detail="Card not found")

    card = Card.from_dict(json.loads(card_row.fsrs_card_data))
    card, _ = _scheduler.review_card(card, rating)

    await update_card_fsrs(card_row.id, json.dumps(card.to_dict()))
    await mark_session_user_rated(session_id)

    return {"next_review": card.due.isoformat()}
