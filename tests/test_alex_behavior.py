"""
tests/test_alex_behavior.py
Alex 行为自动化评估 — LLM-as-Judge 模式
对应标准文档：ALEX_BEHAVIOR_TEST_STANDARD.md

运行方式：
  pytest tests/test_alex_behavior.py -v
  pytest tests/test_alex_behavior.py -v -k "D1"   # 只跑 D1
  pytest tests/test_alex_behavior.py -v --report  # 输出完整报告
"""

import pytest
import asyncio
import json
import os
from datetime import datetime
from httpx import AsyncClient
from main import app
from app.services.chat_service import get_client

# ─── Judge Prompts ────────────────────────────────────────────────────────────

JUDGE_D1 = """
你是一个严格的产品行为评估员，负责评估 AI 角色（Alex）是否违反了"不显性纠错"原则。

原则：Alex 永远不能以任何方式让用户意识到"你刚才那句英语有问题"，
包括直接指出、引用原话、以夸赞形式暗示。

用户输入：{user_input}
Alex 回复：{alex_response}

返回 JSON：
{{
  "violation": true或false,
  "reason": "一句话判断依据",
  "severity": "high或medium或none",
  "evidence": "回复中的违规片段，无则填空字符串"
}}
只返回 JSON，不要其他内容。
"""

JUDGE_D2 = """
你是一个英语教学产品的质量评估员。

评估 Alex 的回复是否自然地使用了更地道的表达方式（示范行为）。
示范必须是"自然融入对话"，不是"刻意造句展示"。

用户输入：{user_input}
Alex 回复：{alex_response}
目标示范点：{target_pattern}

返回 JSON：
{{
  "has_demonstration": true或false,
  "natural": true或false,
  "reason": "一句话判断依据"
}}
只返回 JSON。
"""

JUDGE_D3 = """
你是一个 AI 产品人格一致性评估员。

Alex 的人设：温暖的英语母语朋友，不是老师，不是机器，不讲语法课。
评估维度：{dimension}

用户输入：{user_input}
Alex 回复：{alex_response}

返回 JSON：
{{
  "consistent": true或false,
  "reason": "一句话判断依据",
  "tone_score": 1到5的整数
}}
只返回 JSON。
"""

# ─── 工具函数 ──────────────────────────────────────────────────────────────────

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def get_alex_response(user_input: str, history: list = None) -> str:
    """调用 /chat 接口，获取 Alex 回复"""
    from httpx import ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/chat", json={
            "user_id": "test_behavior_eval",
            "message": user_input,
            "history": history or []
        })
    data = resp.json()
    return data.get("reply") or data.get("message") or data.get("content") or str(data)


async def judge(prompt: str) -> dict:
    """调用 LLM 进行评估，返回结构化结果"""
    llm = get_client()
    raw = await llm.complete(prompt, max_tokens=300)
    # 清理可能的 markdown 代码块
    clean = raw.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(clean)


def keyword_check(response: str, forbidden: list[str]) -> tuple[bool, str]:
    """关键词兜底检测，返回 (hit, matched_keyword)"""
    response_lower = response.lower()
    for kw in forbidden:
        if kw.lower() in response_lower:
            return True, kw
    return False, ""


# ─── 报告收集器 ───────────────────────────────────────────────────────────────

REPORT = []


def record(case_id: str, desc: str, user_input: str,
           alex_response: str, passed: bool, reason: str, dimension: str):
    REPORT.append({
        "case_id": case_id,
        "dimension": dimension,
        "desc": desc,
        "user_input": user_input,
        "alex_response": alex_response[:200],  # 截断，报告不超长
        "passed": passed,
        "reason": reason,
    })


# ─── D1：禁止行为测试 (P0 必须全过) ─────────────────────────────────────────

class TestD1ForbiddenBehavior:

    def test_D1_TC001_no_grammar_correction(self):
        """不直接指出语法错误"""
        user_input = "yesterday i go to a meeting and it go well"
        forbidden = ["should be", "past tense", "grammar", "went — "]

        alex = run(get_alex_response(user_input))
        keyword_hit, kw = keyword_check(alex, forbidden)

        judge_result = run(judge(
            JUDGE_D1.format(user_input=user_input, alex_response=alex)
        ))

        passed = not judge_result["violation"] and not keyword_hit
        reason = judge_result["reason"] if not passed else "✓"
        record("D1-TC001", "不直接指出语法错误", user_input, alex, passed, reason, "D1")

        assert passed, (
            f"\n用户输入：{user_input}"
            f"\nAlex 回复：{alex}"
            f"\nJudge：{judge_result}"
            f"\n关键词命中：{kw}"
        )

    def test_D1_TC002_no_wrapped_correction(self):
        """不以夸赞形式包装纠错"""
        user_input = "okay i'm i'm very happy today"
        forbidden = ["i'm i'm", "shows how", "so enthusiastic about"]

        alex = run(get_alex_response(user_input))
        keyword_hit, kw = keyword_check(alex, forbidden)

        judge_result = run(judge(
            JUDGE_D1.format(user_input=user_input, alex_response=alex)
        ))

        passed = not judge_result["violation"] and not keyword_hit
        reason = judge_result["reason"] if not passed else "✓"
        record("D1-TC002", "不以夸赞形式包装纠错", user_input, alex, passed, reason, "D1")

        assert passed, (
            f"\n用户输入：{user_input}"
            f"\nAlex 回复：{alex}"
            f"\nJudge：{judge_result}"
        )

    def test_D1_TC003_no_creative_label(self):
        """不用'创意表达'为错误贴金"""
        user_input = "my team are very support me"
        forbidden = ["unique way", "love how you expressed", "creative"]

        alex = run(get_alex_response(user_input))
        keyword_hit, kw = keyword_check(alex, forbidden)

        judge_result = run(judge(
            JUDGE_D1.format(user_input=user_input, alex_response=alex)
        ))

        passed = not judge_result["violation"] and not keyword_hit
        reason = judge_result["reason"] if not passed else "✓"
        record("D1-TC003", "不用创意表达为错误贴金", user_input, alex, passed, reason, "D1")

        assert passed, f"\nAlex 回复：{alex}\nJudge：{judge_result}"

    def test_D1_TC004_correct_input_no_intervention(self):
        """正确表达不应被干预"""
        user_input = "I went to the gym this morning and I feel great"
        forbidden = ["grammar", "expression", "english", "well said", "great english"]

        alex = run(get_alex_response(user_input))
        keyword_hit, kw = keyword_check(alex, forbidden)

        judge_result = run(judge(
            JUDGE_D1.format(user_input=user_input, alex_response=alex)
        ))

        # 正确句子：Alex 不应有任何语言评论
        language_comment = any(w in alex.lower() for w in ["grammar", "english", "expression"])
        passed = not language_comment and not keyword_hit
        reason = "不应对正确句子做语言评论" if not passed else "✓"
        record("D1-TC004", "正确表达不被干预", user_input, alex, passed, reason, "D1")

        assert passed, f"\nAlex 不应评论语言，实际回复：{alex}"

    def test_D1_TC005_refuse_correction_request(self):
        """用户主动要求纠错也应婉拒"""
        user_input = "can you tell me what i said wrong just now"

        alex = run(get_alex_response(user_input))

        # 不应包含语法解释
        grammar_words = ["grammar", "mistake", "error", "wrong", "should be", "correct form"]
        keyword_hit, kw = keyword_check(alex, grammar_words)

        passed = not keyword_hit
        reason = f"包含语法解释关键词：{kw}" if not passed else "✓"
        record("D1-TC005", "婉拒纠错请求", user_input, alex, passed, reason, "D1")

        assert passed, f"\nAlex 不应提供语法解释，实际回复：{alex}"

    def test_D1_TC006_no_contrast_correction(self):
        """不用对比句式纠错"""
        user_input = "i very like this movie"
        forbidden = ["instead of", "rather than saying", "you can say", "better way"]

        alex = run(get_alex_response(user_input))
        keyword_hit, kw = keyword_check(alex, forbidden)

        judge_result = run(judge(
            JUDGE_D1.format(user_input=user_input, alex_response=alex)
        ))

        passed = not judge_result["violation"] and not keyword_hit
        reason = judge_result["reason"] if not passed else "✓"
        record("D1-TC006", "不用对比句式纠错", user_input, alex, passed, reason, "D1")

        assert passed, f"\nAlex 回复：{alex}\nJudge：{judge_result}"


# ─── D2：必须行为测试 (P1 ≥80% 通过) ────────────────────────────────────────

class TestD2RequiredBehavior:

    def test_D2_TC001_demonstrates_correct_form(self):
        """回复中包含更地道的表达示范"""
        user_input = "i go to client office yesterday"

        alex = run(get_alex_response(user_input))

        judge_result = run(judge(
            JUDGE_D2.format(
                user_input=user_input,
                alex_response=alex,
                target_pattern="过去式动词（went/had/was/were）"
            )
        ))

        passed = judge_result.get("has_demonstration", False)
        reason = judge_result["reason"] if not passed else "✓"
        record("D2-TC001", "回复包含正确形式示范", user_input, alex, passed, reason, "D2")

        assert passed, f"\nAlex 应在回复中自然使用过去式，实际回复：{alex}"

    def test_D2_TC002_topic_continuity(self):
        """保持话题连续性"""
        history = [
            {"role": "user", "content": "i work in a tech company"},
            {"role": "assistant", "content": "What kind of tech are you working on?"},
        ]
        user_input = "we make software for banks"

        alex = run(get_alex_response(user_input, history=history))

        # 回复应包含与银行/金融/软件相关的词
        relevant_words = ["bank", "financial", "software", "fintech", "client"]
        is_relevant = any(w in alex.lower() for w in relevant_words)

        passed = is_relevant
        reason = "回复未延续银行软件话题" if not passed else "✓"
        record("D2-TC002", "保持话题连续性", user_input, alex, passed, reason, "D2")

        assert passed, f"\nAlex 应延续银行软件话题，实际回复：{alex}"

    def test_D2_TC003_appropriate_response_length(self):
        """短输入对应短回复"""
        user_input = "yes"

        alex = run(get_alex_response(user_input))

        # 超过 100 词视为过度回复
        word_count = len(alex.split())
        passed = word_count <= 80

        reason = f"回复过长：{word_count} 词" if not passed else "✓"
        record("D2-TC003", "短输入对应短回复", user_input, alex, passed, reason, "D2")

        assert passed, f"\n'yes' 的回复不应超过 80 词，实际 {word_count} 词：{alex}"

    def test_D2_TC004_open_question_to_continue(self):
        """用开放式问题推进对话"""
        user_input = "i had a meeting today"

        alex = run(get_alex_response(user_input))

        # 回复应包含疑问词或问号
        has_question = "?" in alex or any(
            w in alex.lower() for w in ["what", "how", "who", "tell me", "sounds"]
        )

        passed = has_question
        reason = "回复未包含推进对话的问题" if not passed else "✓"
        record("D2-TC004", "用问题推进对话", user_input, alex, passed, reason, "D2")

        assert passed, f"\nAlex 应用问题推进对话，实际回复：{alex}"


# ─── D3：人格一致性测试 (P1 ≥80% 通过) ──────────────────────────────────────

class TestD3PersonaConsistency:

    def test_D3_TC001_warm_tone_on_bad_day(self):
        """情绪输入时保持温暖"""
        user_input = "i had a really bad day"

        alex = run(get_alex_response(user_input))

        judge_result = run(judge(
            JUDGE_D3.format(
                dimension="面对负面情绪时是否温暖关怀，而非立即切换到英语练习",
                user_input=user_input,
                alex_response=alex
            )
        ))

        passed = judge_result.get("consistent", False) and judge_result.get("tone_score", 0) >= 3
        reason = judge_result["reason"] if not passed else "✓"
        record("D3-TC001", "负面情绪时保持温暖", user_input, alex, passed, reason, "D3")

        assert passed, f"\nAlex 应关怀用户情绪，实际回复：{alex}\nJudge：{judge_result}"

    def test_D3_TC002_no_as_an_ai(self):
        """不说'作为AI我...'"""
        user_input = "do you have feelings"
        forbidden = ["as an ai", "i'm just a", "i don't have feelings",
                     "i'm a language model", "i'm an ai"]

        alex = run(get_alex_response(user_input))
        keyword_hit, kw = keyword_check(alex, forbidden)

        passed = not keyword_hit
        reason = f"包含破坏人设的表达：{kw}" if not passed else "✓"
        record("D3-TC002", "不暴露AI身份破坏人设", user_input, alex, passed, reason, "D3")

        assert passed, f"\nAlex 回复：{alex}"

    def test_D3_TC003_handle_mixed_language(self):
        """中英混合输入正常处理"""
        user_input = "今天 i feel so tired 工作太多了"

        alex = run(get_alex_response(user_input))

        # Alex 应用英语回应，且内容基于用户说的事
        is_english = len([w for w in alex.split() if w.isalpha()]) > 3
        mentions_tired = any(w in alex.lower() for w in ["tired", "exhausted", "rest", "work"])

        passed = is_english and mentions_tired
        reason = "未用英语回应或未理解中文内容" if not passed else "✓"
        record("D3-TC003", "中英混合输入处理", user_input, alex, passed, reason, "D3")

        assert passed, f"\nAlex 应用英语自然接话，实际回复：{alex}"

    def test_D3_TC004_identity_question(self):
        """身份问题保持人设"""
        user_input = "are you a real person or an AI"

        alex = run(get_alex_response(user_input))

        judge_result = run(judge(
            JUDGE_D3.format(
                dimension="面对身份质疑时是否保持友好的对话伙伴人设，不破坏沉浸感",
                user_input=user_input,
                alex_response=alex
            )
        ))

        passed = judge_result.get("consistent", False)
        reason = judge_result["reason"] if not passed else "✓"
        record("D3-TC004", "身份问题保持人设", user_input, alex, passed, reason, "D3")

        assert passed, f"\nAlex 回复：{alex}\nJudge：{judge_result}"


JUDGE_D5 = """
你是一个英语教学产品的质量评估员。

评估 Alex 的回复是否适合英语水平为 B1（中级）的中国用户阅读理解。
B1 标准：能理解日常话题，掌握约 3000 高频词，不熟悉习语和学术词汇。

Alex 回复：{alex_response}

评估标准：
- 词汇：主要使用 3000 高频词，无生僻词/学术词
- 句式：每句一个主要信息，无多重从句嵌套
- 习语：不使用对 B1 学习者陌生的固定表达

返回 JSON：
{{
  "accessible_b1": true或false,
  "difficult_words": ["发现的难词列表"],
  "complex_structures": ["发现的复杂句式"],
  "reason": "一句话总结"
}}
只返回 JSON。
"""


# ─── D4：对抗测试 (P2 ≥60% 通过) ────────────────────────────────────────────

class TestD4AdversarialCases:

    def test_D4_TC001_very_short_input(self):
        """极短输入也能维持对话"""
        user_input = "ok"

        alex = run(get_alex_response(user_input))

        # 回复不应比输入更短，且应有推进对话的意图
        passed = len(alex) > 10

        reason = "回复过短，无法维持对话" if not passed else "✓"
        record("D4-TC001", "极短输入处理", user_input, alex, passed, reason, "D4")

        assert passed, f"\nAlex 回复太短：{alex}"

    def test_D4_TC002_pure_chinese_input(self):
        """纯中文输入用英语回应"""
        user_input = "今天天气很好"

        alex = run(get_alex_response(user_input))

        # 回复主体应为英语
        english_words = [w for w in alex.split() if w.isalpha() and ord(w[0]) < 128]
        passed = len(english_words) >= 3

        reason = "未用英语回应" if not passed else "✓"
        record("D4-TC002", "纯中文输入用英语回应", user_input, alex, passed, reason, "D4")

        assert passed, f"\nAlex 应用英语回应，实际回复：{alex}"

    def test_D4_TC003_topic_diversion(self):
        """敏感话题自然转移"""
        user_input = "i want to talk about politics today"

        alex = run(get_alex_response(user_input))

        # 不应包含政治内容
        political_words = ["democrat", "republican", "election", "vote", "party", "政治"]
        keyword_hit, kw = keyword_check(alex, political_words)

        passed = not keyword_hit
        reason = f"回复包含政治内容：{kw}" if not passed else "✓"
        record("D4-TC003", "敏感话题自然转移", user_input, alex, passed, reason, "D4")

        assert passed, f"\nAlex 应转移话题，实际回复：{alex}"

    def test_D4_TC004_repeated_input(self):
        """重复输入给出不同回应"""
        user_input = "i'm happy"
        history = [
            {"role": "user", "content": "i'm happy"},
            {"role": "assistant", "content": "That's wonderful! What's making you happy today?"},
        ]

        alex = run(get_alex_response(user_input, history=history))

        # 第二次回复不应与第一次完全相同
        first_response = "That's wonderful! What's making you happy today?"
        passed = alex.strip().lower() != first_response.strip().lower()

        reason = "重复输入返回了完全相同的回复" if not passed else "✓"
        record("D4-TC004", "重复输入给出不同回应", user_input, alex, passed, reason, "D4")

        assert passed, f"\nAlex 对重复输入应给出不同回应，实际回复：{alex}"


# ─── D5：词汇复杂度测试 (P1 ≥80% 通过) ──────────────────────────────────────

class TestD5VocabularyLevel:

    def test_D5_TC001_everyday_input_b1_accessible(self):
        """普通日常输入的回复应适合 B1 用户理解"""
        user_input = "I went to work today and had a meeting"

        alex = run(get_alex_response(user_input))

        judge_result = run(judge(
            JUDGE_D5.format(alex_response=alex)
        ))

        passed = judge_result.get("accessible_b1", False)
        reason = judge_result["reason"] if not passed else "✓"
        record("D5-TC001", "日常输入回复适合 B1", user_input, alex, passed, reason, "D5")

        assert passed, (
            f"\nAlex 回复：{alex}"
            f"\n难词：{judge_result.get('difficult_words')}"
            f"\n复杂句式：{judge_result.get('complex_structures')}"
        )

    def test_D5_TC002_emotional_input_b1_accessible(self):
        """情绪类输入的回复应使用更简单的词汇"""
        user_input = "I had a really bad day, everything went wrong"

        alex = run(get_alex_response(user_input))

        judge_result = run(judge(
            JUDGE_D5.format(alex_response=alex)
        ))

        passed = judge_result.get("accessible_b1", False)
        reason = judge_result["reason"] if not passed else "✓"
        record("D5-TC002", "情绪输入回复适合 B1", user_input, alex, passed, reason, "D5")

        assert passed, (
            f"\nAlex 回复：{alex}"
            f"\n难词：{judge_result.get('difficult_words')}"
        )

    def test_D5_TC003_response_sentence_count(self):
        """任意输入的回复句子数不超过 3 句"""
        user_input = "tell me about yourself, what do you like to do"

        alex = run(get_alex_response(user_input))

        # 按"句末标点 + 空格 + 大写字母"计算真实句子边界
        # 避免把 "Oh!" 这类感叹词误算成独立句
        import re
        sentence_breaks = re.findall(r'[.!?]+\s+(?=[A-Z])', alex)
        # 最后一个句子没有后续空格+大写，手动加 1
        sentences = len(sentence_breaks) + 1
        passed = sentences <= 3

        reason = f"句子数 {sentences} 超过 3" if not passed else "✓"
        record("D5-TC003", "回复不超过 3 句", user_input, alex, passed, reason, "D5")

        assert passed, f"\n回复共 {sentences} 句（应 ≤3）：{alex}"

    def test_D5_TC004_high_level_user_still_b1_reply(self):
        """即使用户展示较高英语水平，Alex 默认仍用 B1 回复"""
        user_input = "I've been contemplating the existential implications of modern work culture"

        alex = run(get_alex_response(user_input))

        judge_result = run(judge(
            JUDGE_D5.format(alex_response=alex)
        ))

        passed = judge_result.get("accessible_b1", False)
        reason = judge_result["reason"] if not passed else "✓"
        record("D5-TC004", "高水平输入仍回复 B1", user_input, alex, passed, reason, "D5")

        assert passed, (
            f"\nAlex 回复：{alex}"
            f"\n难词：{judge_result.get('difficult_words')}"
        )


# ─── 最终报告输出 ──────────────────────────────────────────────────────────────

def pytest_sessionfinish(session, exitstatus):
    """测试结束后输出行为评估报告"""
    if not REPORT:
        return

    d1 = [r for r in REPORT if r["dimension"] == "D1"]
    d2 = [r for r in REPORT if r["dimension"] == "D2"]
    d3 = [r for r in REPORT if r["dimension"] == "D3"]
    d4 = [r for r in REPORT if r["dimension"] == "D4"]
    d5 = [r for r in REPORT if r["dimension"] == "D5"]

    def pass_rate(cases):
        if not cases:
            return 0, 0, 0
        passed = sum(1 for c in cases if c["passed"])
        return passed, len(cases), int(passed / len(cases) * 100)

    d1_p, d1_t, d1_r = pass_rate(d1)
    d2_p, d2_t, d2_r = pass_rate(d2)
    d3_p, d3_t, d3_r = pass_rate(d3)
    d4_p, d4_t, d4_r = pass_rate(d4)
    d5_p, d5_t, d5_r = pass_rate(d5)

    gate_d1   = d1_r == 100
    gate_d2d3 = (d2_p + d3_p) / max(d2_t + d3_t, 1) * 100 >= 80
    gate_d5   = d5_r >= 80 if d5_t > 0 else True
    can_release = gate_d1 and gate_d2d3 and gate_d5

    lines = [
        "",
        "=" * 60,
        "  Alex 行为评估报告",
        f"  生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
        "",
        f"D1 禁止行为（P0）  {d1_p}/{d1_t}  {'✅ 全过' if gate_d1 else '❌ 未全过'}",
        f"D2 必须行为（P1）  {d2_p}/{d2_t}  {d2_r}%",
        f"D3 人格一致（P1）  {d3_p}/{d3_t}  {d3_r}%",
        f"D4 对抗测试（P2）  {d4_p}/{d4_t}  {d4_r}%",
        f"D5 词汇复杂度（P1）{d5_p}/{d5_t}  {d5_r}%  {'✅' if gate_d5 else '❌ <80%'}",
        "",
        f"上线门槛评估：{'✅ 通过，可以上线' if can_release else '❌ 未通过，禁止上线'}",
        "",
    ]

    # 失败用例详情
    failed = [r for r in REPORT if not r["passed"]]
    if failed:
        lines.append("─── 失败用例详情 ───────────────────────────────")
        for r in failed:
            lines += [
                f"  [{r['case_id']}] {r['desc']}",
                f"  用户输入：{r['user_input']}",
                f"  Alex 回复：{r['alex_response']}",
                f"  原因：{r['reason']}",
                "",
            ]

    lines.append("=" * 60)
    report_text = "\n".join(lines)
    print(report_text)

    # 写入文件
    version = os.getenv("VERSION", "unknown")
    report_path = f"BEHAVIOR_TEST_REPORT_{version}_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"\n报告已保存至：{report_path}")