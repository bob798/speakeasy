"""
V0.7 后续修复：
  1. narration 按 CEFR 分级决定英文比例
  2. narration TTS 按等级选声线（A-B → xiaoxiao；C1+ → jenny）
  3. 解读 drawer 标题不截断，句子可换行全展示
"""
from pathlib import Path

from app.prompts.explain import EXPLAIN_SENTENCE_PROMPT, EXPLAIN_WORD_PROMPT
from app.services.explain_service import _SCHEMA_VERSION

PRACTICE_HTML = Path("static/practice.html")


# ── A. narration 分级规则写入 prompt ─────────────────────────

def test_sentence_prompt_has_level_language_rule():
    # 两个关键段落都要覆盖到
    assert "A1 / A2" in EXPLAIN_SENTENCE_PROMPT
    assert "B1 / B2" in EXPLAIN_SENTENCE_PROMPT
    assert "C1 / C2" in EXPLAIN_SENTENCE_PROMPT
    assert "纯中文" in EXPLAIN_SENTENCE_PROMPT
    assert "英文" in EXPLAIN_SENTENCE_PROMPT


def test_word_prompt_has_level_language_rule():
    assert "A1 / A2" in EXPLAIN_WORD_PROMPT
    assert "C1 / C2" in EXPLAIN_WORD_PROMPT
    assert "纯中文" in EXPLAIN_WORD_PROMPT


def test_schema_version_bumped_for_narration_rule_change():
    # 规则变更后必须升版本使旧缓存失效
    assert _SCHEMA_VERSION >= 4


# ── B. narration TTS voice 按等级选 ─────────────────────────

def test_narration_voice_switches_on_c_level():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    start = src.index('async function playExplainNarration')
    body  = src[start:src.index('\n}\n', start)]
    # 既要有中文 voice 也要有英文 voice
    assert "'xiaoxiao'" in body
    assert "'jenny'" in body
    # 读取 currentExplainPayload.cefr
    assert "currentExplainPayload.cefr" in body
    # 判断 C1/C2
    assert "C1" in body and "C2" in body


def test_current_payload_stores_cefr():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    # 至少一处非流式赋值带 cefr
    assert "cefr: data.cefr_level" in src
    # 流式路径里 partial 赋值也带 cefr
    assert "explanation: partial, cefr" in src


# ── C. drawer 标题不截断 ────────────────────────────────────

def test_title_no_js_truncation():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    # 原来 slice(0, 40) + '…' 的写法应消失
    assert "text.slice(0, 40)" not in src
    # openExplainDrawer 直接把完整 text 塞进 title
    fn_start = src.index('function openExplainDrawer(')
    fn_body  = src[fn_start:src.index('\n}\n', fn_start)]
    assert ".textContent" in fn_body
    assert "+ text" in fn_body
    assert ".slice(" not in fn_body


def test_title_css_allows_wrap():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    # 新规则：可换行 + 单词断行；旧的 nowrap/ellipsis 应消失
    css_start = src.index('.explain-title')
    css_end   = src.index('}', css_start)
    rule = src[css_start:css_end]
    assert "white-space:nowrap" not in rule
    assert "text-overflow:ellipsis" not in rule
    assert "word-break:break-word" in rule
    # header 改成顶部对齐以支持多行标题
    header_start = src.index('.explain-header')
    header_end   = src.index('}', header_start)
    header_rule  = src[header_start:header_end]
    assert "align-items:flex-start" in header_rule
