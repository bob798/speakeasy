# 主对话流程（Chat Flow）

> 描述：从用户发送消息到 Alex 流式回复的完整数据流，含记忆注入与多模型路由
> 涉及模块：chat_router · memory_service · model_client · sessions 表 · messages 表 · grammar_cards 表
> 最后更新：V0.2b

---

## 一、全局流程概览

```mermaid
flowchart TD
    A([用户输入消息\n文字 / 语音]) --> B{输入类型}

    B -->|语音| C[STT\nGroq Whisper / WebSpeech]
    B -->|文字| D[直接进入发送流程]
    C --> D

    D --> E[Frontend\nsendMessage]
    E --> F[POST /chat/stream\n携带 session_id · user_id · history]

    F --> G[upsert_session\n确保 Session 记录存在]
    G --> H[save_message user\n持久化用户消息]
    H --> I[memory_service\nbuild_system_prompt]

    I --> J{active cards\n且 due <= now?}
    J -->|有| K[注入记忆到 system prompt\n最多 3 张卡片]
    J -->|无| L[使用基础 SYSTEM_PROMPT]

    K --> M[model_client\nchat_stream]
    L --> M

    M --> N[OpenRouter LLM\n流式响应]
    N --> O[SSE 逐 chunk 推送\ntype=delta]
    O --> P([浏览器实时渲染])

    N --> Q[流结束后\nsave_message assistant]
    Q --> R[SSE done 事件\ntype=done + message_id]
    R --> S{自动朗读?}
    S -->|是| T[TTS edge-tts]
    S -->|否| U([用户看到完整回复])
    T --> U
```

---

## 二、主对话完整时序

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant ChatRouter as chat_router
    participant MemSvc as memory_service
    participant ModelClient as model_client
    participant LLM as OpenRouter LLM
    participant DB as SQLite

    User->>FE: 输入消息（文字 / 语音识别结果）
    FE->>FE: sendMessage(text)
    FE->>FE: 追加用户气泡，清空输入框

    FE->>ChatRouter: POST /chat/stream\n{message, session_id, user_id, history[]}

    ChatRouter->>DB: upsert_session(session_id, user_id)
    ChatRouter->>DB: save_message(session_id, "user", message)
    ChatRouter->>DB: commit()  ← 流式开始前释放写锁

    ChatRouter->>MemSvc: build_system_prompt(user_id)
    Note over MemSvc: get_injectable_cards(user_id, limit=3)<br/>过滤 due <= now，按 stability 升序
    MemSvc->>DB: SELECT * FROM grammar_cards WHERE user_id AND status='active'
    DB-->>MemSvc: active 卡片列表
    MemSvc-->>ChatRouter: system_prompt（含或不含记忆注入段）

    ChatRouter->>ModelClient: client.chat_stream(message, history)
    Note over ModelClient: messages = [system] + history + [user_msg]

    ModelClient->>LLM: 流式请求（SSE）
    loop 每个 chunk
        LLM-->>ModelClient: delta text
        ModelClient-->>ChatRouter: yield chunk
        ChatRouter-->>FE: SSE data: {type:"delta", content:chunk}
        FE-->>User: 实时追加到气泡
    end

    LLM-->>ModelClient: 流结束
    ModelClient-->>ChatRouter: 生成器耗尽

    ChatRouter->>DB: save_message(session_id, "assistant", full_content)
    DB-->>ChatRouter: message_id
    ChatRouter-->>FE: SSE data: {type:"done", session_id, message_id}

    FE->>FE: 更新 chatHistory，更新轮次计数
    alt 自动朗读开启
        FE->>FE: ttsQueue.push(full_content)
    end
```

---

## 三、System Prompt 构建逻辑

```mermaid
flowchart TD
    A([build_system_prompt 被调用]) --> B[get_injectable_cards\nuser_id, limit=3]

    B --> C[查询所有 status=active 的卡片]
    C --> D{有卡片?}

    D -->|否| E[返回基础 SYSTEM_PROMPT\n无记忆注入]

    D -->|是| F[遍历每张卡片\n解析 fsrs_card_data.due]
    F --> G{due <= now?}
    G -->|否，未到期| H[跳过该卡片]
    G -->|是，已到期| I[纳入候选列表]

    I --> J{候选列表\n是否非空?}
    J -->|否| E
    J -->|是| K[按 stability 升序排序\n取前 3 张]

    K --> L[构建记忆注入段\n格式：「该用户有待改善的语法习惯：xxx。\n在对话中自然使用正确形式，\n绝对不要直接指出。」]
    L --> M[拼接到 SYSTEM_PROMPT 末尾\n## About This User 私有上下文块]
    M --> N([返回增强 system_prompt])
```

**注入限制**：
- 注入上限：最多 3 张（`limit=3`）
- 注入条件：`due <= now`（卡片已到期）
- 排序：`stability` 升序（优先注入最不稳定的记忆）
- 隐私保护：注入段标注"绝对不要直接提及"，Alex 只能以自然方式示范正确用法

---

## 四、多模型路由逻辑

```mermaid
flowchart TD
    A([get_client 被调用]) --> B[读取 MODEL_PROVIDER\n环境变量]

    B --> C{provider?}

    C -->|anthropic| D[AnthropicClient\n使用官方 SDK\nanthropic.Anthropic]
    C -->|deepseek| E[OpenAICompatibleClient\nbase_url: api.deepseek.com]
    C -->|volcengine| F[OpenAICompatibleClient\nbase_url: ark.cn-beijing.volces.com]
    C -->|zhipu| G[OpenAICompatibleClient\nbase_url: open.bigmodel.cn]
    C -->|未知| H[抛出 ValueError\n启动报错]

    D --> I[chat_stream 实现\n.messages.stream]
    E --> J[chat_stream 实现\n.chat.completions.create stream=True]
    F --> J
    G --> J

    I --> K([返回 AsyncGenerator\n逐 chunk yield])
    J --> K
```

**共同配置**：
- `timeout=30.0`
- `http_client=httpx.Client(trust_env=False)` — 忽略系统代理
- `MODEL_NAME` 由 `MODEL_NAME` 环境变量决定，默认见 `app/config.py`

---

## 五、会话管理逻辑

```mermaid
flowchart TD
    A([页面加载]) --> B[getUserId\nlocalStorage uuid]
    B --> C[getSessionId\nlocalStorage uuid]
    C --> D[loadHistory\nGET /history/{user_id}]
    D --> E[渲染历史侧边栏]

    F([用户查看历史会话]) --> G[onHistoryClick\nsid]
    G --> H[GET /history/{sid}/messages]
    H --> I[renderReadonlyChat\nsetMode readonly]
    I --> J[GET /review/{sid}]
    J --> K{200?}
    K -->|是| L[showReviewBtn\nheader-right 插入按钮]
    K -->|否| M[hideReviewBtn\n静默]

    N([用户点「新对话」]) --> O[onNewChat]
    O --> P[newSession\n生成新 uuid]
    P --> Q[重置 chatHistory · _roundCount]
    Q --> R[hideReviewBtn + resetEndBtn]
    R --> S[Alex 发开场白]

    T([用户点「← 回到当前对话」]) --> U[returnToCurrentSession]
    U --> V[恢复 DOM 快照]
    V --> W[hideReviewBtn + resetEndBtn]
    W --> X[setMode chat]
```

---

## 六、关键数据结构

**`/chat/stream` 请求体**：

```json
{
  "message": "I go to office yesterday",
  "session_id": "uuid-string",
  "user_id": "uuid-string",
  "history": [
    {"role": "user",      "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

**SSE 事件类型**：

```
data: {"type": "delta",  "content": "Hey! "}
data: {"type": "delta",  "content": "That sounds"}
data: {"type": "done",   "session_id": "...", "message_id": 42}
data: {"type": "error",  "message": "..."}
```

**sessions 表**：

```
id          TEXT PK  (uuid)
user_id     TEXT
preview     TEXT     (侧边栏预览，首条用户消息前 40 字符)
created_at  DATETIME
```

**messages 表**：

```
id          INT PK (autoincrement)
session_id  TEXT FK → sessions.id
role        TEXT  ('user' | 'assistant')
content     TEXT
created_at  DATETIME
```
