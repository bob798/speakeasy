# CLAUDE.md — Speakeasy 项目上岗手册

> 每次启动前完整阅读本文件。
> 本文件分两部分：【永久内容】长期有效；【版本状态】每次版本迭代后更新。

---

## 【永久内容】项目认知

### 产品定位

**Speakeasy** — 职场人的英语练习伙伴。

AI 扮演英语母语朋友 Alex，和用户聊真实生活里的事。
**核心原则：永远不显性纠错，在对话中自然示范更好的表达方式。**

### 团队分工

| 角色 | 负责人 | 职责 |
|---|---|---|
| CEO / 产品决策 | Human | 方向确认、最终验收 |
| CTO / 规划 | Claude | 技术方案、开发计划文档 |
| 程序员 | Claude Code | 编码、自测、汇报 |

### 技术栈

```
后端：Python · FastAPI · SQLite · SQLAlchemy · Uvicorn
前端：原生 HTML / JS / CSS
LLM：多模型工厂，通过 OpenRouter 接入
      · Anthropic Claude (claude-haiku-4-5)
      · DeepSeek (deepseek-chat)
      · Volcengine Doubao (doubao-1-5-pro-32k)
      · Zhipu GLM (glm-4-flash)
STT：faster-whisper
TTS：edge-tts
记忆：py-fsrs（FSRS 6 算法）
开发工具：VSCode + Claude Code · Token 走 OpenRouter
```

### 项目目录结构

```
speakeasy/
├── app/
│   ├── models/
│   │   └── db.py              # 所有数据表定义
│   ├── services/
│   │   ├── chat_service.py    # LLM 调用、System Prompt 构建
│   │   ├── review_service.py  # 对话分析（V0.2b+）
│   │   └── memory_service.py  # FSRS 记忆调度（V0.2b+）
│   ├── prompts/
│   │   └── review.py          # 分析用 Prompt（V0.2b+）
│   └── routers/
│       ├── chat.py            # /chat · /chat/summary
│       └── review.py          # /review（V0.2b+）
├── docs/
│   ├── adr/
│   │   ├── ADR-001-sqlite-over-postgresql.md
│   │   ├── ADR-002-fsrs-pending-active-states.md
│   │   ├── ADR-003-openrouter-multi-model.md
│   │   └── ADR-004-no-explicit-correction-rule.md
│   └── architecture/
│       └── c4-container.md
├── frontend/
│   └── src/
│       └── components/        # 前端组件
├── tests/                     # 所有测试文件
├── CLAUDE.md                  # 本文件
├── ROADMAP.md                 # 产品路线图
├── BUG_LOG.md
├── ALEX_BEHAVIOR_TEST_STANDARD.md
├── SPEC_V02B.md               # V0.2b 规格文档（当前版本）
├── CLAUDE_CODE_DOC_STANDARD.md # 开发计划文档规范
├── requirements.txt
└── .env                       # API Keys（不提交 git）
```

### 数据表清单

| 表名 | 引入版本 | 说明 |
|---|---|---|
| sessions | V0.2a | 对话 session 记录 |
| messages | V0.2a | 消息历史，含 role/content |
| grammar_cards | V0.2b | FSRS 管理的语法错误卡片 |
| session_reviews | V0.2b | 每次对话的复盘数据 |

### API 接口清单

| 接口 | 方法 | 引入版本 | 说明 |
|---|---|---|---|
| `/chat` | POST | V0.1 | 主对话，V0.2b 起注入 grammar_cards |
| `/chat/summary` | POST | V0.1 | V0.2b 升级为返回复盘数据 |
| `/review/{session_id}` | GET | V0.2b | 获取复盘数据 |
| `/review/{session_id}/rate` | POST | V0.2b | 用户评分，更新 FSRS |

---

## 【永久内容】行为规则

### 必须遵守

1. **按 Step 顺序执行，不跳步**
2. **每个 Step 先实现，再跑测试，全部 PASS 才进入下一步**
3. **遇到文档未覆盖的情况：停下来问 Human，不自行决策**
4. **不修改已完成版本的代码和测试**（除非 Human 明确要求）
5. **所有 pip install 在激活的 venv 中执行**

### 测试规范

- 测试数据使用独立 user_id：`test_user_[版本号]_[step号]`
- 每个测试有 `autouse fixture` 保证前后清理
- 断言必须用具体值，禁止模糊断言（如 `assert result is not None`）
- Mock 只作用于外部依赖（LLM API），不 Mock 内部服务

### 完成标志

- 每个 Step 完成后终端打印 `✅ Step N 完成`
- 全部 Step 完成后运行 `pytest tests/ -v` 全量回归
- 全绿后按汇报模板输出结果，等待 Human 验收

### 禁止行为

```
❌ 不在当前 Step 范围内的功能，一律不实现
❌ 不擅自修改数据表结构（需先向 Human 确认）
❌ 不修改 .env 文件内容
❌ 不删除任何已有测试文件
❌ 不在测试中使用真实 user_id 数据
```

### 文档维护规则

Claude Code 在以下时机自动维护文档，无需 Human 指示：

| 时机 | 维护动作 |
|---|---|
| 每个 Step 完成 | 更新 CLAUDE.md 的 Step 进度状态 |
| 架构新增/修改模块 | 更新 docs/architecture/c4-container.md |
| 新增跨模块服务 | 在 docs/architecture/flows/ 新建对应 flow 文档 |
| 修改跨模块调用链 | 更新 docs/architecture/flows/ 对应文档 |
| Bug 修复完成 | 更新 BUG_LOG.md 状态为已修复 |
| 做了重要技术决策 | 在 docs/adr/ 新增 ADR 草稿，汇报中标注"待 Human 确认" |

Human 维护（Claude Code 不代劳）：
  · ROADMAP.md 的版本状态（每次验收后移入"已发布"）
  · ADR 的最终确认（Claude 起草，Human 30秒确认即可）
  · User Stories 的方向确认

---

## 【版本状态】当前状态

> ⚠️ 此部分每次版本迭代后由 Human / Claude 更新

### 当前版本：V0.3（待规划）

**已完成版本功能：**
```
V0.1  ✅  文本对话 · 今日一句 · 多模型支持
V0.2a ✅  语音输入 STT · 语音输出 TTS · 流式输出 · 对话历史持久化
V0.2b ✅  对话复盘 · FSRS 记忆调度 · 点击提问 UI
```

**下一版本预告：V0.3**
```
Level 评估 · Preference 提取 · 记忆管理页面
```

---

## 【版本状态】环境启动

```bash
# 激活虚拟环境
source venv/bin/activate          # macOS/Linux
venv\Scripts\activate             # Windows

# 启动开发服务器
uvicorn app.main:app --reload

# 运行测试
pytest tests/ -v

# 运行单个 Step 测试
pytest tests/test_stepN.py -v
```

---

## 【版本状态】版本更新记录

| 版本 | 状态 | 核心交付 |
|---|---|---|
| V0.1 | ✅ 完成 | 文本对话 · 今日一句 |
| V0.2a | ✅ 完成 | STT · TTS · 流式输出 · 历史持久化 |
| V0.2b | ✅ 完成 | 复盘 · FSRS · 点击提问 |
| V0.3 | ⏳ 规划中 | Level评估 · Preference · 记忆管理 |