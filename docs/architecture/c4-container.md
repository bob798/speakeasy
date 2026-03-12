# Speakeasy 架构图（C4 Model）

> 维护规则：每次新增或删除模块时由 Claude Code 更新此文件
> 最后更新：V0.3.1

---

## Level 1 — System Context（系统边界）

```mermaid
graph TB
    User["👤 职场学习者\n（浏览器）"]
    Speakeasy["🎯 Speakeasy\n英语练习伙伴"]
    OpenRouter["☁️ OpenRouter\nLLM 代理"]
    EdgeTTS["🔊 edge-tts\n语音合成"]
    Whisper["🎙️ faster-whisper\n语音识别"]

    User -->|练习英语对话| Speakeasy
    Speakeasy -->|LLM API 调用| OpenRouter
    Speakeasy -->|文字转语音| EdgeTTS
    Speakeasy -->|语音转文字| Whisper
```

---

## Level 2 — Container（模块组成）

```mermaid
graph TB
    subgraph Browser["浏览器"]
        Frontend["原生 HTML / JS / CSS\n对话界面 · 历史记录 · 复盘 UI"]
    end

    subgraph Backend["FastAPI Backend（Python）"]
        ChatRouter["chat_router\n/chat · /chat/summary"]
        ReviewRouter["review_router\n/review"]
        SettingsRouter["settings_router\n/settings/{user_id}"]
        VADRouter["vad_router\n/ws/vad/{user_id}"]
        ChatService["chat_service\nLLM 调用 · Prompt 构建"]
        ReviewService["review_service\n对话分析"]
        MemoryService["memory_service\nFSRS 记忆调度"]
        SettingsService["settings_service\n语速 · 音色 · 激活方式"]
        VADService["vad_service\nSilero VAD 语音检测"]
    end

    subgraph Storage["存储"]
        SQLite[("SQLite\nsessions · messages\ngrammar_cards · session_reviews\nuser_settings")]
    end

    subgraph External["外部服务"]
        OpenRouter["OpenRouter\nClaude · DeepSeek · Doubao · Zhipu"]
        EdgeTTS["edge-tts"]
        Whisper["faster-whisper"]
    end

    Frontend -->|HTTP| ChatRouter
    Frontend -->|HTTP| ReviewRouter
    Frontend -->|HTTP| SettingsRouter
    Frontend -->|WS| VADRouter
    Frontend -->|HTTP /tts| EdgeTTS
    ChatRouter --> ChatService
    ChatRouter --> MemoryService
    ReviewRouter --> ReviewService
    ReviewRouter --> MemoryService
    SettingsRouter --> SettingsService
    VADRouter --> VADService
    ChatService -->|API| OpenRouter
    ReviewService -->|API| OpenRouter
    ChatService --> SQLite
    ReviewService --> SQLite
    MemoryService --> SQLite
    SettingsService --> SQLite
    ChatRouter -->|音频流| Whisper
```

---

## Level 3 — Component（Backend 内部）

```mermaid
graph LR
    subgraph Routers["路由层"]
        CR[chat_router]
        RR[review_router]
    end

    subgraph Services["服务层"]
        CS[chat_service]
        RS[review_service]
        MS[memory_service]
        SS[settings_service]
        VS[vad_service]
    end

    subgraph Data["数据层"]
        ORM[SQLAlchemy ORM]
        DB[(SQLite)]
    end

    CR --> CS
    CR --> MS
    RR --> RS
    RR --> MS
    CS --> ORM
    RS --> ORM
    MS --> ORM
    SS --> ORM
    VS --> ORM
    ORM --> DB
```

---

## 变更记录

| 版本 | 变更内容 |
|---|---|
| V0.1 | 初始：Frontend + ChatRouter + ChatService + SQLite |
| V0.2a | 新增：STT / TTS 外部服务接入 |
| V0.2b | 新增：ReviewRouter · ReviewService · MemoryService · grammar_cards 表 · session_reviews 表 |
| V0.3.1 | 新增：SettingsRouter · SettingsService · VADRouter · VADService · user_settings 表 |

---

## 功能流程文档索引

| 流程 | 文件 | 说明 |
|---|---|---|
| 记忆调度 | [memory-flow.md](flows/memory-flow.md) | FSRS 卡片完整生命周期 |
| 对话复盘 | [review-flow.md](flows/review-flow.md) | 复盘生成、评分、历史访问 |
| 主对话   | [chat-flow.md](flows/chat-flow.md) | 消息处理、记忆注入、多模型路由 |
| 用户设置 | [settings-flow.md](flows/settings-flow.md) | 语速·音色·激活方式保存与TTS集成 |
| VAD检测  | [vad-flow.md](flows/vad-flow.md) | 实时语音检测、误触处理 |