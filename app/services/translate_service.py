"""翻译服务 — LLM 翻译 + 生词本 CRUD"""

from typing import List, Dict, Optional
from datetime import datetime

from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, Vocabulary
from app.prompts.translate import TRANSLATE_ZH2EN_PROMPT, TRANSLATE_EN2ZH_PROMPT
from app.services.model_client import get_client
from app.logger import get_logger

logger = get_logger("translate_service")

VALID_DIRECTIONS = {"zh2en", "en2zh"}


async def translate_text(text: str, direction: str) -> str:
    """
    翻译文本。
    :param text: 源文本（不超过 1000 字符）
    :param direction: 'zh2en' | 'en2zh'
    :raises ValueError: 空文本 / 超长 / 无效方向
    :raises Exception: LLM 调用失败
    """
    if not text or not text.strip():
        raise ValueError("输入文本不能为空")

    text = text.strip()

    if len(text) > 1000:
        raise ValueError("输入文本不能超过 1000 字符")

    if direction not in VALID_DIRECTIONS:
        raise ValueError(f"无效的翻译方向: {direction}，可选值: zh2en / en2zh")

    if direction == "zh2en":
        system_prompt = TRANSLATE_ZH2EN_PROMPT
    else:
        system_prompt = TRANSLATE_EN2ZH_PROMPT

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ]

    client = get_client()
    result = await client.complete(messages)
    return result.strip()


def save_vocabulary(
    user_id: str,
    source_text: str,
    translated_text: str,
    direction: str,
    context: Optional[str] = None,
) -> Dict:
    """写入生词本，返回记录 dict"""
    if direction not in VALID_DIRECTIONS:
        raise ValueError(f"无效的翻译方向: {direction}，可选值: zh2en / en2zh")
    if not source_text or not source_text.strip():
        raise ValueError("源文本不能为空")
    if not translated_text or not translated_text.strip():
        raise ValueError("译文不能为空")
    with OrmSession(engine) as s:
        v = Vocabulary(
            user_id=user_id,
            source_text=source_text,
            translated_text=translated_text,
            direction=direction,
            context=context,
            status="active",
        )
        s.add(v)
        s.commit()
        s.refresh(v)
        return _vocab_to_dict(v)


def list_vocabulary(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    """查询生词本列表（仅 status='active'）"""
    with OrmSession(engine) as s:
        items = (
            s.query(Vocabulary)
            .filter_by(user_id=user_id, status="active")
            .order_by(Vocabulary.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [_vocab_to_dict(v) for v in items]


def delete_vocabulary(vocab_id: int, user_id: str) -> bool:
    """软删除生词本条目，返回是否成功"""
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(id=vocab_id, user_id=user_id).first()
        if not v:
            return False
        v.status = "deleted"
        s.commit()
        return True


def _vocab_to_dict(v: Vocabulary) -> Dict:
    return {
        "id": v.id,
        "user_id": v.user_id,
        "source_text": v.source_text,
        "translated_text": v.translated_text,
        "direction": v.direction,
        "context": v.context,
        "status": v.status,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }
