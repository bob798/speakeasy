# Speakeasy

> Your English is good enough. What stops you is that first second before you speak.

[中文文档](./README.md)

---

## What problem does this solve

Chinese professionals don't freeze in English because they don't know the language. They freeze because they're afraid — afraid of making mistakes, afraid of sounding unprofessional, afraid of judgment.

Most language apps make this worse: pronunciation scores, grammar corrections, losing hearts. The more you practice, the more you fear speaking.

**Speakeasy's bet isn't "teach you English." It's "help you stop being afraid to speak."**

---

## What Speakeasy is

An English-speaking friend with memory, named Alex.

You talk about your real life — today's meeting, something that went sideways at work, where you went last weekend. Alex never corrects you explicitly. But you gradually speak more naturally. Alex remembers what you've told him and picks up the thread next time. He knows what you do for work and steers topics toward your context.

Not a course. Not a drill. Not an AI teacher. **A friend.**

---

## How it's different from practicing with ChatGPT

| | ChatGPT | Speakeasy (Alex) |
|---|---|---|
| Remembers what you said? | No — starts fresh every time | Yes. Will ask how that thing you mentioned turned out |
| Remembers your grammar patterns? | No | Yes — reinforces correct forms naturally in conversation |
| Knows what you do for work? | No | Yes — adjusts topics and vocabulary to your context |
| Will it correct you? | Yes, directly | Never. Uses natural modeling instead |
| Good for? | Anything, but nothing accumulates | Long-term spoken fluency, especially workplace English |

---

## How it works

```
You say: "Yesterday I go to a meeting with my boss..."
                            ↓
Alex responds naturally (no correction):
"Oh that sounds tough — how did the meeting go?
 I went to a really long one last week too..."
                            ↓
Session ends. Alex generates a review:
  - Expressions you used well (what you did right)
  - More natural alternatives (not "you were wrong" — "here's a better way")
                            ↓
Next session, Alex remembers:
  - You have a past tense habit (quietly uses went/had/was more often)
  - You had a stressful meeting last week (might ask "how did that work out?")
  - You're a product manager (steers toward products, teams, user research)
```

**Three design principles:**

| Principle | What it is | What it isn't |
|---|---|---|
| **Zero judgment** | No scores, no red marks, no "you should say..." | Not a lenient teacher |
| **Natural modeling** | Alex plants correct expressions in replies; you absorb them | Not a hidden grammar lesson |
| **Alex remembers you** | Error history + life events + your profile | Not just conversation history |

---

## How Alex's memory works

```
After each conversation:
  What you talked about
         │
         ├─► grammar_cards    Recurring grammar errors
         │   (FSRS schedules when to reinforce them in future conversations)
         │
         ├─► user_facts       What happened in your life
         │   LLM extracts 2-3 facts: "User has an important presentation this week"
         │
         └─► user_profile     Who you are
             Profession / learning goal / topic preferences / English level

Next conversation: all three layers are injected into Alex's context.
Alex knows your recurring mistakes, last week's events, what you're working toward.
```

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
uvicorn app.main:app --reload
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
