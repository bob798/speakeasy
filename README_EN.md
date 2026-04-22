# Speakeasy

> Your AI companion tutor. The more you talk, the better it knows you.

[中文文档](./README.md)

---

## What problem does this solve

People who want to practice English don't lack resources. They lack a practice partner that **actually knows them**.

Flashcards, drills, courses — the moment you stop, you start forgetting. And every app treats you like a stranger: it doesn't know what you do for work, doesn't remember what you said last time, doesn't know where you're weak or where you've already improved. After three months of practice, the system knows you exactly as well as it did on day one.

General AI (ChatGPT) can chat, but the same problem applies: when the conversation ends, everything resets. It doesn't accumulate, doesn't adapt, doesn't know you.

**Speakeasy's premise: a language tutor that genuinely builds up its understanding of you over time.**

---

## What Speakeasy is

An AI companion tutor, named Alex.

You talk about your real life — today's meeting, something that went sideways, where you went last weekend. Alex continuously builds a picture of you: what you do for work, where your language habits are, what's happening in your life. Every conversation, Alex knows you a little better — topics become more relevant, guidance more targeted, reinforcement more precise.

Alex has two ways to help you improve:

**Implicit (you don't notice, but it's happening)**
During conversation, Alex naturally plants the expressions you need to work on in his replies. You think you're chatting. Alex knows you're improving.

**Explicit (after the conversation, when you choose to review)**
At the end of each session, Alex generates a review: what you expressed well today, and where there's a more natural way to say it. You can dig in with follow-up questions, or just come back next time.

Not a course. Not a drill. Not an AI teacher. **A tutor that knows you better every time.**

---

## How it's different from practicing with ChatGPT

| | ChatGPT | Speakeasy (Alex) |
|---|---|---|
| Remembers what you said? | No — starts fresh every time | Yes. Will ask how that thing you mentioned turned out |
| Remembers your grammar patterns? | No | Yes — continuously reinforces them through natural conversation |
| Knows what you do for work? | No | Yes — adjusts topics and vocabulary to your context |
| Evolves over time? | No — same every session | Yes — gets more calibrated the more you talk |
| How does it help you improve? | You have to drive it | Implicit guidance + explicit review, both running in parallel |

---

## How Alex gets to know you

```
After each conversation:
  What you talked about
         │
         ├─► grammar_cards    Your recurring grammar patterns
         │   (FSRS schedules when to reinforce them in future conversations)
         │
         ├─► user_facts       What's happening in your life
         │   LLM extracts 2-3 facts: "User has an important presentation this week"
         │
         └─► user_profile     Who you are
             Profession / English level / topic preferences / learning goals

Next conversation: all three layers are injected into Alex's context.
Alex knows your language habits, what happened last week, where you're heading.
```

This isn't just a technical design — it's how Alex actually comes to know you.

---

## How it works in practice

```
You say: "Yesterday I go to a meeting with my boss..."

Alex responds naturally (implicit guidance, happening in the background):
"Oh that sounds tough — how did the meeting go?
 I went to a really long one last week too..."
  ↑ used "went" — your weak point, modeled without comment

Session ends. Alex generates a review (explicit, when you're ready):
  ✓ Expressions you used well today
  → More natural alternatives (not "you were wrong" — "here's a better way")

Next session, Alex has updated its understanding of you:
  · Uses more past tense forms, targeting your go/went pattern
  · Remembers the meeting with your boss, may naturally follow up
  · Knows you're a product manager, steers toward products, teams, users
```

**Three design principles:**

| Principle | What it is | What it isn't |
|---|---|---|
| **Knows you** | Profession + grammar habits + life events, continuously updated | Not just conversation history |
| **Guides you** | Topics, difficulty, reinforcement targets — dynamically adjusted, implicit + explicit | Not a fixed curriculum |
| **Stays with you** | Cross-session, no end point, becomes more yours over time | Not a one-off tool |

---

## Current state

| Version | Features |
|---|---|
| V0.1 ✅ | Text conversation (Alex persona) + daily tip + multi-model support |
| V0.2a ✅ | Voice input (STT) + voice output (TTS) + streaming + conversation history |
| V0.2b ✅ | Session review (errors + highlights) + FSRS scheduling + click-to-ask UI |
| V0.3 🔧 | User profile + level assessment + cross-session fact memory + memory management page |

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/your-username/speakeasy.git
cd speakeasy

# 2. Install
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env — pick one provider:
# MODEL_PROVIDER=anthropic / deepseek / volcengine / zhipu
```

| Provider | Get API Key | Best for |
|---|---|---|
| Anthropic | https://console.anthropic.com | Best English quality |
| DeepSeek | https://platform.deepseek.com | Best value |
| Volcengine | https://console.volcengine.com/ark | China-stable access |
| Zhipu GLM | https://bigmodel.cn | Free debugging |

```bash
# 4. Run
uvicorn main:app --reload
# Open http://localhost:8000
```

---

## Tech stack

```
Frontend               Backend                AI Layer
────────────          ────────────           ──────────────────────
HTML / CSS / JS ──────► FastAPI (Python) ────► Claude / DeepSeek
(Vanilla)              SQLAlchemy 2.0         Doubao / GLM
                       SQLite + aiosqlite     (via OpenRouter)
                            │
                       STT: faster-whisper (local inference)
                       TTS: edge-tts (local, no API cost)
                       Memory: py-fsrs (FSRS 6 algorithm)
```

---

## FAQ

**httpx SOCKS proxy error**

On macOS, if you're running Clash / Surge with "system proxy" enabled, httpx reads the system proxy config by default. The codebase already sets `trust_env=False` — if errors persist, check for any additional httpx client initializations.

**STT returns no transcript**

On first run, faster-whisper downloads a model file (~150MB) automatically. Wait for the download to complete.

---

## License

MIT
