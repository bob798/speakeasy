"""BBC 文章级 SRS 路由 — V0.10"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.routers.auth import get_current_user_id
from app.services import bbc_article_srs
from app.services.bbc_question_gen import generate_questions
from app.logger import get_logger

logger = get_logger("bbc_review")

router = APIRouter()


class WrongSegment(BaseModel):
    text: str
    segment_idx: Optional[int] = None
    context: Optional[str] = None


class RateRequest(BaseModel):
    rating: str  # again | hard | good | easy
    wrong_segments: Optional[List[WrongSegment]] = None


@router.post("/bbc-eaw/{slug}/start", status_code=201)
async def start(slug: str, user_id: str = Depends(get_current_user_id)):
    try:
        return bbc_article_srs.start_studying(user_id, slug)
    except LookupError as e:
        raise HTTPException(404, str(e))


@router.get("/bbc-eaw/{slug}/review")
async def review(slug: str, user_id: str = Depends(get_current_user_id)):
    """取该文章的复习题；未生成则懒加载首次生成。"""
    try:
        questions = await bbc_article_srs.ensure_questions(slug, generate_questions)
    except LookupError as e:
        raise HTTPException(404, str(e))
    if not questions:
        raise HTTPException(503, "题目生成失败，请稍后重试")
    return {"slug": slug, "questions": questions, "count": len(questions)}


@router.post("/bbc-eaw/{slug}/rate")
async def rate(
    slug: str,
    req: RateRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        wrong = [s.model_dump() for s in (req.wrong_segments or [])]
        return bbc_article_srs.rate_card(user_id, slug, req.rating, wrong)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except LookupError as e:
        raise HTTPException(404, str(e))


@router.get("/bbc-eaw/due")
async def due(user_id: str = Depends(get_current_user_id)):
    items = bbc_article_srs.list_due_articles(user_id)
    return {"items": items, "count": len(items)}
