"""通用追问（Ask）服务 — 跨页面复用的多轮 Q&A

scope 决定 system prompt 模板（见 app/prompts/ask.py）；
ref_type/ref_id 指向业务侧的被追问对象（解读、译文等）；
context_payload 保存首轮 system prompt 所需的上下文，持久化在 thread 上。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, AskThread, AskMessage
from app.prompts.ask import SCOPE_PROMPTS, build_system_prompt
from app.services.model_client import get_client
from app.logger import get_logger

logger = get_logger("ask_service")

MAX_QUESTION_LEN = 1000
MAX_HISTORY_TURNS = 10     # 追问不做长会话，10 轮封顶
DEFAULT_TITLE_LEN = 30


class AskError(ValueError):
    """业务错误（非空、越界、scope 不存在等）"""


def _valid_scope(scope: str) -> None:
    if scope not in SCOPE_PROMPTS:
        raise AskError(f"未支持的 scope: {scope}")


def _dump(payload) -> str:
    return json.dumps(payload or {}, ensure_ascii=False)


def _load(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _make_title(scope: str, ref_id: str, first_question: str) -> str:
    q = (first_question or "").strip().replace("\n", " ")
    if q:
        return q[:DEFAULT_TITLE_LEN]
    return f"{scope}:{ref_id}"[:DEFAULT_TITLE_LEN]


def _load_history(s: OrmSession, thread_id: int) -> List[AskMessage]:
    return (
        s.query(AskMessage)
        .filter_by(thread_id=thread_id)
        .order_by(AskMessage.id)
        .all()
    )


def _history_to_messages(history: List[dict]) -> List[dict]:
    # 限制最近 MAX_HISTORY_TURNS 轮（=user+assistant 对话）
    trimmed = history[-(MAX_HISTORY_TURNS * 2):]
    return [{"role": m["role"], "content": m["content"]} for m in trimmed]


# ── Public API ─────────────────────────────────────────────

async def create_thread(
    *,
    user_id: str,
    scope: str,
    ref_type: str,
    ref_id: str,
    context_payload: Optional[dict],
    first_question: str,
) -> dict:
    """新建 thread 并完成首轮问答。返回 {thread_id, messages: [user, assistant]}。"""
    if not user_id:
        raise AskError("user_id 不能为空")
    _valid_scope(scope)
    if not ref_type or not ref_id:
        raise AskError("ref_type / ref_id 不能为空")
    q = (first_question or "").strip()
    if not q:
        raise AskError("问题不能为空")
    if len(q) > MAX_QUESTION_LEN:
        raise AskError(f"问题长度不能超过 {MAX_QUESTION_LEN} 字符")

    ctx = context_payload or {}
    system_prompt = build_system_prompt(scope, ctx)

    # 先建 thread + user message 入库
    with OrmSession(engine) as s:
        thread = AskThread(
            user_id=user_id,
            scope=scope,
            ref_type=ref_type,
            ref_id=str(ref_id),
            title=_make_title(scope, str(ref_id), q),
            context_payload=_dump(ctx),
        )
        s.add(thread)
        s.flush()
        thread_id = thread.id
        s.add(AskMessage(thread_id=thread_id, role="user", content=q))
        s.commit()

    # LLM 调用
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": q},
    ]
    client = get_client()
    answer = (await client.complete(messages, max_tokens=800)).strip()

    with OrmSession(engine) as s:
        s.add(AskMessage(thread_id=thread_id, role="assistant", content=answer))
        # touch updated_at
        t = s.query(AskThread).filter_by(id=thread_id).first()
        if t:
            t.updated_at = datetime.utcnow()
        s.commit()

    return {
        "thread_id": thread_id,
        "messages": [
            {"role": "user", "content": q},
            {"role": "assistant", "content": answer},
        ],
    }


async def append_message(
    *,
    user_id: str,
    thread_id: int,
    question: str,
) -> dict:
    """在已有 thread 中追问，返回 {thread_id, answer}。"""
    q = (question or "").strip()
    if not q:
        raise AskError("问题不能为空")
    if len(q) > MAX_QUESTION_LEN:
        raise AskError(f"问题长度不能超过 {MAX_QUESTION_LEN} 字符")

    with OrmSession(engine) as s:
        t = s.query(AskThread).filter_by(id=thread_id).first()
        if not t or t.status == "deleted":
            raise AskError("thread 不存在或已删除")
        if t.user_id != user_id:
            raise AskError("无权访问此 thread")
        scope = t.scope
        ctx = _load(t.context_payload)
        history_raw = _load_history(s, thread_id)
        history = [{"role": m.role, "content": m.content} for m in history_raw]
        s.add(AskMessage(thread_id=thread_id, role="user", content=q))
        t.updated_at = datetime.utcnow()
        s.commit()

    system_prompt = build_system_prompt(scope, ctx)
    messages = (
        [{"role": "system", "content": system_prompt}]
        + _history_to_messages(history)
        + [{"role": "user", "content": q}]
    )
    client = get_client()
    answer = (await client.complete(messages, max_tokens=800)).strip()

    with OrmSession(engine) as s:
        s.add(AskMessage(thread_id=thread_id, role="assistant", content=answer))
        t = s.query(AskThread).filter_by(id=thread_id).first()
        if t:
            t.updated_at = datetime.utcnow()
        s.commit()

    return {"thread_id": thread_id, "answer": answer}


def list_threads(
    *,
    user_id: str,
    scope: Optional[str] = None,
    ref_type: Optional[str] = None,
    ref_id: Optional[str] = None,
    limit: int = 50,
) -> List[dict]:
    with OrmSession(engine) as s:
        q = s.query(AskThread).filter_by(user_id=user_id, status="active")
        if scope:
            q = q.filter(AskThread.scope == scope)
        if ref_type:
            q = q.filter(AskThread.ref_type == ref_type)
        if ref_id:
            q = q.filter(AskThread.ref_id == str(ref_id))
        rows = q.order_by(AskThread.updated_at.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "scope": r.scope,
                "ref_type": r.ref_type,
                "ref_id": r.ref_id,
                "title": r.title,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]


def get_thread(*, user_id: str, thread_id: int) -> Optional[dict]:
    with OrmSession(engine) as s:
        t = s.query(AskThread).filter_by(id=thread_id).first()
        if not t or t.status == "deleted" or t.user_id != user_id:
            return None
        msgs = _load_history(s, thread_id)
        return {
            "id": t.id,
            "scope": t.scope,
            "ref_type": t.ref_type,
            "ref_id": t.ref_id,
            "title": t.title,
            "messages": [
                {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat() if m.created_at else None}
                for m in msgs
            ],
        }


def delete_thread(*, user_id: str, thread_id: int) -> bool:
    with OrmSession(engine) as s:
        t = s.query(AskThread).filter_by(id=thread_id).first()
        if not t or t.user_id != user_id:
            return False
        t.status = "deleted"
        s.commit()
        return True
