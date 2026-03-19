# Changelog

All notable changes to Speakeasy will be documented in this file.

---

## [Unreleased]
> 计划中的功能 / Upcoming features
- Scene modes: workplace / travel / interview
- Progress visualization & streak tracking
- Spaced repetition UI for grammar cards

---

## [0.3.0] - 2026-03-18

### Added — 三层记忆系统：Alex 真正认识你了

**层1：用户画像（user_profile）**
- `POST /assessment/self` — 5 道 CEFR 自评题，纯规则映射（can/partially/cannot），无 LLM 调用
- `GET /memory/profile` / `PUT /memory/profile` — 画像读写（职业、行业、话题偏好、学习目标、对话风格）
- 首次打开 index.html 时展示引导 banner，完成或跳过后不再出现（localStorage 双态）

**层2：跨会话事实记忆（user_facts）**
- 每次对话结束后，LLM 自动提取最多 5 条用户事实，异步写入 `user_facts` 表（不阻塞 summary 响应）
- 幂等保护：同一 `session_id` 不重复提取
- `GET /memory/facts` — 分页查询；`DELETE /memory/facts/{id}` — 物理删除

**层3：语法卡片管理（原 V0.2b，现在可见可控）**
- `GET /memory/cards` — 按 status 筛选（active/pending）；`DELETE /memory/cards/{id}` — 软删除

**System Prompt 三层注入（`build_system_prompt`）**
- 层1 profile 各字段独立 guard，空字段自动跳过，不产生空行
- 层2 facts token 估算截断（budget=400，始终保留至少 1 条）
- 层3 grammar_cards 逻辑与 V0.2b 完全一致（回归验证）

**记忆管理页面（`/memory`）**
- 三 Tab SPA：语言档案 / Alex 记得的事 / 语法强化
- 语言档案 Tab：展示 CEFR badge + 各 profile 字段编辑 + [重新评估] 按钮
- 事实 Tab：分页列表 + 逐条删除
- 语法卡 Tab：active/pending 展示 + 软删除
- index.html header 新增 🧠 入口跳转

### Technical
- 新表：`user_profile`（单行 upsert）、`user_facts`（append-only + 幂等）
- `app/services/profile_service.py` — CEFR 评分算法（纯规则，无 LLM）
- `app/services/facts_service.py` — LLM 提取、分页查询、物理删除
- `app/prompts/facts.py` — 事实提取 Prompt（英文，防止 tag 泄露）
- `app/routers/memory.py` — 所有 /memory/* + /assessment/* 路由（共 8 个端点）
- `static/memory.html` — 三 Tab 记忆管理 SPA（复用 index.html CSS 变量）
- 67 条新测试（Step 1–6），全量回归 159 passed

---

## [0.1.0] - 2025-03-06

### Added
- Core chat API (`POST /chat`) with multi-turn conversation support
- Daily tip generation (`POST /chat/summary`) — one gentle takeaway per session
- Multi-model support: Anthropic Claude / DeepSeek / Volcengine / Zhipu GLM
  - Switch providers with a single `.env` config change
- Frontend chat UI (`index.html`) — warm, judgment-free design
- Health check endpoint (`GET /health`)
- Debug status endpoint (`GET /debug/status`)
- Structured logging with request tracing (`request_id`)
- System Prompt: Alex persona — natural modeling, zero explicit correction

### Technical
- FastAPI + Python async backend
- Stateless architecture — conversation history maintained client-side
- Environment-based API key management (never committed to repo)
- OpenAI-compatible client for DeepSeek / Volcengine / Zhipu

---

*Format based on [Keep a Changelog](https://keepachangelog.com)*
