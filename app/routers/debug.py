import os
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session as OrmSession

from app.config import settings
from app.database import engine
from app.services.model_client import PROVIDER_CONFIG
from app.models.db import engine as sync_engine, LlmCallLog
from app.routers.auth import get_current_user_id

router = APIRouter()


@router.get("/debug/status")
async def debug_status():
    provider = os.getenv("MODEL_PROVIDER", "anthropic").lower()
    env_key  = PROVIDER_CONFIG.get(provider, {}).get("env_key", "")
    api_key  = os.getenv(env_key, "") if env_key else ""

    # 检查 DB 连通性
    db_status = "disconnected"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        pass

    return {
        "status":              "ok",
        "model":               settings.MODEL_NAME,
        "provider":            provider,
        "api_key_configured":  bool(api_key),
        "db":                  db_status,
        "stt_available":       bool(settings.GROQ_API_KEY),
        "tts_available":       True,
        "groq_key_configured": bool(settings.GROQ_API_KEY),
    }


def _safe_input_preview(raw: str) -> str:
    try:
        return json.loads(raw)[-1]["content"][:200]
    except Exception:
        return ""


@router.get("/debug/llm-logs")
async def list_llm_logs(
    scene: str = Query(None),
    model: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
):
    """查询 LLM 调用日志，用于模型选型对比"""
    with OrmSession(sync_engine) as s:
        q = s.query(LlmCallLog).order_by(LlmCallLog.created_at.desc())
        if scene:
            q = q.filter(LlmCallLog.scene == scene)
        if model:
            q = q.filter(LlmCallLog.model == model)
        rows = q.limit(limit).all()
        return {
            "logs": [
                {
                    "id": r.id,
                    "scene": r.scene,
                    "provider": r.provider,
                    "model": r.model,
                    "stream": r.stream,
                    "ttft_ms": r.ttft_ms,
                    "total_ms": r.total_ms,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "status": r.status,
                    "error_message": r.error_message,
                    "input_preview": _safe_input_preview(r.input_messages),
                    "output_preview": (r.output_text or "")[:200],
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
            "count": len(rows),
        }


@router.get("/debug/llm-logs/{log_id}")
async def get_llm_log(
    log_id: int,
    user_id: str = Depends(get_current_user_id),
):
    """查看单条 LLM 调用日志的完整输入输出"""
    with OrmSession(sync_engine) as s:
        r = s.query(LlmCallLog).filter_by(id=log_id).first()
        if not r:
            raise HTTPException(404, "日志不存在")
        return {
            "id": r.id,
            "scene": r.scene,
            "provider": r.provider,
            "model": r.model,
            "stream": r.stream,
            "ttft_ms": r.ttft_ms,
            "total_ms": r.total_ms,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "status": r.status,
            "error_message": r.error_message,
            "input_messages": json.loads(r.input_messages) if r.input_messages else [],
            "output_text": r.output_text,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
