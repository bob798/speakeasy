# CLAUDE.md — Speakeasy 项目上岗手册

> 每次启动前完整阅读本文件。
> 本文件分两部分：【永久内容】长期有效；【版本状态】每次版本迭代后更新。

---

## 【永久内容】项目认知

### 产品定位

**Speakeasy** — AI 陪伴式私教，越聊越懂你。

AI 扮演英语私教朋友 Alex，在真实对话中持续积累对用户的认知，动态调整话题、难度与强化方向。
**核心原则：私教级的洞察，包裹在朋友式的对话里；隐式引导 + 显式复盘，双路径同步习得。**

- **认识你**：职业画像 + 语法习惯 + 生活事件，三层记忆持续更新
- **带你走**：FSRS 调度强化点，LLM 动态调整话题与难度，越用越精准
- **陪着你**：跨 session 无终点，学习退入背景，习得自然发生

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
│   │   ├── memory_service.py  # FSRS 记忆调度（V0.2b+）
│   │   ├── fsrs_utils.py      # FSRS 共享工具（V0.4+）
│   │   ├── subtitle_service.py # B站字幕提取（V0.4+）
│   │   ├── practice_service.py # 发音练习卡片管理（V0.4+）
│   │   └── translate_service.py # 翻译服务 + 生词本 CRUD（V0.5+）
│   ├── prompts/
│   │   ├── review.py          # 分析用 Prompt（V0.2b+）
│   │   └── translate.py       # 翻译 Prompt（V0.5+）
│   └── routers/
│       ├── chat.py            # /chat · /chat/summary
│       ├── review.py          # /review（V0.2b+）
│       ├── practice.py        # /practice/*（V0.4+）
│       └── translate.py       # /translate/*（V0.5+）
├── docs/
│   ├── spec/                  # 产品规格文档
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
├── .claude/
│   ├── CLAUDE.md                  # 本文件
│   └── CLAUDE_CODE_V02B_INSTRUCTIONS.md       # 各开发版本执行指令
├── ROADMAP.md                 # 产品路线图
├── BUG_LOG.md
├── ALEX_BEHAVIOR_TEST_STANDARD.md
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
| user_profile | V0.3 | 用户画像（CEFR/职业/目标/风格） |
| user_facts | V0.3 | LLM 提取的跨会话事实记忆 |
| pronunciation_cards | V0.4 | FSRS 管理的发音练习卡片 |
| subtitle_sources | V0.4 | B站字幕缓存 |
| vocabulary | V0.5 | 翻译生词本收藏（软删除，无 FSRS） |
| ask_threads | V0.7 | 跨页面通用追问 thread（scope + ref_type/ref_id） |
| ask_messages | V0.7 | 追问 thread 的消息列表 |
| bbc_eaw_episodes | V0.7.x | BBC English at Work 67 集语料（共享，不绑 user_id），见 `docs/datasets/bbc_eaw.md` |

### API 接口清单

| 接口 | 方法 | 引入版本 | 说明 |
|---|---|---|---|
| `/chat` | POST | V0.1 | 主对话，V0.2b 起注入 grammar_cards，V0.3 起注入三层记忆 |
| `/chat/summary` | POST | V0.1 | V0.2b 升级为复盘，V0.3 起异步触发 facts 提取 |
| `/review/{session_id}` | GET | V0.2b | 获取复盘数据 |
| `/review/{session_id}/rate` | POST | V0.2b | 用户评分，更新 FSRS |
| `/assessment/self` | POST | V0.3 | 5 题 CEFR 自评，保存到 user_profile |
| `/memory/profile` | GET/PUT | V0.3 | 用户画像读写 |
| `/memory/facts` | GET | V0.3 | 事实记忆分页查询 |
| `/memory/facts/{id}` | DELETE | V0.3 | 物理删除一条 fact |
| `/memory/cards` | GET | V0.3 | 语法卡列表（active/pending） |
| `/memory/cards/{id}` | DELETE | V0.3 | 软删除语法卡（status='deleted'） |
| `/memory` | GET | V0.3 | 返回 memory.html 管理页面 |
| `/practice/subtitles` | POST | V0.4 | B站字幕提取或手动文本解析 |
| `/practice/cards` | POST | V0.4 | 批量创建发音练习卡片 |
| `/practice/cards` | GET | V0.4 | 发音卡列表（支持分页/状态过滤） |
| `/practice/cards/{id}/review` | POST | V0.4 | FSRS 评分更新 |
| `/practice/cards/{id}` | DELETE | V0.4 | 软删除发音卡 |
| `/practice/due` | GET | V0.4 | 获取到期复习卡 |
| `/practice` | GET | V0.4 | 返回 practice.html 练习页面 |
| `/translate` | GET | V0.5 | 返回 translate.html 翻译页面 |
| `/translate/text` | POST | V0.5 | 双向翻译（zh2en/en2zh），1000 字符上限 |
| `/translate/vocabulary` | POST | V0.5 | 收藏译文到生词本 |
| `/translate/vocabulary` | GET | V0.5 | 生词本列表（分页） |
| `/translate/vocabulary/{id}` | DELETE | V0.5 | 软删除生词本条目 |
| `/practice/explain/phonetic` | POST | V0.7 | 单词 IPA 本地秒出（eng-to-ipa） |
| `/practice/explain/stream` | POST | V0.7 | 句子解读 NDJSON 流式（字段级渐进渲染） |
| `/ask/threads` | POST | V0.7 | 通用追问：新建 thread + 首轮问答 |
| `/ask/threads/{id}/messages` | POST | V0.7 | 追问某 thread（带历史） |
| `/ask/threads` | GET | V0.7 | 列出 thread（按 scope/ref_type/ref_id 过滤） |
| `/ask/threads/{id}` | GET | V0.7 | 查看 thread + 消息 |
| `/ask/threads/{id}` | DELETE | V0.7 | 软删 thread |

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
| 部署方式/配置变更 | 同步更新 README.md 中的部署说明、环境要求等相关章节 |
| API 接口新增/修改 | 同步更新 README.md 中的 API 文档（如有）及 CLAUDE.md 接口清单 |
| 依赖变更 | 同步更新 README.md 中的安装/依赖说明 |

Human 维护（Claude Code 不代劳）：
  · ROADMAP.md 的版本状态（每次验收后移入"已发布"）
  · ADR 的最终确认（Claude 起草，Human 30秒确认即可）
  · User Stories 的方向确认

### Git 与部署规范

**分支流程（强制）：**
- 所有改动走独立分支 + PR，**不直接提交或合并到 main**
- 即使 Human 说"合并到 main"，也创建 PR（`gh pr create`）
- 分支命名：`feat/xxx`、`fix/xxx`、`style/xxx`

**CI/CD 流水线：**

```
push 到 main → GitHub Actions 自动触发
  │
  ├─ Bundle Size Budget（前端变更时）
  │   └─ 300KB gzip 硬预算（JS 200KB + CSS 100KB），超标即阻止合入
  │
  └─ Build and Deploy
      ├─ Job 1: build-and-push
      │   ├─ Docker 多阶段构建（前端 npm build + 后端 Python）
      │   └─ 推送到阿里云 ACR（3 tag：latest / 版本号 / SHA）
      │
      └─ Job 2: deploy（AUTO_DEPLOY=true 时执行）
          ├─ SSH 到腾讯云 VPS（deployer 用户 + 专用密钥）
          └─ 执行 VPS 上的 scripts/deploy_vps.sh
              ├─ ACR 登录 → docker compose pull → 重建容器
              ├─ /health 健康检查（60s 超时）
              └─ DB 数据摘要校验
```

**部署约束：**
- VPS 上的 `scripts/deploy_vps.sh` 必须与仓库保持同步（CI 用 `SKIP_GIT=1` 不会自动更新）
- 修改 `deploy_vps.sh` 或 `.github/workflows/deploy.yml` 后，需手动同步到 VPS
- 修改 `docker-compose.yml` 或 `Dockerfile` 后，同样需手动同步到 VPS
- 不修改 GitHub Secrets（VPS_HOST / VPS_USER / VPS_SSH_KEY / VPS_APP_DIR / ALIYUN_*）
- 不修改 GitHub Variables（AUTO_DEPLOY）
- 版本号格式：`{VERSION}-{YYYYMMDD}-{SHORT_SHA}`，VERSION 文件在项目根目录

---

## 【版本状态】当前状态

> ⚠️ 此部分每次版本迭代后由 Human / Claude 更新

### 当前版本：V0.7（已完成）

**已完成版本功能：**
```
V0.1  ✅  文本对话 · 今日一句 · 多模型支持
V0.2a ✅  语音输入 STT · 语音输出 TTS · 流式输出 · 对话历史持久化
V0.2b ✅  对话复盘 · FSRS 记忆调度 · 点击提问 UI
V0.3  ✅  三层记忆系统 · Level评估 · user_facts · 记忆管理页面
V0.4  ✅  发音练习 · B站字幕提取 · 录音对比 · FSRS 复习闭环
V0.5  ✅  翻译 MVP：双向翻译 · 生词本 · /translate 独立页
V0.6  ✅  用户账号系统 · JWT · 登录注册 · 数据迁移脚本
V0.7  ✅  解读弹窗增强 · 通用 Ask 追问（跨页面可复用）
```

**下一版本预告：V0.8**
```
场景模式（职场/旅行/面试） · 进度可视化 · 学习连续天数
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
| V0.3 | ✅ 完成 | 三层记忆 · Level评估 · user_facts · 记忆管理页 |
| V0.4 | ✅ 完成 | 发音练习 · B站字幕提取 · 录音对比 · FSRS 复习闭环 |
| V0.5 | ✅ 完成 | 翻译 MVP：双向翻译 · 生词本 · /translate 独立页 |
| V0.6 | ✅ 完成 | 用户账号系统 · JWT · 登录注册 · 数据迁移 |
| V0.7 | ✅ 完成 | 解读弹窗增强（IPA 秒出 / 连读 / 点读 / 讲解朗读 / 流式）· 通用 Ask 追问抽象 |