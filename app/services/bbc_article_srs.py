"""BBC 文章级 SRS 服务 — V0.10

每个 (user_id, slug) 一张 FSRS 卡。题目按 slug 共享缓存。
答错的句子会落入 Vocabulary（item_type=sentence、source=bbc_eaw）。
"""
import json
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session as OrmSession

from app.models.db import (
    engine,
    BbcArticleCard,
    BbcArticleQuestion,
    BbcEawEpisode,
)
from app.services.fsrs_utils import (
    create_card,
    review_card,
    is_due,
    get_due_date,
    RATING_MAP,
)
from app.services import vocab_service
from app.logger import get_logger

logger = get_logger("bbc_article_srs")


def _card_to_dict(c: BbcArticleCard, episode: Optional[BbcEawEpisode] = None) -> Dict:
    return {
        "id": c.id,
        "user_id": c.user_id,
        "slug": c.slug,
        "status": c.status,
        "first_studied_at": c.first_studied_at.isoformat() if c.first_studied_at else None,
        "last_reviewed_at": c.last_reviewed_at.isoformat() if c.last_reviewed_at else None,
        "review_count": c.review_count,
        "due": get_due_date(c.fsrs_card_data) if c.fsrs_card_data else None,
        "is_due": is_due(c.fsrs_card_data) if c.fsrs_card_data else True,
        "title": episode.title if episode else None,
        "topic": episode.topic if episode else None,
    }


def _question_to_dict(q: BbcArticleQuestion) -> Dict:
    return {
        "id": q.id,
        "slug": q.slug,
        "qtype": q.qtype,
        "prompt": q.prompt,
        "answer": q.answer,
        "segment_idx": q.segment_idx,
        "phrases_used": json.loads(q.phrases_used or "[]"),
    }


def start_studying(user_id: str, slug: str) -> Dict:
    """首次学习 / 已有则返回当前卡。"""
    with OrmSession(engine) as s:
        episode = s.query(BbcEawEpisode).filter_by(slug=slug).first()
        if not episode:
            raise LookupError(f"BBC episode not found: {slug}")

        card = (
            s.query(BbcArticleCard)
            .filter_by(user_id=user_id, slug=slug, status="active")
            .first()
        )
        if card:
            return _card_to_dict(card, episode)

        card = BbcArticleCard(
            user_id=user_id,
            slug=slug,
            fsrs_card_data=create_card(),
            status="active",
        )
        s.add(card)
        s.commit()
        s.refresh(card)
        return _card_to_dict(card, episode)


def get_questions(slug: str, generator=None) -> List[Dict]:
    """取该 slug 的题目。若为空，调用 generator(slug) 异步生成并落库。

    generator 协议：async (slug) -> list[dict] of {qtype, prompt, answer, segment_idx?, phrases_used?}
    """
    with OrmSession(engine) as s:
        rows = s.query(BbcArticleQuestion).filter_by(slug=slug).order_by(BbcArticleQuestion.id).all()
        return [_question_to_dict(q) for q in rows]


async def ensure_questions(slug: str, generator) -> List[Dict]:
    """若 slug 还没题目则用 generator 生成；返回最终题目列表。"""
    existing = get_questions(slug)
    if existing:
        return existing

    raw = await generator(slug)
    if not raw:
        logger.warning("BBC question generator returned empty for slug=%s", slug)
        return []

    with OrmSession(engine) as s:
        # 二次检查防并发重复生成
        already = s.query(BbcArticleQuestion).filter_by(slug=slug).count()
        if already:
            rows = s.query(BbcArticleQuestion).filter_by(slug=slug).order_by(BbcArticleQuestion.id).all()
            return [_question_to_dict(q) for q in rows]

        for item in raw:
            q = BbcArticleQuestion(
                slug=slug,
                qtype=item.get("qtype", "back_translate"),
                prompt=item.get("prompt", ""),
                answer=item.get("answer", ""),
                segment_idx=item.get("segment_idx"),
                phrases_used=json.dumps(item.get("phrases_used", []), ensure_ascii=False),
            )
            s.add(q)
        s.commit()

        rows = s.query(BbcArticleQuestion).filter_by(slug=slug).order_by(BbcArticleQuestion.id).all()
        return [_question_to_dict(q) for q in rows]


def rate_card(
    user_id: str,
    slug: str,
    rating_str: str,
    wrong_segments: Optional[List[Dict]] = None,
) -> Dict:
    """评分推进 + 答错的句子批量入生词本。

    wrong_segments: [{text, segment_idx?, context?}]
    """
    rating_str = (rating_str or "").lower()
    if rating_str not in RATING_MAP:
        raise ValueError(f"rating 必须为 again/hard/good/easy，收到: {rating_str}")

    with OrmSession(engine) as s:
        card = (
            s.query(BbcArticleCard)
            .filter_by(user_id=user_id, slug=slug, status="active")
            .first()
        )
        if not card:
            raise LookupError(f"未找到学习记录: {slug}")

        if not card.fsrs_card_data:
            card.fsrs_card_data = create_card()

        new_json, card_dict = review_card(card.fsrs_card_data, RATING_MAP[rating_str])
        card.fsrs_card_data = new_json
        card.last_reviewed_at = datetime.utcnow()
        card.review_count = (card.review_count or 0) + 1
        s.commit()
        s.refresh(card)

        episode = s.query(BbcEawEpisode).filter_by(slug=slug).first()
        result = _card_to_dict(card, episode)

    # 答错联动：在事务外做（vocab_service 自管 session）
    saved = 0
    if wrong_segments:
        saved = vocab_service.bulk_save_from_bbc(
            user_id=user_id,
            slug=slug,
            segments=wrong_segments,
        )
    result["wrong_saved"] = saved
    return result


def list_due_articles(user_id: str) -> List[Dict]:
    """列出今日到期的文章卡。"""
    with OrmSession(engine) as s:
        cards = (
            s.query(BbcArticleCard)
            .filter_by(user_id=user_id, status="active")
            .all()
        )
        slugs = {c.slug for c in cards}
        episodes = {
            e.slug: e
            for e in s.query(BbcEawEpisode).filter(BbcEawEpisode.slug.in_(slugs)).all()
        }
        result = []
        for c in cards:
            d = _card_to_dict(c, episodes.get(c.slug))
            if d["is_due"]:
                result.append(d)
        result.sort(key=lambda x: x.get("due") or "")
        return result
