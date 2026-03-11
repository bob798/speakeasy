# 记忆调度流程（Memory Flow）

> 描述：FSRS 记忆卡片从创建到复习的完整数据流
> 涉及模块：chat_router · review_service · memory_service · grammar_cards 表
> 最后更新：V0.2b

---

## 一、全局流程概览

```mermaid
flowchart TD
    A([用户发送消息]) --> B[chat_router]
    B --> C[memory_service\n注入已有卡片]
    C --> D[chat_service\n调用 LLM]
    D --> E([Alex 回复])

    F([用户点击「结束对话」]) --> G[review_service\n分析对话]
    G --> H{LLM 分析\n是否成功}
    H -->|成功| I[提取错误列表]
    H -->|失败| J([展示今日英语小贴士\n降级处理])

    I --> K[memory_service\n更新卡片状态]
    K --> L([展示复盘界面])

    L --> M{用户评分}
    M -->|👍 已掌握| N[FSRS 长间隔调度]
    M -->|🔁 再复习| O[FSRS 短间隔调度]
    M -->|不操作| P[保持当前状态]
```

---

## 二、卡片状态机

```mermaid
stateDiagram-v2
    [*] --> pending: 第一次出现该错误\nfrequency = 1

    pending --> pending: 对话中再次出现\n同类错误（frequency+1）
    pending --> active: frequency 达到 2\n创建 FSRS Card

    active --> active: 用户评分后\nFSRS 重新调度间隔

    active --> deleted: 用户主动删除

    deleted --> [*]
```

**状态说明**：

| 状态 | 含义 | fsrs_card_data |
|---|---|---|
| `pending` | 刚发现，等待确认是真实问题 | 空字符串 |
| `active` | 已确认，纳入 FSRS 调度 | JSON（含 due_date 等） |
| `deleted` | 用户主动删除 | 保留原值 |

---

## 三、对话阶段：卡片注入流程

```mermaid
sequenceDiagram
    actor User
    participant ChatRouter as chat_router
    participant MemSvc as memory_service
    participant ChatSvc as chat_service
    participant LLM as OpenRouter LLM

    User->>ChatRouter: POST /chat {message}
    ChatRouter->>MemSvc: get_active_cards(user_id)
    MemSvc-->>ChatRouter: active 卡片列表（key + explanation）

    ChatRouter->>ChatSvc: build_prompt(message, cards)
    Note over ChatSvc: 将 active 卡片注入 system prompt<br/>格式：「用户常犯错误：xxx」

    ChatSvc->>LLM: 携带 system prompt 的对话请求
    LLM-->>ChatSvc: Alex 回复
    ChatSvc-->>User: 流式返回回复
```

**注入逻辑说明**：
- 只注入 `status = 'active'` 的卡片，`pending` 不注入
- 注入上限：最多 10 张（避免 prompt 过长）
- 注入格式：自然语言描述，不暴露"这是错误记录"给用户

---

## 四、复盘阶段：错误分析与卡片更新

```mermaid
sequenceDiagram
    actor User
    participant ChatRouter as chat_router
    participant ReviewSvc as review_service
    participant MemSvc as memory_service
    participant LLM as OpenRouter LLM
    participant DB as SQLite

    User->>ChatRouter: POST /chat/summary {session_id}

    ChatRouter->>ReviewSvc: analyze_session(session_id)
    ReviewSvc->>DB: 读取本次对话的所有消息
    ReviewSvc->>LLM: 分析对话，提取错误列表

    alt LLM 分析成功
        LLM-->>ReviewSvc: errors[] + highlights[]
        ReviewSvc->>MemSvc: update_cards(user_id, errors)

        loop 遍历每个 error
            MemSvc->>DB: 查询 grammar_cards WHERE user_id AND key = error.key

            alt 卡片不存在（新错误）
                MemSvc->>DB: INSERT status=pending, frequency=1
            else 卡片 pending 且 frequency < 2
                MemSvc->>DB: UPDATE frequency+1
            else 卡片 pending 且 frequency >= 2
                MemSvc->>DB: UPDATE status=active，创建 FSRS Card
            else 卡片已是 active
                MemSvc->>DB: 不修改状态（is_user_rated=false 时更新 FSRS）
            end
        end

        ReviewSvc->>DB: INSERT session_reviews
        ReviewSvc-->>User: 返回复盘数据

    else LLM 分析失败
        ReviewSvc-->>User: 返回今日英语小贴士（降级）
    end
```

---

## 五、评分阶段：FSRS 调度更新

```mermaid
sequenceDiagram
    actor User
    participant ReviewRouter as review_router
    participant MemSvc as memory_service
    participant FSRS as py-fsrs
    participant DB as SQLite

    User->>ReviewRouter: POST /review/{session_id}/rate {card_key, rating}

    ReviewRouter->>MemSvc: rate_card(user_id, card_key, rating)
    MemSvc->>DB: 读取 grammar_cards WHERE key = card_key

    alt 卡片存在且 status = active
        MemSvc->>FSRS: 传入当前 fsrs_card_data + rating
        FSRS-->>MemSvc: 新的 fsrs_card_data（含下次复习时间）
        MemSvc->>DB: UPDATE fsrs_card_data, is_user_rated=true
        MemSvc-->>User: 200 OK + 下次复习时间
    else 卡片不存在或 status != active
        MemSvc-->>User: 400 错误
    end
```

**`is_user_rated` 的作用**：
- `false`（默认）：系统自动触发 FSRS 调度，用较保守的参数
- `true`：用户主动评分，FSRS 使用用户给出的 rating，不再被系统覆盖

---

## 六、历史复盘访问流程

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant ReviewRouter as review_router
    participant DB as SQLite

    User->>Frontend: 进入历史会话页面
    Frontend->>ReviewRouter: GET /review/{session_id}

    alt session_reviews 存在
        ReviewRouter->>DB: 查询 session_reviews WHERE session_id
        DB-->>ReviewRouter: 复盘数据
        ReviewRouter-->>Frontend: 200 + {errors, highlights, stats}
        Frontend-->>User: 渲染「查看复盘」按钮
    else session_reviews 不存在
        ReviewRouter-->>Frontend: 404
        Frontend-->>User: 静默处理，不显示按钮
    end
```

---

## 七、关键数据结构

**grammar_cards 表**：

```
id              INT PK
user_id         TEXT (indexed)
key             TEXT (snake_case，如 "go_went")
content         TEXT (错误描述)
example_wrong   TEXT
example_right   TEXT
explanation_zh  TEXT
frequency       INT  (默认 1)
fsrs_card_data  TEXT (JSON，pending 时为空字符串)
status          TEXT ('pending' | 'active' | 'deleted')
created_at      DATETIME
updated_at      DATETIME
UNIQUE(user_id, key)
```

**session_reviews 表**：

```
id              INT PK
session_id      INT UNIQUE FK → sessions.id
user_id         TEXT
errors          TEXT (JSON Array)
highlights      TEXT (JSON Array)
stats           TEXT (JSON)
is_user_rated   BOOL (默认 False)
created_at      DATETIME
```
