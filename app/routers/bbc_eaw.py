"""文章系列公共语料 API · 共享只读，不绑 user_id

路由前缀：/articles/episodes（由 main.py 注册）
"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session as OrmSession

from app.models.db import ArticleEpisode, engine

router = APIRouter()


@router.get("/articles/episodes")
async def list_episodes(
    limit: int = Query(100, ge=1, le=200),
    topic: Optional[str] = None,
    series: Optional[str] = None,
):
    """列出文章集 · 公共数据，无需登录"""
    with OrmSession(engine) as s:
        q = s.query(ArticleEpisode).order_by(ArticleEpisode.id.asc())
        if topic:
            q = q.filter(ArticleEpisode.topic == topic)
        if series:
            q = q.filter(ArticleEpisode.series == series)
        rows = q.limit(limit).all()
        return {
            "items": [
                {
                    "slug": r.slug,
                    "series": r.series,
                    "title": r.title,
                    "episode_id": r.episode_id,
                    "topic": r.topic,
                    "description": r.description,
                    "transcript_turns": r.transcript_turns,
                    "air_date": r.air_date,
                }
                for r in rows
            ],
            "count": len(rows),
        }


@router.get("/articles/episodes/{slug}")
async def get_episode(slug: str):
    """取单集详情 · 把 transcript 转成 PracticePlayer 期待的 segments 形态"""
    with OrmSession(engine) as s:
        row = s.query(ArticleEpisode).filter_by(slug=slug).first()
        if not row:
            raise HTTPException(404, "episode not found")

        transcript = json.loads(row.transcript_json or "[]")
        phrases = json.loads(row.phrases_json or "[]")

        segments = [
            {
                "content": item.get("text", ""),
                "speaker": item.get("speaker"),
                "from": None,
                "to": None,
            }
            for item in transcript
            if item.get("text", "").strip()
        ]

        return {
            "slug": row.slug,
            "title": row.title,
            "topic": row.topic,
            "description": row.description,
            "series": row.series,
            "source_type": "article",
            "segments": segments,
            "phrases": phrases,
            "listening_question": row.listening_question,
            "listening_answer": row.listening_answer,
            "url": row.url,
        }
