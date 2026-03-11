# 对话复盘流程（Review Flow）

> 描述：从用户点击「结束对话」到复盘展示、用户评分、历史访问的完整数据流
> 涉及模块：chat_router · review_service · memory_service · review_router · session_reviews 表 · grammar_cards 表
> 最后更新：V0.2b

---

## 一、全局流程概览

```mermaid
flowchart TD
    A([用户点击「结束对话」]) --> B[Frontend\nonEndChat]
    B --> C{chatHistory\n轮数 >= 2?}

    C -->|否| D[直接跳转 /review 页面\n无复盘数据]
    C -->|是| E[POST /chat/summary]

    E --> F[review_service\nanalyze_conversation]
    F --> G{用户消息 >= 2\n且 LLM 成功?}

    G -->|失败| H[返回 type=tip\n今日英语小贴士]
    G -->|成功| I[提取 errors + highlights\nconfidence >= 0.7]

    I --> J[memory_service\nupdate_grammar_cards]
    I --> K[memory_service\nmark_errors_not_appeared]
    J --> L[(grammar_cards 表)]
    K --> L

    I --> M[save_session_review\n写入 session_reviews 表]
    M --> N[返回 type=review\n复盘数据]

    N --> O[Frontend\n替换「结束对话」为「查看复盘」按钮]
    H --> P[Frontend\n展示今日一句]
```

---

## 二、复盘生成时序

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant ChatRouter as chat_router
    participant ReviewSvc as review_service
    participant MemSvc as memory_service
    participant LLM as OpenRouter LLM
    participant DB as SQLite

    User->>FE: 点击「结束对话」
    FE->>FE: 检查 chatHistory 轮数

    alt 轮数 < 2
        FE->>FE: 直接跳转 /review（无复盘）
    else 轮数 >= 2
        FE->>FE: 按钮变为「分析中...」disabled
        FE->>ChatRouter: POST /chat/summary {session_id, user_id, history}

        ChatRouter->>ReviewSvc: analyze_conversation(session_id, user_id, history)
        ReviewSvc->>ReviewSvc: 过滤出 user 消息（>= 2 条才继续）
        ReviewSvc->>ReviewSvc: 格式化对话文本 → 填入 REVIEW_PROMPT
        ReviewSvc->>LLM: complete(prompt, max_tokens=1000)

        alt LLM 返回合法 JSON
            LLM-->>ReviewSvc: {errors[], highlights[]}
            ReviewSvc->>ReviewSvc: 过滤 confidence < 0.7 的 errors
            ReviewSvc->>ReviewSvc: 构建 stats {turns, duration_seconds}
            ReviewSvc->>DB: INSERT/UPDATE session_reviews
            ReviewSvc-->>ChatRouter: result dict

            ChatRouter->>MemSvc: update_grammar_cards(user_id, errors)
            ChatRouter->>MemSvc: mark_errors_not_appeared(user_id, appeared_keys)
            ChatRouter-->>FE: {type: "review", errors[], highlights[], stats{}}
            FE-->>User: 按钮变为「查看复盘」（绿色边框）
        else LLM 失败或解析错误
            ReviewSvc-->>ChatRouter: None
            ChatRouter->>ChatRouter: get_daily_tip()（LLM 生成）
            ChatRouter-->>FE: {type: "tip", tip: "..."}
            FE-->>User: 展示今日英语小贴士
        end
    end
```

---

## 三、复盘 UI 三层结构

```mermaid
flowchart TD
    A([用户进入 /review 页面]) --> B[GET /review/{session_id}]

    B --> C{session_reviews\n记录存在?}
    C -->|否，404| D[展示「暂无复盘数据」]
    C -->|是，200| E[渲染三层卡片]

    E --> F[第一层：统计摘要\nstats.turns · 会话时长]
    E --> G[第二层：语法错误卡片\nerrors[]\n原句 / 建议 / 解释]
    E --> H[第三层：表达亮点\nhighlights[]\n做得好的地方]

    G --> I{卡片 status?}
    I -->|pending| J[显示卡片，无评分按钮]
    I -->|active| K[显示卡片 + 评分按钮\n👍 已掌握 / 🔁 再复习]

    K --> L([用户点击评分])
    L --> M[POST /review/{session_id}/rate]
```

---

## 四、用户评分时序

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend (review.html)
    participant ReviewRouter as review_router
    participant MemSvc as memory_service（via review_router）
    participant FSRS as py-fsrs
    participant DB as SQLite

    User->>FE: 点击「👍 已掌握」或「🔁 再复习」
    FE->>ReviewRouter: POST /review/{session_id}/rate\n{user_id, card_key, rating: "good"/"again"}

    ReviewRouter->>DB: 查询 grammar_cards WHERE user_id AND key = card_key
    DB-->>ReviewRouter: card_row

    alt 卡片存在且 status = active
        ReviewRouter->>ReviewRouter: Card.from_dict(card_row.fsrs_card_data)
        ReviewRouter->>FSRS: scheduler.review_card(card, Rating.Good / Rating.Again)
        FSRS-->>ReviewRouter: 新 card（含 due, stability 等）
        ReviewRouter->>DB: UPDATE fsrs_card_data = card.to_dict()
        ReviewRouter->>DB: UPDATE session_reviews.is_user_rated = True
        ReviewRouter-->>FE: {next_review: ISO8601 时间}
        FE-->>User: 显示「下次复习：X 天后」
    else 卡片不存在或 status ≠ active
        ReviewRouter-->>FE: 404
        FE-->>User: 静默处理
    end
```

---

## 五、历史复盘访问时序

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend (index.html)
    participant ReviewRouter as review_router
    participant DB as SQLite

    User->>FE: 点击历史会话列表中某条记录
    FE->>FE: onHistoryClick(sid)
    FE->>FE: GET /history/{sid}/messages → 渲染只读对话

    FE->>ReviewRouter: GET /review/{sid}

    alt session_reviews 存在
        ReviewRouter->>DB: SELECT * FROM session_reviews WHERE session_id = sid
        DB-->>ReviewRouter: 复盘行
        ReviewRouter-->>FE: 200 {errors[], highlights[], stats{}}
        FE->>FE: showReviewBtn(sid)\n在 header-right 插入「查看复盘」按钮
        FE-->>User: 右上角出现「查看复盘」绿色按钮
    else 不存在
        ReviewRouter-->>FE: 404
        FE->>FE: hideReviewBtn() 静默处理
        FE-->>User: 无按钮（该会话无复盘）
    end

    User->>FE: 点击「查看复盘」
    FE->>FE: window.location.href = /review?session_id=sid
```

---

## 六、LLM 分析结果数据结构

**REVIEW_PROMPT 期望 LLM 返回的 JSON 结构**：

```json
{
  "errors": [
    {
      "key": "go_went",
      "content": "过去时 go 应用 went",
      "original": "I go to the office yesterday",
      "corrected": "I went to the office yesterday",
      "explanation_zh": "go 的过去式是 went",
      "confidence": 0.95
    }
  ],
  "highlights": [
    {
      "quote": "That's a really thoughtful way to put it!",
      "comment": "用了地道的 put it 表达，自然流畅"
    }
  ]
}
```

**过滤规则**：`confidence < 0.7` 的 error 条目在 `review_service` 中被丢弃，不写入数据库。

**`session_reviews` 表存储格式**：

```
errors    TEXT  → JSON.stringify(errors[])     过滤后
highlights TEXT → JSON.stringify(highlights[])
stats      TEXT → JSON.stringify({turns, duration_seconds})
```
