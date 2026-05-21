"""V0.10 · BBC 文章级 SRS 单测

覆盖：
  - start_studying: 首次建卡 + 幂等
  - ensure_questions: 首次调 generator + 二次返缓存
  - rate_card: FSRS 推进 + wrong_segments 联动入生词本
  - list_due_articles
"""
import asyncio
import json

import pytest
from sqlalchemy.orm import Session as OrmSession

from app.models.db import (
    engine,
    ArticleEpisode,
    BbcArticleCard,
    BbcArticleQuestion,
    Vocabulary,
)
from app.services import bbc_article_srs, vocab_service
from app.services.bbc_question_gen import generate_questions

USER = "user_bbc_test"
SLUG = "test-ep-1"


@pytest.fixture(autouse=True)
def _reset():
    with OrmSession(engine) as s:
        s.query(BbcArticleCard).filter_by(user_id=USER).delete()
        s.query(BbcArticleQuestion).filter_by(slug=SLUG).delete()
        s.query(Vocabulary).filter_by(user_id=USER).delete()
        s.query(ArticleEpisode).filter_by(slug=SLUG).delete()
        s.add(ArticleEpisode(
            slug=SLUG,
            url="http://example.com",
            title="Test Episode",
            topic="Test Topic",
            phrases_json=json.dumps(["come up with", "for sure"]),
            transcript_json=json.dumps([
                {"speaker": "A", "text": "We need to come up with a plan."},
                {"speaker": "B", "text": "I will help for sure."},
                {"speaker": "A", "text": "Great, let's start now."},
            ]),
            transcript_turns=3,
        ))
        s.commit()
    yield


def test_start_studying_creates_card():
    card = bbc_article_srs.start_studying(USER, SLUG)
    assert card["slug"] == SLUG
    assert card["due"] is not None
    assert card["title"] == "Test Episode"


def test_start_studying_is_idempotent():
    a = bbc_article_srs.start_studying(USER, SLUG)
    b = bbc_article_srs.start_studying(USER, SLUG)
    assert a["id"] == b["id"]


def test_start_studying_unknown_slug_raises():
    with pytest.raises(LookupError):
        bbc_article_srs.start_studying(USER, "nonexistent")


def test_ensure_questions_calls_generator_first_time(monkeypatch):
    calls = {"n": 0}

    async def fake_gen(slug):
        calls["n"] += 1
        return [
            {"qtype": "cloze", "prompt": "fill: ____", "answer": "blank"},
            {"qtype": "back_translate", "prompt": "translate", "answer": "Hello"},
        ]

    qs = asyncio.run(bbc_article_srs.ensure_questions(SLUG, fake_gen))
    assert len(qs) == 2
    assert calls["n"] == 1
    # 二次调用应直接读缓存，不再触发 generator
    qs2 = asyncio.run(bbc_article_srs.ensure_questions(SLUG, fake_gen))
    assert len(qs2) == 2
    assert calls["n"] == 1  # 没有再调


def test_real_generator_deterministic_produces_mixed_questions(monkeypatch):
    monkeypatch.setenv("SPEAKEASY_BBC_QUESTION_LLM", "0")
    qs = asyncio.run(generate_questions(SLUG))
    qtypes = {q["qtype"] for q in qs}
    assert "cloze" in qtypes
    assert "back_translate" in qtypes
    assert "recall_prompt" in qtypes


def test_llm_path_used_when_enabled(monkeypatch):
    """LLM 返回合法 JSON · 应直接采用 LLM 输出"""
    monkeypatch.setenv("SPEAKEASY_BBC_QUESTION_LLM", "1")

    class FakeClient:
        async def complete(self, messages, max_tokens=2000):
            return json.dumps({
                "questions": [
                    {"qtype": "cloze", "prompt": "Fill: ____", "answer": "blank", "segment_idx": 0, "phrases_used": ["blank"]},
                    {"qtype": "back_translate", "prompt": "翻译", "answer": "Hello", "segment_idx": 1, "phrases_used": []},
                    {"qtype": "recall_prompt", "prompt": "Summarize", "answer": "", "segment_idx": None, "phrases_used": []},
                ]
            })

    monkeypatch.setattr("app.services.model_client.get_client", lambda: FakeClient())
    qs = asyncio.run(generate_questions(SLUG))
    assert len(qs) == 3
    assert [q["qtype"] for q in qs] == ["cloze", "back_translate", "recall_prompt"]


def test_llm_failure_falls_back_to_deterministic(monkeypatch):
    """LLM 抛错 · 应回退到 deterministic 而不是返回空"""
    monkeypatch.setenv("SPEAKEASY_BBC_QUESTION_LLM", "1")

    class BoomClient:
        async def complete(self, messages, max_tokens=2000):
            raise RuntimeError("network down")

    monkeypatch.setattr("app.services.model_client.get_client", lambda: BoomClient())
    qs = asyncio.run(generate_questions(SLUG))
    assert qs, "fallback 应给出题目而不是空"
    assert any(q["qtype"] == "back_translate" for q in qs)


def test_llm_garbage_falls_back(monkeypatch):
    """LLM 返回非法 JSON · 也应回退"""
    monkeypatch.setenv("SPEAKEASY_BBC_QUESTION_LLM", "1")

    class GarbageClient:
        async def complete(self, messages, max_tokens=2000):
            return "not json at all"

    monkeypatch.setattr("app.services.model_client.get_client", lambda: GarbageClient())
    qs = asyncio.run(generate_questions(SLUG))
    assert qs


def test_llm_validates_qtype(monkeypatch):
    """LLM 返回未知 qtype 的题应被过滤；若全部不合法则回退"""
    monkeypatch.setenv("SPEAKEASY_BBC_QUESTION_LLM", "1")

    class MixedClient:
        async def complete(self, messages, max_tokens=2000):
            return json.dumps({
                "questions": [
                    {"qtype": "cloze", "prompt": "Fill: ____", "answer": "x"},
                    {"qtype": "bogus_type", "prompt": "x", "answer": "x"},
                ]
            })

    monkeypatch.setattr("app.services.model_client.get_client", lambda: MixedClient())
    qs = asyncio.run(generate_questions(SLUG))
    # 合法的 cloze 保留，bogus 被过滤
    assert all(q["qtype"] in {"cloze", "back_translate", "recall_prompt"} for q in qs)
    assert any(q["qtype"] == "cloze" for q in qs)


def test_rate_card_advances_due():
    bbc_article_srs.start_studying(USER, SLUG)
    result = bbc_article_srs.rate_card(USER, SLUG, "good")
    assert result["due"] is not None
    assert result["last_reviewed_at"] is not None
    assert result["review_count"] == 1


def test_rate_with_wrong_segments_inserts_vocab():
    bbc_article_srs.start_studying(USER, SLUG)
    result = bbc_article_srs.rate_card(
        USER, SLUG, "again",
        wrong_segments=[
            {"text": "We need to come up with a plan."},
            {"text": "I will help for sure."},
        ],
    )
    assert result["wrong_saved"] == 2
    items = vocab_service.list_items(user_id=USER, source_ref=SLUG)
    assert len(items) == 2
    assert all(it["source_type"] == "article" for it in items)


def test_rate_invalid_rating():
    bbc_article_srs.start_studying(USER, SLUG)
    with pytest.raises(ValueError):
        bbc_article_srs.rate_card(USER, SLUG, "meh")


def test_rate_unknown_slug_raises():
    with pytest.raises(LookupError):
        bbc_article_srs.rate_card(USER, "nonexistent", "good")


def test_list_due_articles_excludes_not_due():
    """新卡 FSRS 初始化后 due 在 ~1 分钟后，立刻查不应出现在 due 列表"""
    bbc_article_srs.start_studying(USER, SLUG)
    due = bbc_article_srs.list_due_articles(USER)
    # 新卡走默认 Rating.Again 初始化，due 在未来 → 不在 due 列表
    assert not any(d["slug"] == SLUG for d in due)


def test_list_due_articles_after_force_due(monkeypatch):
    """构造已到期的卡：直接清空 fsrs_card_data 让 is_due fallback 返回 True"""
    bbc_article_srs.start_studying(USER, SLUG)
    with OrmSession(engine) as s:
        c = s.query(BbcArticleCard).filter_by(user_id=USER, slug=SLUG).first()
        c.fsrs_card_data = ""  # is_due 对空串返回 False，但代码走 _card_to_dict 时直接给 is_due=True
        s.commit()
    due = bbc_article_srs.list_due_articles(USER)
    assert any(d["slug"] == SLUG for d in due)
