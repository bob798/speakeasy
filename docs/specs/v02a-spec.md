# Speakeasy V0.2a 开发规格文档

> **用途：Claude Code 执行文档。每行都是指令，没有讨论。**
> 完整阅读后用 3 条说明理解摘要，按 Step 顺序执行。
> 每步通过验证命令后打印 `✅ Step N 完成` 再继续。
> 遇到文档未覆盖的情况先停下问，不自行决策。

---

## 一、版本目标

| 功能 | 说明 |
|------|------|
| 数据库持久化 | SQLite（开发）/ PostgreSQL（生产），消息不丢失 |
| 流式输出 | SSE 打字机效果 |
| 语音输入 STT | Groq Whisper API，无 Key 时降级浏览器 WebSpeech |
| 语音输出 TTS | edge-tts，失败时降级浏览器 WebSpeech |
| 对话历史 | 左侧面板，按日期分组，支持分页 |
| 用户标识 | user_id（localStorage）+ session_id（sessionStorage） |

**不在范围：** 复盘、FSRS、Level 评估、Plugin Registry、Whisper 自建、声音克隆。

---

## 二、文件结构

```
speakeasy/
├── app/
│   ├── config.py              # 新增 DATABASE_URL, GROQ_API_KEY
│   ├── database.py            # async engine + get_db() + create_tables()【新建】
│   ├── models/
│   │   └── db.py              # Session, Message ORM【新建】
│   ├── schemas/
│   │   ├── chat.py            # ChatRequest user_id/session_id 改为 Optional
│   │   ├── stt.py             # STTResponse【新建】
│   │   └── tts.py             # TTSRequest【新建】
│   ├── services/
│   │   ├── model_client.py    # 新增 chat_stream()
│   │   ├── stt_service.py     # Groq 封装【新建】
│   │   └── tts_service.py     # edge-tts + 内存缓存【新建】
│   └── routers/
│       ├── chat.py            # 升级 /chat；新增 /chat/stream
│       ├── stt.py             # /stt【新建】
│       ├── tts.py             # /tts【新建】
│       ├── history.py         # /history/...【新建】
│       └── debug.py           # /debug/status 升级
├── static/
│   ├── index.html             # 全量重写，CSS 内联
│   └── js/
│       ├── config.js          # 常量
│       ├── utils.js           # getUserId / getSessionId / showToast
│       ├── tts-provider.js    # TTSProvider + ServerTTSProvider + TTSQueue
│       ├── stt-provider.js    # STTProvider + ServerSTTProvider + WebSpeechSTTProvider
│       └── app.js             # 主逻辑（最后加载）
├── tests/
│   └── test_v02a.py
├── main.py                    # 升级：lifespan + CORS + 静态文件 + 路由
├── requirements.txt
├── .env.example
└── .gitignore
```

**index.html JS 加载顺序（底部 body，严格按此顺序）：**
```html
<script src="/static/js/config.js"></script>
<script src="/static/js/utils.js"></script>
<script src="/static/js/tts-provider.js"></script>
<script src="/static/js/stt-provider.js"></script>
<script src="/static/js/app.js"></script>
```

---

## 三、数据库设计

### app/models/db.py

```python
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Session(Base):
    __tablename__ = "sessions"
    id         : Mapped[str]                = mapped_column(String, primary_key=True)
    user_id    : Mapped[str]                = mapped_column(String, index=True)
    created_at : Mapped[datetime]           = mapped_column(default=func.now())
    ended_at   : Mapped[Optional[datetime]] = mapped_column(nullable=True)
    messages   : Mapped[List["Message"]]    = relationship(
        back_populates="session",
        order_by="Message.created_at",
        cascade="all, delete-orphan"
    )

class Message(Base):
    __tablename__ = "messages"
    id         : Mapped[int]       = mapped_column(primary_key=True, autoincrement=True)
    session_id : Mapped[str]       = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    role       : Mapped[str]       = mapped_column(String(16))  # "user" | "assistant"
    content    : Mapped[str]
    created_at : Mapped[datetime]  = mapped_column(default=func.now())
    session    : Mapped["Session"] = relationship(back_populates="messages")
```

### app/database.py

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings
from app.models.db import Base

_url = settings.DATABASE_URL or "sqlite+aiosqlite:///./speakeasy.db"
_sqlite = "sqlite" in _url

engine = create_async_engine(
    _url,
    echo=False,
    connect_args={"check_same_thread": False} if _sqlite else {}
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

---

## 四、API 完整契约

### POST /chat（向后兼容升级）
```
Request:
{
    "user_id":    "string | null",   ← Optional；null 时跳过 DB 写入
    "session_id": "string | null",   ← Optional
    "message":    "string",
    "history":    []
}
Response: { "reply": "string", "session_id": "string", "request_id": "string" }
```

### POST /chat/stream（新增）
```
Request: 同 /chat
Response: text/event-stream

data: {"type": "delta",  "content": "Hey"}\n\n
data: {"type": "done",   "session_id": "xxx", "message_id": 42}\n\n
data: {"type": "error",  "message": "..."}\n\n

必须响应头：
  Content-Type: text/event-stream
  Cache-Control: no-cache
  X-Accel-Buffering: no
```

### POST /stt（新增）
```
Request: multipart/form-data，字段名 "audio"，最大 25MB
         支持格式：webm / mp4 / wav / ogg / mp3
注意：全程 in-memory 处理，不写磁盘临时文件

Response 200: { "text": "识别文字", "duration": 8.3 }
Response 503: { "error": "STT_NOT_CONFIGURED", "fallback": "webspeech" }
Response 429: { "error": "STT_RATE_LIMITED", "retry_after": 60, "fallback": "webspeech" }
```

### POST /tts（新增）
```
Request:
{
    "text":  "string（最多 1000 字符，截断不报错）",
    "voice": "jenny（默认）| guy | sonia"
}

voice 映射：
  jenny → en-US-JennyNeural
  guy   → en-US-GuyNeural
  sonia → en-GB-SoniaNeural

Response 200: audio/mpeg binary，Header: Cache-Control: public, max-age=3600
Response 503: { "error": "TTS_FAILED", "fallback": "webspeech" }
```

### GET /history/{user_id}（新增）
```
Query: ?limit=20&offset=0（limit 默认 20，最大 100）

Response 200:
{
    "sessions": [
        {
            "id":         "uuid",
            "created_at": "2025-03-06T14:30:00Z",
            "ended_at":   "2025-03-06T14:45:00Z",  ← null 表示进行中
            "preview":    "I had a tough day..."    ← 第一条 user 消息前 20 字
        }
    ],
    "total": 42,
    "limit": 20,
    "offset": 0
}
```

### GET /history/{session_id}/messages（新增）
```
Response 200:
{
    "session_id": "uuid",
    "messages": [
        { "id": 1, "role": "user", "content": "...", "created_at": "..." }
    ]
}
```

### GET /debug/status（升级）
```
Response 200:
{
    "status":              "ok",
    "model":               "claude-3-5-sonnet",
    "db":                  "connected",
    "stt_available":       true,
    "tts_available":       true,
    "groq_key_configured": true
}
```

---

## 五、后端关键实现

### app/config.py 新增字段
```python
DATABASE_URL:     str  = ""     # 空 = SQLite
GROQ_API_KEY:     str  = ""     # 空 = STT 降级 WebSpeech
ENABLE_STREAMING: bool = True
```

### main.py 完整结构
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.database import create_tables
from app.routers import chat, stt, tts, history, debug

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(stt.router)
app.include_router(tts.router)
app.include_router(history.router)
app.include_router(debug.router)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")
```

### app/services/stt_service.py
```python
import io
from groq import AsyncGroq
from app.config import settings

MIME_MAP = {
    "webm": "audio/webm", "mp4": "audio/mp4", "m4a": "audio/mp4",
    "wav":  "audio/wav",  "ogg": "audio/ogg", "mp3": "audio/mpeg"
}

async def transcribe_audio(audio_bytes: bytes, filename: str) -> dict:
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not configured")

    ext  = filename.rsplit(".", 1)[-1].lower()
    mime = MIME_MAP.get(ext, "audio/webm")

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    result = await client.audio.transcriptions.create(
        model="whisper-large-v3",
        file=(filename, io.BytesIO(audio_bytes), mime),  # 全程 in-memory
        language="en",
        response_format="verbose_json"
    )
    return {
        "text":     result.text.strip(),
        "duration": getattr(result, "duration", 0.0)
    }
```

### app/services/tts_service.py
```python
import io, edge_tts

VOICES = {
    "jenny": "en-US-JennyNeural",
    "guy":   "en-US-GuyNeural",
    "sonia": "en-GB-SoniaNeural",
}

_cache: dict = {}
_CACHE_MAX = 50

async def text_to_speech(text: str, voice_key: str = "jenny") -> bytes:
    voice     = VOICES.get(voice_key, VOICES["jenny"])
    cache_key = f"{voice}::{text}"

    if cache_key in _cache:
        return _cache[cache_key]

    buf = io.BytesIO()
    async for chunk in edge_tts.Communicate(text, voice).stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])

    audio = buf.getvalue()
    if not audio:
        raise RuntimeError("edge-tts returned empty audio")

    if len(_cache) >= _CACHE_MAX:
        for k in list(_cache)[:10]:
            del _cache[k]
    _cache[cache_key] = audio
    return audio
```

### app/services/model_client.py 新增
```python
from typing import AsyncGenerator

class BaseModelClient:
    def chat(self, message: str, history: list) -> str:
        raise NotImplementedError
    async def chat_stream(self, message: str, history: list) -> AsyncGenerator[str, None]:
        raise NotImplementedError

class AnthropicClient(BaseModelClient):
    async def chat_stream(self, message, history):
        with self.client.messages.stream(
            model=self.model, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT,
            messages=history + [{"role": "user", "content": message}]
        ) as stream:
            for text in stream.text_stream:
                yield text

class OpenAICompatibleClient(BaseModelClient):
    async def chat_stream(self, message, history):
        resp = self.client.chat.completions.create(
            model=self.model, max_tokens=MAX_TOKENS, stream=True,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
                     + history + [{"role": "user", "content": message}]
        )
        for chunk in resp:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
```

### app/routers/chat.py — /chat/stream 核心逻辑
```python
@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    if req.user_id and req.session_id:
        await upsert_session(db, req.session_id, req.user_id)
        await save_message(db, req.session_id, "user", req.message)

    async def generate():
        full = []
        try:
            async for chunk in model_client.chat_stream(req.message, req.history):
                full.append(chunk)
                yield f"data: {json.dumps({'type':'delta','content':chunk})}\n\n"

            content = "".join(full)
            msg_id  = None
            if req.session_id:
                msg    = await save_message(db, req.session_id, "assistant", content)
                msg_id = msg.id

            yield f"data: {json.dumps({'type':'done','session_id':req.session_id,'message_id':msg_id})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
```

### app/routers/history.py — 分页 + 懒更新
```python
from datetime import datetime, timedelta
STALE = timedelta(hours=2)

@router.get("/history/{user_id}")
async def get_history(
    user_id: str,
    limit:   int = Query(default=20, ge=1, le=100),
    offset:  int = Query(default=0,  ge=0),
    db: AsyncSession = Depends(get_db)
):
    # 懒更新：超 2 小时的活跃 session 补齐 ended_at
    stale = await db.execute(
        select(Session)
        .where(Session.user_id == user_id, Session.ended_at == None)
        .options(selectinload(Session.messages))
    )
    now = datetime.utcnow()
    for s in stale.scalars():
        if s.messages:
            last = max(m.created_at for m in s.messages)
            if now - last > STALE:
                s.ended_at = last
    await db.commit()

    total = (await db.execute(
        select(func.count()).where(Session.user_id == user_id)
    )).scalar()

    rows = (await db.execute(
        select(Session)
        .where(Session.user_id == user_id)
        .options(selectinload(Session.messages))
        .order_by(Session.created_at.desc())
        .limit(limit).offset(offset)
    )).scalars().all()

    def preview(s):
        first = next((m for m in s.messages if m.role == "user"), None)
        if first:
            t = first.content[:20]
            return t + ("..." if len(first.content) > 20 else "")
        return f"对话 · {s.created_at.strftime('%H:%M')}"

    return {
        "sessions": [
            {
                "id":         s.id,
                "created_at": s.created_at.isoformat() + "Z",
                "ended_at":   (s.ended_at.isoformat() + "Z") if s.ended_at else None,
                "preview":    preview(s)
            } for s in rows
        ],
        "total": total, "limit": limit, "offset": offset
    }
```

---

## 六、前端关键实现

### static/js/utils.js
```javascript
function getUserId() {
    let id = localStorage.getItem('speakeasy_uid');
    if (!id) { id = crypto.randomUUID(); localStorage.setItem('speakeasy_uid', id); }
    return id;
}

function getSessionId() {
    let id = sessionStorage.getItem('speakeasy_sid');
    if (!id) { id = crypto.randomUUID(); sessionStorage.setItem('speakeasy_sid', id); }
    return id;
}

function newSession() {
    sessionStorage.removeItem('speakeasy_sid');
    return getSessionId();
}

function showToast(msg, type = 'info', duration = 3000) {
    document.querySelector('.toast')?.remove();
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = msg;
    document.body.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 300); }, duration);
}

function showBanner(msg) {
    const b = document.getElementById('compat-banner');
    document.getElementById('compat-msg').textContent = msg;
    b.style.display = 'flex';
}
```

### static/js/stt-provider.js
```javascript
class STTProvider {
    isSupported() { return false; }
    async start(onInterim, onFinal, onError) {}
    stop() {} cancel() {}
}

class ServerSTTProvider extends STTProvider {
    constructor() {
        super();
        this.mimeType = ['audio/webm;codecs=opus','audio/webm','audio/mp4','audio/ogg;codecs=opus','']
            .find(t => t === '' || MediaRecorder.isTypeSupported(t));
    }
    _ext() {
        if (this.mimeType.includes('webm')) return 'webm';
        if (this.mimeType.includes('mp4'))  return 'mp4';
        if (this.mimeType.includes('ogg'))  return 'ogg';
        return 'webm';
    }
    isSupported() {
        return !!(navigator.mediaDevices?.getUserMedia) &&
               (location.protocol === 'https:' || location.hostname === 'localhost');
    }
    async start(onInterim, onFinal, onError) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.recorder = new MediaRecorder(stream, this.mimeType ? { mimeType: this.mimeType } : {});
            this.chunks = [];
            this.recorder.ondataavailable = e => { if (e.data.size > 0) this.chunks.push(e.data); };
            this.recorder.onstop = async () => {
                stream.getTracks().forEach(t => t.stop());
                const blob = new Blob(this.chunks, { type: this.mimeType || 'audio/webm' });
                const form = new FormData();
                form.append('audio', blob, `rec.${this._ext()}`);
                onInterim('识别中...');
                try {
                    const res  = await fetch('/stt', { method: 'POST', body: form });
                    const data = await res.json();
                    if (data.fallback === 'webspeech') { onError({ type: 'FALLBACK' }); return; }
                    if (data.text) onFinal(data.text);
                    else onError({ type: 'EMPTY' });
                } catch (e) { onError({ type: 'NETWORK' }); }
            };
            this.recorder.start();
            this.timeout = setTimeout(() => this.stop(), 10000);
        } catch (e) {
            onError({ type: e.name === 'NotAllowedError' ? 'PERMISSION_DENIED' : 'UNKNOWN' });
        }
    }
    stop()   { clearTimeout(this.timeout); if (this.recorder?.state === 'recording') this.recorder.stop(); }
    cancel() {
        clearTimeout(this.timeout);
        if (this.recorder?.state === 'recording') {
            this.recorder.ondataavailable = null;
            this.recorder.onstop = null;
            this.recorder.stream?.getTracks().forEach(t => t.stop());
            this.recorder.stop();
        }
    }
}

class WebSpeechSTTProvider extends STTProvider {
    isSupported() { return !!(window.SpeechRecognition || window.webkitSpeechRecognition); }
    async start(onInterim, onFinal, onError) {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.rec = new SR();
        this.rec.lang = 'en-US';
        this.rec.interimResults = true;
        this.rec.onresult = e => {
            const t = Array.from(e.results).map(r => r[0].transcript).join('');
            if (e.results[e.results.length - 1].isFinal) onFinal(t); else onInterim(t);
        };
        this.rec.onerror = e => onError({ type: e.error });
        this.rec.start();
        this.timeout = setTimeout(() => this.stop(), 10000);
    }
    stop()   { clearTimeout(this.timeout); this.rec?.stop(); }
    cancel() { clearTimeout(this.timeout); this.rec?.abort(); }
}

// 工厂（V0.3 只改这里）
function createSTTProvider() { return new ServerSTTProvider(); }
```

### static/js/tts-provider.js
```javascript
class TTSProvider {
    isSupported() { return false; }
    async speak(text, onStart, onEnd, onError) {}
    stop() {}
}

class ServerTTSProvider extends TTSProvider {
    isSupported() { return true; }
    async speak(text, onStart, onEnd, onError) {
        try {
            const res = await fetch('/tts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text })
            });
            if (!res.ok) {
                const d = await res.json();
                if (d.fallback === 'webspeech') { this._ws(text, onStart, onEnd, onError); return; }
                throw new Error(d.error);
            }
            const url = URL.createObjectURL(await res.blob());
            this._audio = new Audio(url);
            this._audio.onplay  = onStart;
            this._audio.onended = () => { URL.revokeObjectURL(url); this._audio = null; onEnd(); };
            this._audio.onerror = onError;
            await this._audio.play();
        } catch (e) { onError(e); }
    }
    stop() { if (this._audio) { this._audio.pause(); this._audio.src = ''; this._audio = null; } }
    _ws(text, onStart, onEnd, onError) {
        if (!window.speechSynthesis) { onEnd(); return; }
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(text);
        u.lang = 'en-US'; u.rate = 0.9;
        const v = speechSynthesis.getVoices().find(v => v.lang.startsWith('en'));
        if (v) u.voice = v;
        u.onstart = onStart; u.onend = onEnd; u.onerror = onError;
        speechSynthesis.speak(u);
    }
}

class TTSQueue {
    constructor(provider) { this.p = provider; this.q = []; this.busy = false; }
    enqueue(text, manual = false) {
        if (manual) { this.q = []; this.p.stop(); this.busy = false; }
        this.q.push(text);
        if (!this.busy) this._next();
    }
    clear() { this.q = []; this.p.stop(); this.busy = false; }
    async _next() {
        if (!this.q.length) { this.busy = false; return; }
        this.busy = true;
        await new Promise(r => this.p.speak(this.q.shift(), () => {}, r, r));
        this._next();
    }
}

// 工厂（V0.3 只改这里）
function createTTSProvider() { return new ServerTTSProvider(); }
```

### static/js/app.js（核心流程）
```javascript
const userId      = getUserId();
let   sessionId   = getSessionId();
const ttsQueue    = new TTSQueue(createTTSProvider());
let   sttProvider = null;
let   autoPlay    = false;
let   sttState    = 'idle';   // idle | recording | processing
let   chatHistory = [];       // [{role, content}]

// ── 初始化 ──────────────────────────────────────
window.addEventListener('DOMContentLoaded', async () => {
    await initSTT();
    await loadHistory();

    document.getElementById('autoplay-btn').addEventListener('click', function () {
        autoPlay = !autoPlay;
        this.setAttribute('aria-checked', autoPlay);
        if (!autoPlay) ttsQueue.clear();
    });
});

async function initSTT() {
    const server = createSTTProvider();
    if (!navigator.mediaDevices?.getUserMedia) {
        showBanner('您的浏览器不支持录音，请使用 Chrome / Edge');
        hideMicBtn(); return;
    }
    if (!server.isSupported()) {
        showBanner('录音功能需要 HTTPS（本地开发请用 localhost）');
        hideMicBtn(); return;
    }
    try {
        const status = await fetch('/debug/status').then(r => r.json());
        if (!status.stt_available) {
            const ws = new WebSpeechSTTProvider();
            if (ws.isSupported()) {
                showBanner('未设置 GROQ_API_KEY，使用浏览器内置识别（仅 Chrome）');
                sttProvider = ws;
            } else {
                showBanner('未设置 GROQ_API_KEY，且浏览器不支持 WebSpeech');
                hideMicBtn();
            }
            return;
        }
    } catch (e) { /* 服务未启动时忽略 */ }
    sttProvider = server;
}

// ── 发送消息 ──────────────────────────────────────
async function sendMessage(text) {
    if (!text.trim()) return;
    setInput('');
    appendBubble('user', text);
    chatHistory.push({ role: 'user', content: text });

    const bubbleId = appendBubble('ai', '', true);  // streaming=true 显示光标

    try {
        const res = await fetch('/chat/stream', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId, session_id: sessionId,
                message: text,   history: chatHistory.slice(-10)
            })
        });

        const reader = res.body.getReader();
        const dec    = new TextDecoder();
        let buf = '', full = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += dec.decode(value, { stream: true });
            const parts = buf.split('\n\n');
            buf = parts.pop();

            for (const part of parts) {
                if (!part.startsWith('data: ')) continue;
                const d = JSON.parse(part.slice(6));

                if (d.type === 'delta') {
                    full += d.content;
                    updateBubble(bubbleId, full, true);

                } else if (d.type === 'done') {
                    updateBubble(bubbleId, full, false);
                    attachTTSBtn(bubbleId, full);
                    chatHistory.push({ role: 'assistant', content: full });
                    if (autoPlay) ttsQueue.enqueue(full);
                    setTimeout(loadHistory, 500);  // 延迟刷新历史列表

                } else if (d.type === 'error') {
                    showToast(d.message, 'error');
                    removeBubble(bubbleId);
                }
            }
        }
    } catch (e) {
        showToast('网络错误，请重试', 'error');
        removeBubble(bubbleId);
    }
}

// ── 录音状态机 ──────────────────────────────────────
function onMicClick() {
    if (!sttProvider) return;

    if (sttState === 'idle') {
        sttState = 'recording';
        setMicState('recording');
        sttProvider.start(
            (interim) => setInputPlaceholder(interim),
            (text)    => {
                sttState = 'idle';
                setMicState('idle');
                setInput(text);
                sendMessage(text);
            },
            (err)     => {
                sttState = 'idle';
                setMicState('idle');
                if (err.type === 'PERMISSION_DENIED')
                    showToast('请在浏览器地址栏允许麦克风权限', 'error');
                else if (err.type === 'FALLBACK') {
                    sttProvider = new WebSpeechSTTProvider();
                    showToast('已切换到浏览器内置识别');
                } else {
                    showToast('识别失败，请重试', 'error');
                }
            }
        );
    } else if (sttState === 'recording') {
        sttProvider.stop();
        sttState = 'processing';
        setMicState('processing');
    }
}

// ── 历史面板 ──────────────────────────────────────
async function loadHistory() {
    try {
        const data = await fetch(`/history/${userId}?limit=20`).then(r => r.json());
        renderHistoryList(data.sessions);
    } catch (e) {}
}

async function openHistorySession(sid) {
    const data = await fetch(`/history/${sid}/messages`).then(r => r.json());
    renderReadonlyChat(data.messages, data.session_id);
}

function onNewChat() {
    sessionId    = newSession();
    chatHistory  = [];
    clearChatArea();
    setMode('chat');
}

function onSend() {
    const text = getInput().trim();
    if (text) sendMessage(text);
}
```

---

## 七、UI 设计规范

### CSS 变量
```css
:root {
    --bg-base:     #0a0a0f;
    --bg-surface:  #13131a;
    --bg-elevated: #1c1c28;
    --bg-overlay:  #242435;

    --bubble-user:         #1e1b3a;
    --bubble-ai:           #161620;
    --bubble-user-border:  rgba(124,106,247,0.25);
    --bubble-ai-border:    rgba(255,255,255,0.06);

    --accent:      #7c6af7;
    --accent-light:#9d8fff;
    --accent-dim:  rgba(124,106,247,0.15);

    --recording:   #ff4757;
    --success:     #2ed573;
    --warning:     #ffa502;

    --text-primary:   #e8e8f0;
    --text-secondary: #8888aa;
    --text-muted:     #555566;

    --radius-sm:   8px;
    --radius-md:   12px;
    --radius-lg:   18px;
    --radius-full: 9999px;
}
```

### 布局
```css
body { margin:0; font-family:'DM Sans',sans-serif; background:var(--bg-base); color:var(--text-primary); }

.layout {
    display: grid;
    grid-template-columns: 260px 1fr;
    grid-template-rows: 56px 1fr 72px;
    height: 100vh;
    overflow: hidden;
}
.header    { grid-column:1/-1; grid-row:1; background:var(--bg-surface); border-bottom:1px solid rgba(255,255,255,.06); display:flex; align-items:center; padding:0 20px; justify-content:space-between; }
.sidebar   { grid-column:1; grid-row:2/4; background:var(--bg-surface); border-right:1px solid rgba(255,255,255,.06); overflow-y:auto; }
.chat-area { grid-column:2; grid-row:2; overflow-y:auto; padding:24px; display:flex; flex-direction:column; gap:16px; }
.input-bar { grid-column:2; grid-row:3; background:var(--bg-surface); border-top:1px solid rgba(255,255,255,.06); padding:12px 20px; display:flex; align-items:center; gap:10px; }
```

### 字体（head 中引入）
```html
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
```

### 关键动效
```css
/* 流式光标 */
.streaming::after { content:'▋'; color:var(--accent); animation:blink .8s step-end infinite; margin-left:2px; }
@keyframes blink { 50% { opacity:0; } }

/* 录音脉冲 */
.mic-recording { background:var(--recording) !important; animation:pulse 1.5s ease-out infinite; }
@keyframes pulse { 0%{box-shadow:0 0 0 0 rgba(255,71,87,.6);} 70%{box-shadow:0 0 0 14px rgba(255,71,87,0);} 100%{box-shadow:0 0 0 0 rgba(255,71,87,0);} }

/* TTS 音波 */
.wave { display:flex; align-items:center; gap:2px; height:16px; }
.wave span { width:3px; background:var(--accent-light); border-radius:2px; animation:wave .8s ease infinite; }
.wave span:nth-child(2) { animation-delay:.15s; }
.wave span:nth-child(3) { animation-delay:.3s; }
@keyframes wave { 0%,100%{transform:scaleY(.6);} 50%{transform:scaleY(1.2);} }

/* 气泡入场 */
.bubble { animation:pop .2s cubic-bezier(.34,1.56,.64,1); }
@keyframes pop { from{opacity:0;transform:translateY(8px) scale(.97);} to{opacity:1;transform:none;} }

/* 气泡 */
.bubble-user { background:var(--bubble-user); border:1px solid var(--bubble-user-border); border-radius:18px 18px 4px 18px; padding:12px 16px; max-width:75%; align-self:flex-end; }
.bubble-ai   { background:var(--bubble-ai);   border:1px solid var(--bubble-ai-border);   border-radius:18px 18px 18px 4px; padding:12px 16px; max-width:85%; align-self:flex-start; position:relative; }

/* Toast */
.toast { position:fixed; bottom:88px; left:50%; transform:translateX(-50%) translateY(20px); opacity:0; transition:all .25s cubic-bezier(.34,1.56,.64,1); background:var(--bg-overlay); border:1px solid rgba(255,255,255,.1); border-radius:var(--radius-full); padding:10px 20px; font-size:14px; z-index:1000; white-space:nowrap; pointer-events:none; }
.toast.show { opacity:1; transform:translateX(-50%) translateY(0); }
.toast.error   { border-color:rgba(255,71,87,.4); color:#ff6b7a; }
.toast.success { border-color:rgba(46,213,115,.4); color:#2ed573; }

/* Banner */
.compat-banner { background:rgba(255,165,0,.1); border-bottom:1px solid rgba(255,165,0,.3); padding:8px 20px; font-size:13px; color:var(--warning); display:flex; justify-content:space-between; align-items:center; }

/* Toggle */
.toggle-btn { width:40px; height:22px; border-radius:11px; background:var(--bg-elevated); border:none; cursor:pointer; position:relative; transition:background .2s; padding:0; }
.toggle-btn[aria-checked="true"] { background:var(--accent); }
.toggle-thumb { position:absolute; top:3px; left:3px; width:16px; height:16px; border-radius:50%; background:#fff; transition:transform .2s; display:block; }
.toggle-btn[aria-checked="true"] .toggle-thumb { transform:translateX(18px); }

/* 输入框 */
.input-box { flex:1; background:var(--bg-elevated); border:1px solid rgba(255,255,255,.08); border-radius:var(--radius-lg); padding:10px 16px; font-size:15px; color:var(--text-primary); resize:none; outline:none; font-family:inherit; max-height:120px; overflow-y:auto; transition:border-color .2s; }
.input-box:focus { border-color:rgba(124,106,247,.4); }

/* 历史 */
.history-item { padding:10px 16px; cursor:pointer; border-radius:var(--radius-md); margin:2px 8px; transition:background .15s; }
.history-item:hover  { background:var(--bg-elevated); }
.history-item.active { background:var(--accent-dim); }
.history-preview { font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.history-time    { font-size:11px; color:var(--text-muted); margin-top:2px; }
.history-group-label { font-size:11px; font-weight:600; color:var(--text-muted); padding:12px 16px 4px; text-transform:uppercase; letter-spacing:.08em; }
```

### index.html 骨架
```html
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>Speakeasy</title>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
    <style>/* 全部 CSS 粘贴在此 */</style>
</head>
<body>

<div id="compat-banner" class="compat-banner" style="display:none">
    <span id="compat-msg"></span>
    <button onclick="this.parentElement.style.display='none'" style="background:none;border:none;cursor:pointer;color:inherit;font-size:16px">✕</button>
</div>

<div class="layout">

    <header class="header">
        <div style="display:flex;align-items:center;gap:10px">
            <span style="font-size:20px">🗣</span>
            <span style="font-weight:600;font-size:16px;letter-spacing:-.01em">Speakeasy</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
            <span style="font-size:13px;color:var(--text-secondary)">自动朗读</span>
            <button id="autoplay-btn" class="toggle-btn" role="switch" aria-checked="false">
                <span class="toggle-thumb"></span>
            </button>
        </div>
    </header>

    <aside class="sidebar">
        <div style="padding:16px 16px 8px;display:flex;justify-content:space-between;align-items:center">
            <span style="font-size:12px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.08em">历史对话</span>
            <button id="new-chat-btn" onclick="onNewChat()"
                style="font-size:12px;padding:4px 10px;border-radius:var(--radius-full);background:var(--accent-dim);color:var(--accent);border:none;cursor:pointer;font-family:inherit">
                + 新对话
            </button>
        </div>
        <div id="history-list"></div>
    </aside>

    <main class="chat-area" id="chat-area"></main>

    <div class="input-bar">
        <button id="mic-btn" onclick="onMicClick()"
            style="width:40px;height:40px;border-radius:50%;border:none;cursor:pointer;background:var(--bg-elevated);color:var(--text-secondary);font-size:18px;flex-shrink:0;transition:all .2s"
            title="录音">🎤</button>

        <textarea id="input-box" class="input-box" rows="1"
            placeholder="和 Alex 说点什么..."
            onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();onSend()}"
            oninput="this.style.height='auto';this.style.height=Math.min(this.scrollHeight,120)+'px'"></textarea>

        <button onclick="onSend()"
            style="width:40px;height:40px;border-radius:50%;border:none;cursor:pointer;background:var(--accent);color:#fff;font-size:18px;flex-shrink:0;transition:opacity .2s">↑</button>
    </div>

</div>

<script src="/static/js/config.js"></script>
<script src="/static/js/utils.js"></script>
<script src="/static/js/tts-provider.js"></script>
<script src="/static/js/stt-provider.js"></script>
<script src="/static/js/app.js"></script>
</body>
</html>
```

---

## 八、执行步骤

### Step 0：依赖安装
```bash
pip install sqlalchemy==2.0.36 aiosqlite==0.20.0 asyncpg==0.30.0 groq edge-tts python-multipart
```
requirements.txt 新增以上依赖；.env.example 新增 `DATABASE_URL=` `GROQ_API_KEY=` `ENABLE_STREAMING=true`；.gitignore 新增 `*.db`。

**验证：**
```bash
python -c "import sqlalchemy,aiosqlite,groq,edge_tts,multipart; print('✅ Step 0 完成')"
```

---

### Step 1：app/config.py 新增字段
新增 `DATABASE_URL`、`GROQ_API_KEY`、`ENABLE_STREAMING`（见第五章）。

**验证：**
```bash
python -c "from app.config import settings; assert hasattr(settings,'GROQ_API_KEY'); print('✅ Step 1 完成')"
```

---

### Step 2：数据库层
新建 `app/models/db.py`、`app/database.py`（见第三章完整代码）。

**验证：**
```bash
python -c "
import asyncio, sqlalchemy as sa
from app.database import create_tables, engine
async def t():
    await create_tables()
    async with engine.connect() as c:
        r = await c.execute(sa.text(\"SELECT name FROM sqlite_master WHERE type='table'\"))
        tables = [row[0] for row in r]
        assert 'sessions' in tables and 'messages' in tables, tables
        print('✅ Step 2 完成 - 表:', tables)
asyncio.run(t())
"
```

---

### Step 3：升级 main.py
加入 lifespan + CORS + 静态文件 + 根路由 + 注册所有新路由（见第五章完整结构）。

**验证：**
```bash
python -c "
from main import app
paths = [r.path for r in app.routes if hasattr(r,'path')]
for p in ['/stt','/tts','/history/{user_id}','/']:
    assert p in paths, f'路由缺失: {p}'
print('✅ Step 3 完成 - 路由:', [p for p in paths if not p.startswith('/openapi')])
"
```

---

### Step 4：升级 /chat 接口
schemas/chat.py：`user_id`、`session_id` 改为 Optional。
routers/chat.py：有 user_id+session_id 时写 DB，无时跳过（向后兼容）。

**验证（需启动服务）：**
```bash
# 含 user_id
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u1","session_id":"s1","message":"hi","history":[]}' | python -m json.tool

# 不含 user_id（旧格式向后兼容）
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"hi","history":[]}' | python -m json.tool

sqlite3 speakeasy.db "SELECT role,substr(content,1,30) FROM messages;" && echo "✅ Step 4 完成"
```

---

### Step 5：model_client.py 新增 chat_stream()
各 Client 实现异步生成器 `chat_stream()`（见第五章代码）。

**验证：**
```bash
python -c "
import asyncio
from app.services.model_client import get_model_client
async def t():
    c = get_model_client(); out = []
    async for chunk in c.chat_stream('reply with just: ok', []):
        out.append(chunk)
    assert out, '输出为空'
    print('输出:', ''.join(out)[:60])
    print('✅ Step 5 完成')
asyncio.run(t())
"
```

---

### Step 6：/chat/stream 路由
routers/chat.py 新增 `/chat/stream`（见第五章核心逻辑）。

**验证：**
```bash
curl -sN -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u1","session_id":"s2","message":"count 1 2 3","history":[]}' \
  --max-time 15 | grep '"type"'
echo "✅ Step 6 完成"
```

---

### Step 7：STT 服务 + /stt 路由
新建 `app/services/stt_service.py`、`app/routers/stt.py`（见第五章）。

**验证：**
```bash
# 无 API Key → 503 + fallback 信号
curl -s -X POST http://localhost:8000/stt \
  -F "audio=@/dev/null;filename=t.webm" | python -m json.tool
echo "✅ Step 7 完成"
```

---

### Step 8：TTS 服务 + /tts 路由
新建 `app/services/tts_service.py`、`app/routers/tts.py`（见第五章）。

**验证：**
```bash
curl -s -X POST http://localhost:8000/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello!"}' --output /tmp/tts.mp3

python -c "
d = open('/tmp/tts.mp3','rb').read()
assert len(d) > 500, f'文件异常: {len(d)} bytes'
print(f'音频大小: {len(d)} bytes')
print('✅ Step 8 完成')
"
```

---

### Step 9：/history 路由
新建 `app/routers/history.py`（见第五章完整代码，含分页 + 懒更新）。

**验证：**
```bash
curl -s "http://localhost:8000/history/u1?limit=20" | python -m json.tool
curl -s "http://localhost:8000/history/s1/messages" | python -m json.tool
echo "✅ Step 9 完成"
```

---

### Step 10：升级 /debug/status
routers/debug.py 新增 `db`、`stt_available`、`tts_available`、`groq_key_configured` 字段。

**验证：**
```bash
curl -s http://localhost:8000/debug/status | python -m json.tool
python -c "
import requests, sys
d = requests.get('http://localhost:8000/debug/status').json()
for f in ['db','stt_available','tts_available']:
    assert f in d, f'缺字段: {f}'
print('✅ Step 10 完成')
"
```

---

### Step 11：前端全量重写
按第六、七章实现所有文件，**创建顺序**：
1. `static/js/config.js`（常量：API 路径等）
2. `static/js/utils.js`
3. `static/js/tts-provider.js`
4. `static/js/stt-provider.js`
5. `static/js/app.js`（补充 DOM 辅助函数：appendBubble / updateBubble / removeBubble / attachTTSBtn / setMicState / setInput / getInput / clearChatArea / setMode / hideMicBtn / renderHistoryList / renderReadonlyChat）
6. `static/index.html`（CSS 内联，JS 按顺序引入）

**验证（人工，Chrome）：**
- [ ] 访问 `http://localhost:8000/`，页面正常加载
- [ ] 发消息，回复逐字出现，完成后光标消失
- [ ] 点 🔊 有声音
- [ ] 点 🎤 按钮变红脉冲，说话后识别文字填入并发送
- [ ] 刷新，历史侧边栏出现之前对话
- [ ] 点「新对话」清空聊天区

```
✅ Step 11 完成
```

---

### Step 12：集成测试
新建 `tests/test_v02a.py`：

```python
import asyncio, httpx

BASE = "http://localhost:8000"

async def run():
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as c:
        # 根路由
        assert (await c.get("/")).status_code == 200

        # chat 含 user_id
        r = await c.post("/chat", json={"user_id":"t","session_id":"ts","message":"hi","history":[]})
        assert r.status_code == 200 and "reply" in r.json()

        # chat 无 user_id（向后兼容）
        r = await c.post("/chat", json={"message":"hi","history":[]})
        assert r.status_code == 200

        # stream
        chunks = []
        async with c.stream("POST","/chat/stream",
            json={"user_id":"t","session_id":"ts2","message":"say hi","history":[]}) as r:
            async for line in r.aiter_lines():
                if line.startswith("data:"): chunks.append(line)
        assert any("done" in l for l in chunks), "stream 无 done 事件"

        # stt（无 Key → 降级）
        r = await c.post("/stt", files={"audio": ("t.webm", b"\x00"*100, "audio/webm")})
        assert r.status_code in (200, 503)

        # tts
        r = await c.post("/tts", json={"text":"hello"})
        assert r.status_code == 200 and "audio" in r.headers.get("content-type","")

        # history（含分页字段）
        r = await c.get("/history/t")
        d = r.json()
        assert "sessions" in d and "total" in d and "limit" in d

        # debug
        d = (await c.get("/debug/status")).json()
        for f in ["db","stt_available","tts_available"]:
            assert f in d, f"debug 缺字段: {f}"

        print("✅ Step 12 完成 - 全部测试通过")

asyncio.run(run())
```

**执行：**
```bash
python tests/test_v02a.py
```

---

## 九、验收标准

### 接口（自动）
- [ ] `GET /` 返回 index.html
- [ ] `POST /chat` 写 DB；无 user_id 时正常响应
- [ ] `POST /chat/stream` 含 delta + done 事件
- [ ] `POST /stt` 有 Key 返回文字；无 Key 返回 fallback 信号
- [ ] `POST /tts` 返回 audio/mpeg
- [ ] `GET /history/{user_id}` 含 sessions/total/limit/offset
- [ ] `GET /history/{session_id}/messages` 含消息列表
- [ ] `GET /debug/status` 含 db/stt_available/tts_available

### 行为（Chrome 人工）
- [ ] 流式回复逐字出现，结束后光标消失
- [ ] 🔊 朗读；快速点多个按序播放；自动朗读开关生效
- [ ] 录音红色脉冲；识别后填入并发送
- [ ] 无 GROQ_API_KEY 时 Banner 提示，文字输入不受影响
- [ ] 历史按日期分组；点击展示只读对话
- [ ] 「新对话」清空聊天区
- [ ] Toast 3 秒消失