"""
追问 System Prompt 注册表。每个 scope 对应一个 builder 函数：
  builder(context_payload: dict) -> str

context_payload 的字段由调用方与 builder 约定。新增 scope 时：
  1. 在 SCOPE_PROMPTS 注册新 key；
  2. 调用方传 context_payload 即可。
"""
from __future__ import annotations

import json
from typing import Callable, Dict


def _safe(val) -> str:
    if val is None:
        return ""
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


# ── practice_explain: 解读弹窗追问 ─────────────────────────
# context_payload:
#   kind: 'sentence' | 'word'
#   text: 原句 / 原词
#   context: 句子上下文（word 时用）
#   cefr_level: 用户 CEFR（可空）
#   explanation: 解读 JSON（可空）

def build_practice_explain_prompt(ctx: dict) -> str:
    kind = _safe(ctx.get("kind") or "sentence")
    text = _safe(ctx.get("text"))
    sentence_ctx = _safe(ctx.get("context"))
    cefr = _safe(ctx.get("cefr_level")) or "B1"
    explanation = ctx.get("explanation") or {}

    return (
        "You are a patient English tutor answering follow-up questions from a Chinese learner. "
        f"The learner's current CEFR level is {cefr}.\n\n"
        f"They are studying this {kind}: \"{text}\"\n"
        + (f"Sentence context: \"{sentence_ctx}\"\n" if sentence_ctx else "")
        + "The initial explanation shown to the learner (JSON):\n"
        + _safe(explanation) + "\n\n"
        "Rules:\n"
        "- 用中文回答，简洁不啰嗦，2-4 句话搞定（必要时可再多一点）；\n"
        "- 保持上下文一致：学习者的问题围绕这个词/句子，不要跑题；\n"
        f"- 例子按 {cefr} 级别的难度给；\n"
        "- 英文举例必须带中文翻译；\n"
        "- 不要重复整段解读，直接回应问题。"
    )


# ── translate: 翻译页追问（预留）───────────────────────────
# context_payload:
#   source_text / translated_text / direction

def build_translate_prompt(ctx: dict) -> str:
    src = _safe(ctx.get("source_text"))
    tgt = _safe(ctx.get("translated_text"))
    direction = _safe(ctx.get("direction") or "zh2en")
    return (
        "You are a bilingual translation coach. The learner is asking follow-up questions "
        "about a translation result.\n\n"
        f"Direction: {direction}\n"
        f"Source: \"{src}\"\n"
        f"Translation: \"{tgt}\"\n\n"
        "Rules:\n"
        "- 用中文回答，2-4 句；\n"
        "- 解释词选/句式/语气差异时给具体替换例子；\n"
        "- 不要泛泛而谈。"
    )


SCOPE_PROMPTS: Dict[str, Callable[[dict], str]] = {
    "practice_explain": build_practice_explain_prompt,
    "translate": build_translate_prompt,
}


def build_system_prompt(scope: str, context_payload: dict) -> str:
    builder = SCOPE_PROMPTS.get(scope)
    if not builder:
        raise ValueError(f"未注册的追问 scope: {scope}")
    return builder(context_payload or {})
