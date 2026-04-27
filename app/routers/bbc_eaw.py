"""BBC English at Work 公共语料 API · 共享只读，不绑 user_id"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session as OrmSession

from app.models.db import BbcEawEpisode, engine

router = APIRouter()


@router.get("/bbc-eaw/episodes")
async def list_episodes(
    limit: int = Query(100, ge=1, le=200),
    topic: Optional[str] = None,
):
    """列出 EAW 集 · 公共数据，无需登录"""
    with OrmSession(engine) as s:
        q = s.query(BbcEawEpisode).order_by(BbcEawEpisode.id.asc())
        if topic:
            q = q.filter(BbcEawEpisode.topic == topic)
        rows = q.limit(limit).all()
        return {
            "items": [
                {
                    "slug": r.slug,
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


@router.get("/bbc-eaw/episodes/{slug}")
async def get_episode(slug: str):
    """取单集详情 · 把 transcript 转成 PracticePlayer 期待的 segments 形态"""
    with OrmSession(engine) as s:
        row = s.query(BbcEawEpisode).filter_by(slug=slug).first()
        if not row:
            raise HTTPException(404, "episode not found")

        transcript = json.loads(row.transcript_json or "[]")
        phrases = json.loads(row.phrases_json or "[]")

        # transcript: [{speaker, text}] → segments: [{content, speaker}]
        # PracticePlayer 用 seg.content 做主键，无时间戳就用顺序 idx 做兜底
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
            "source_type": "bbc_eaw",
            "segments": segments,
            "phrases": phrases,
            "listening_question": row.listening_question,
            "listening_answer": row.listening_answer,
            "url": row.url,
        }
