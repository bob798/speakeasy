"""BBC 文章复习题生成 — V0.10

公共入口：
    await generate_questions(slug: str) -> list[dict]

策略：先尝试 LLM 出题，失败则退回 deterministic 版本。
返回结构：
    [{qtype, prompt, answer, segment_idx?, phrases_used?}]
qtype: cloze | back_translate | recall_prompt

环境变量：
    SPEAKEASY_BBC_QUESTION_LLM=0  关闭 LLM，强制走 deterministic（测试 / 离线）
"""
import json
import os
import re
from typing import List, Dict, Optional

from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, BbcEawEpisode
from app.prompts.bbc_questions import BBC_QUESTION_GEN_PROMPT
from app.logger import get_logger

logger = get_logger("bbc_question_gen")

VALID_QTYPES = {"cloze", "back_translate", "recall_prompt"}


def _load_episode(slug: str) -> Optional[BbcEawEpisode]:
    with OrmSession(engine) as s:
        return s.query(BbcEawEpisode).filter_by(slug=slug).first()


def _build_cloze(transcript: List[Dict], phrases: List[str]) -> Optional[Dict]:
    """找一段 transcript，里面包含至少一个 phrase，挖空。"""
    if not phrases:
        return None
    for idx, turn in enumerate(transcript):
        text = turn.get("text", "")
        for phrase in phrases:
            if phrase and phrase.lower() in text.lower():
                # 大小写无关替换为 ____
                lower = text.lower()
                start = lower.find(phrase.lower())
                blanked = text[:start] + "____" + text[start + len(phrase):]
                return {
                    "qtype": "cloze",
                    "prompt": f"听并补全：\n{blanked}",
                    "answer": phrase,
                    "segment_idx": idx,
                    "phrases_used": [phrase],
                }
    return None


def _build_back_translate(transcript: List[Dict], take: int = 2) -> List[Dict]:
    """挑前 take 个非空英文句，让用户中→英回译。answer 留空给前端做参考对照。"""
    out = []
    for idx, turn in enumerate(transcript):
        text = (turn.get("text") or "").strip()
        if not text:
            continue
        out.append({
            "qtype": "back_translate",
            "prompt": f"把这句意思翻回英文：\n{text}",
            "answer": text,  # 原句作为参考答案
            "segment_idx": idx,
            "phrases_used": [],
        })
        if len(out) >= take:
            break
    return out


def _build_recall(topic: Optional[str], phrases: List[str]) -> Optional[Dict]:
    if not topic and not phrases:
        return None
    used = phrases[:3]
    hint = "、".join(used) if used else ""
    prompt = f"用 1-2 句话复述这篇文章的主题"
    if topic:
        prompt += f"（话题：{topic}）"
    if hint:
        prompt += f"，尽量用上：{hint}"
    return {
        "qtype": "recall_prompt",
        "prompt": prompt,
        "answer": "",
        "segment_idx": None,
        "phrases_used": used,
    }


def _strip_code_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
    return raw.strip()


def _validate_question(q: Dict) -> Optional[Dict]:
    qtype = q.get("qtype")
    prompt = (q.get("prompt") or "").strip()
    if qtype not in VALID_QTYPES or not prompt:
        return None
    seg_idx = q.get("segment_idx")
    if seg_idx is not None and not isinstance(seg_idx, int):
        seg_idx = None
    phrases_used = q.get("phrases_used") or []
    if not isinstance(phrases_used, list):
        phrases_used = []
    return {
        "qtype": qtype,
        "prompt": prompt,
        "answer": (q.get("answer") or ""),
        "segment_idx": seg_idx,
        "phrases_used": phrases_used,
    }


async def _generate_via_llm(episode: BbcEawEpisode) -> List[Dict]:
    """LLM 出题；任何异常向上抛，由 generate_questions 捕获后回退。"""
    from app.services.model_client import get_client  # 延迟导入以便测试时无 LLM 也能用

    transcript = json.loads(episode.transcript_json or "[]")
    phrases = json.loads(episode.phrases_json or "[]")
    transcript = [
        {"speaker": t.get("speaker", ""), "text": t["text"], "idx": i}
        for i, t in enumerate(transcript)
        if (t.get("text") or "").strip()
    ]
    payload = json.dumps(
        {
            "topic": episode.topic or "",
            "phrases": phrases,
            "transcript": transcript,
        },
        ensure_ascii=False,
    )
    messages = [
        {"role": "system", "content": BBC_QUESTION_GEN_PROMPT},
        {"role": "user", "content": payload},
    ]
    client = get_client()
    raw = await client.complete(messages, max_tokens=2000, scene="bbc_question_gen")
    cleaned = _strip_code_fences(raw)
    data = json.loads(cleaned)

    items = data.get("questions") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError(f"LLM 返回缺少 questions 数组: {cleaned[:200]}")

    validated = [v for v in (_validate_question(q) for q in items) if v]
    if not validated:
        raise ValueError("LLM 返回的题目全部不合法")
    return validated[:6]


def _generate_deterministic(episode: BbcEawEpisode) -> List[Dict]:
    transcript = json.loads(episode.transcript_json or "[]")
    phrases = json.loads(episode.phrases_json or "[]")
    transcript = [t for t in transcript if (t.get("text") or "").strip()]

    questions: List[Dict] = []

    cloze = _build_cloze(transcript, phrases)
    if cloze:
        questions.append(cloze)

    questions.extend(_build_back_translate(transcript, take=2))

    recall = _build_recall(episode.topic, phrases)
    if recall:
        questions.append(recall)

    if len(questions) < 2:
        questions.extend(_build_back_translate(transcript, take=2))

    return questions[:6]


def _llm_enabled() -> bool:
    return os.environ.get("SPEAKEASY_BBC_QUESTION_LLM", "1") not in ("0", "false", "False", "")


async def generate_questions(slug: str) -> List[Dict]:
    """生成 4-6 道混合题。LLM 优先，失败自动回退 deterministic。"""
    episode = _load_episode(slug)
    if not episode:
        logger.warning("generate_questions: slug not found %s", slug)
        return []

    if _llm_enabled():
        try:
            questions = await _generate_via_llm(episode)
            logger.info("BBC questions LLM-generated for slug=%s · %d", slug, len(questions))
            return questions
        except Exception as e:
            logger.warning("BBC questions LLM 失败，回退 deterministic · slug=%s · %s", slug, e)

    return _generate_deterministic(episode)
