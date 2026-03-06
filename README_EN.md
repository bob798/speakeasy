# Speakeasy 🌿

> An AI-powered English speaking companion — judgment-free, natural, effective.

[中文文档](./README.md)

---

## Why I Built This

Most English learning apps share two fundamental problems:

1. **Irrelevant content** — Practice scenarios feel artificial, disconnected from real life
2. **Judgment anxiety** — Grammar corrections and pronunciation scores create pressure before you even open your mouth

**Speakeasy takes a different approach**: An AI native English friend named Alex who chats with you about your real life — never corrects you explicitly, but naturally models better expressions throughout the conversation.

---

## How It Works

```
User says:  "Yesterday I go to a meeting..."
                        ↓
Alex responds naturally (no correction):
"Oh nice! How did the meeting go? I went to one last week too..."
                        ↓
End of session — one gentle tip:
"Try 'went' instead of 'go' — past tense makes you sound more natural"
```

**Three Design Principles:**

| Principle | What It Means |
|---|---|
| 🚫 Zero Judgment | No scores, no red marks, no "you should say..." |
| 🌱 Natural Modeling | AI plants correct expressions organically in replies |
| ✨ One Daily Tip | One takeaway per session — light, no pressure |

---

## Tech Stack

```
Frontend          Backend           AI Layer
──────────        ──────────        ──────────────────────
HTML/CSS/JS  ───► FastAPI      ───► Claude Sonnet / Haiku
                  (Python)          DeepSeek V3
                                    Volcengine Doubao
                                    Zhipu GLM-4-Flash
```

**Key Technical Decisions:**
- **FastAPI** — async, high-performance, auto-generated API docs
- **Multi-model support** — switch providers with one config change
- **Stateless backend** — conversation history maintained client-side
- **Prompt Engineering** — the real differentiation lives in system prompt design

---

## Project Structure

```
speakeasy/
├── main.py                  # FastAPI entry point
├── index.html               # Frontend chat UI
├── requirements.txt
├── .env.example
│
├── app/
│   ├── api/
│   │   └── chat.py          # API routes
│   ├── services/
│   │   └── model_client.py  # Multi-model client
│   └── prompts/
│       ├── system.py        # Alex persona prompt
│       └── summary.py       # Daily tip prompt
```

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/your-username/speakeasy.git
cd speakeasy
```

### 2. Install

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env` — choose one provider and fill in the key:

```bash
MODEL_PROVIDER=anthropic        # or: deepseek / volcengine / zhipu
ANTHROPIC_API_KEY=your_key_here
```

| Provider | Get API Key | Best For |
|---|---|---|
| Anthropic | https://console.anthropic.com | Best English quality |
| DeepSeek | https://platform.deepseek.com | Best value |
| Volcengine | https://console.volcengine.com/ark | China-stable |
| Zhipu GLM | https://bigmodel.cn | Free debugging |

### 4. Run

```bash
# Terminal 1 — backend
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
python3 -m http.server 3000
```

Open **http://localhost:3000/index.html**

---

## Model Pricing

| Model | Input | Output | Recommended Stage |
|---|---|---|---|
| GLM-4-Flash | Free | Free | Debugging |
| DeepSeek V3 | ¥2/M | ¥8/M | Development & launch |
| Claude Haiku 4.5 | $1/M | $5/M | Launch |
| Claude Sonnet 4.6 | $3/M | $15/M | Premium quality |

---

## API Reference

Full interactive docs at **http://localhost:8000/docs**

| Endpoint | Description |
|---|---|
| `GET /health` | Health check |
| `POST /chat` | Send message, get AI reply |
| `POST /chat/summary` | End session, generate daily tip |
| `GET /debug/status` | View current model config |

---

## Roadmap

- [x] V1 — Text chat + daily tip
- [ ] V2 — Voice input/output (Whisper + TTS)
- [ ] V2 — Cross-session memory (track recurring mistakes)
- [ ] V3 — Scene modes (workplace, travel, interview)
- [ ] V3 — Progress visualization

---

## Design Philosophy

The core insight isn't technical — it's about **user psychology**:

> Most Chinese adults have sufficient English knowledge, but freeze when speaking — not because they don't know, but because they're **afraid**.
> Every existing product optimizes for "learn faster." Nobody seriously addresses "dare to speak."

Speakeasy's differentiation isn't in features — it's in **removing that psychological barrier**.

---

## License

MIT
