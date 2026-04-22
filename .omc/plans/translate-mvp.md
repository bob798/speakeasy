# V0.5 翻译 MVP 实施计划

> Spec: `.omc/specs/deep-interview-translate-mvp.md` (ambiguity 17.5%)
> 预算: 1-2 天 | 复杂度: MEDIUM | 涉及 ~8 文件（3 新建 + 5 修改）

---

## A. RALPLAN-DR 摘要（SHORT 模式）

### Principles

1. **Step 顺序执行**：严格按 CLAUDE.md 规则，每 Step 先实现再测试，全绿才进下一步
2. **不污染现有管线**：vocabulary 表独立于 grammar_cards / pronunciation_cards，无 FSRS 字段
3. **复用优先**：LLM 调用走 `model_client.complete()`，TTS 走现有 `/tts` 接口，前端沿用 warm color 主题变量
4. **MVP 最小切面**：不做历史、不做自动检测、不做长文、不做多语种，只交付 spec 10 条 AC

### Decision Drivers

1. **1-2 天工期**：任何增加超过半天工作量的选项直接排除
2. **数据隔离**：不接 FSRS，不改现有卡表，后续版本可独立升级
3. **前端一致性**：新 SPA 必须与 practice.html / memory.html 同等结构，降低维护成本

### Viable Options

**决策点 1: 翻译服务层架构**

| 选项 | 描述 | Pros | Cons |
|---|---|---|---|
| **A. 独立 translate_service.py** (推荐) | 封装 prompt 构造 + model_client 调用 | 可测试、可复用、prompt 集中管理 | 多一个文件 |
| B. 直接在 router 中调用 model_client | 参考 practice.py 的 inline 模式 | 少一层抽象 | prompt 散落在 router，不利于后续调优 |

> 推荐 A：翻译 prompt 需要迭代调优（中英双向、特殊字符处理），独立 service 层更安全。

**决策点 2: 生词本删除策略**

| 选项 | 描述 | Pros | Cons |
|---|---|---|---|
| **A. 软删除 (status='deleted')** (推荐) | 与 grammar_cards / pronunciation_cards 一致 | 风格统一、可恢复 | 查询需过滤 |
| B. 物理删除 | 简单直接 | 零冗余 | 与项目惯例不一致 |

> 推荐 A：项目已有两处软删除先例，保持一致。

**决策点 3: 前端 SPA 技术**

| 选项 | 描述 |
|---|---|
| **A. 原生 HTML/JS/CSS** (唯一选项) | 项目既有 practice.html / memory.html 全部是原生实现 |

> 无替代选项。spec 已锁定沿用现有前端栈，引入 React/Vue 在 Non-Goals 范围外且违反工期约束。

---

## B. 详细实施计划

### Step 1: 数据层 — Vocabulary 模型

**涉及文件**: `app/models/db.py`

**变更**:
- 新增 `class Vocabulary(Base)` — 字段: id(PK), user_id(indexed), source_text, translated_text, direction('zh2en'|'en2zh'), context(nullable), created_at, status('active'|'deleted')
- 使用 Column() 风格（与 GrammarCard / PronunciationCard 一致，非 Mapped 风格）
- `create_tables()` 自动建表（已有 `Base.metadata.create_all`，无需额外动作）

**验收**:
- 启动应用后 `vocabulary` 表存在于 SQLite
- 字段类型与默认值正确

**验证命令**:
```bash
python -c "from app.database import create_tables; import asyncio; asyncio.run(create_tables())"
sqlite3 speakeasy.db ".schema vocabulary"
# 预期: CREATE TABLE vocabulary (id INTEGER PRIMARY KEY, user_id VARCHAR NOT NULL, ...)
pytest tests/test_v05_step1.py -v
```

**测试**: `tests/test_v05_step1.py` — `test_vocabulary_table_created`, `test_vocabulary_default_values`（user_id: `test_user_v05_step1`）

**映射 AC**: 无直接 AC，为 AC6/AC7/AC8 的基础设施

---

### Step 2: 翻译服务层

**涉及文件**: `app/services/translate_service.py` (新建), `app/prompts/translate.py` (新建)

**变更**:
- `app/prompts/translate.py`: `TRANSLATE_ZH2EN_PROMPT`, `TRANSLATE_EN2ZH_PROMPT` — system prompt 模板，指定角色为专业翻译、输出纯译文
  - **Temperature 策略：采用 Prompt 层约束（方案 b）**，不修改 `model_client.complete()` 接口。Prompt 中明确要求："直译为主、不润色不改写、保留专有名词与数字原样、只输出译文不加任何解释或注释"。这样在默认 temperature 下也能获得稳定确定性输出，且不污染共享组件。
  - `app/prompts/__init__.py` 当前为空包标记文件，新增 `translate.py` 无需修改它，直接 `from app.prompts.translate import ...` 导入即可（与 `review.py`、`facts.py` 同风格）
- `app/services/translate_service.py`:
  - `async def translate_text(text: str, direction: str) -> str` — 校验 direction、拼装 messages、调用 `model_client.complete()`，返回译文
  - `def save_vocabulary(user_id, source_text, translated_text, direction, context=None) -> dict` — 写入 vocabulary 表，返回记录
  - `def list_vocabulary(user_id, limit, offset) -> list[dict]` — 查询 status='active' 的记录
  - `def delete_vocabulary(vocab_id, user_id) -> bool` — 软删除

**验收**:
- `translate_text("你好", "zh2en")` 返回英文字符串
- CRUD 操作对 vocabulary 表正确读写

**验证命令**:
```bash
pytest tests/test_v05_step2.py -v
# 关键用例: test_translate_zh2en_basic, test_translate_en2zh_basic,
#           test_translate_mixed_input, test_translate_long_input_over_1000_raises
```

**测试**: `tests/test_v05_step2.py`（user_id: `test_user_v05_step2`）:
- `test_translate_zh2en_basic` — "我做过推荐系统" 翻译结果包含 "recommendation"
- `test_translate_en2zh_basic` — "I love reading" 翻译结果包含中文字符
- `test_translate_empty_input_raises` — 空字符串 / 纯空格输入抛异常
- `test_translate_invalid_direction` — direction 非 zh2en/en2zh 时抛异常
- `test_translate_mixed_input` — 中英混合如 "我用 Python 做 recommendation" 不报错，正常返回
- `test_translate_long_input_over_1000_raises` — 超 1000 字符阻止（对应 AC9）
- `test_save_vocabulary`, `test_list_vocabulary_excludes_deleted`, `test_delete_vocabulary`

**映射 AC**: AC4(翻译), AC6(收藏), AC7(列表), AC8(删除)

---

### Step 3: 后端 API — /translate 路由

**涉及文件**: `app/routers/translate.py` (新建), `main.py`

**变更**:
- `app/routers/translate.py`:
  - Pydantic schemas: `TranslateRequest(text, direction)`, `VocabularyCreate(source_text, translated_text, direction, context?)`, `VocabularyResponse`
  - `GET /translate` — 返回 `FileResponse("static/translate.html")`（注意：页面路由放 main.py，与 /practice /memory 一致）
  - `POST /translate/text` — 调用 `translate_text()`，校验 len(text) <= 1000
  - `POST /translate/vocabulary` — 调用 `save_vocabulary()`
  - `GET /translate/vocabulary` — 调用 `list_vocabulary()`，支持 user_id / limit / offset query params
  - `DELETE /translate/vocabulary/{id}` — 调用 `delete_vocabulary()`
- `main.py`:
  - 导入 `from app.routers import translate` + `app.include_router(translate.router)`
  - 新增 `GET /translate` 页面路由（与 /practice /memory 同级）

**验收**:
- 5 条路由均可通过 curl/httpie 正确调用
- 输入超 1000 字符时 POST /translate/text 返回 400
- 模型调用失败时返回 503 + 明确错误信息

**验证命令**:
```bash
pytest tests/test_v05_step3.py -v
# 手动 smoke test:
curl -X POST http://localhost:8000/translate/text \
  -H "Content-Type: application/json" \
  -d '{"text":"我做过推荐系统","direction":"zh2en"}'
# 预期: {"translated_text": "..."} HTTP 200
```

**测试**: `tests/test_v05_step3.py`（user_id: `test_user_v05_step3`）:
- `test_translate_text_success` — POST /translate/text 返回 200 + translated_text
- `test_translate_text_exceeds_limit` — 超 1000 字符返回 400
- `test_translate_text_model_error` — Mock 模型异常返回 503 + 错误信息
- `test_vocabulary_crud_lifecycle` — 创建 → 列表可见 → 删除 → 列表不可见
- `test_vocabulary_delete_nonexistent` — 删除不存在 ID 返回 404

**映射 AC**: AC2(页面加载), AC4(翻译), AC6(收藏), AC7(列表), AC8(删除), AC9(1000字符限制), AC10(错误提示)

---

### Step 4: 前端 SPA — translate.html

**涉及文件**: `static/translate.html` (新建)

**变更**:
- 页面结构参考 `practice.html`：header（品牌 + 导航链接）+ 主容器
- 核心 UI 组件:
  - 方向切换按钮 `[中 ⇄ 英]`（toggle direction state）
  - 输入 textarea（带字符计数 + 1000 上限提示）
  - 翻译结果展示区
  - 操作栏：🔊 朗读（调用 `/tts`）、⭐ 收藏（调用 `POST /translate/vocabulary`）
  - 📖 生词本面板（展开/折叠），显示收藏列表 + 删除按钮 + 计数 badge `(N)`
  - Toast 组件（收藏成功/失败反馈）
- CSS: 沿用 practice.html 的 `:root` 变量（warm color 主题）
- JS: fetch 统一错误处理（catch → 结果框显示错误文案，不静默）

**验收**:
- 访问 `/translate` 页面加载 < 1s
- 完整走通：输入中文 → 翻译 → 朗读 → 收藏 → 生词本查看 → 删除

**验证命令**:
- 启动服务后访问 `http://localhost:8000/translate`
- 肉眼逐项对照 AC3 的 6 个 UI 组件：方向切换、输入框、结果框、朗读、收藏、生词本入口
- AC5 朗读：点击 🔊 按钮，前端调用现有 `POST /tts` 接口播放结果框内容
- AC9：输入超 1000 字符，确认提交按钮禁用 + 红色提示
- AC10：断网或 Mock 错误时，结果框显示红色错误文案

**测试**: 手动验收为主（前端无自动化测试框架）；后端 AC 已在 Step 3 覆盖

**映射 AC**: AC2, AC3, AC4, AC5, AC6, AC7, AC8, AC9, AC10

---

### Step 5: Header 入口接入

**涉及文件**: `static/index.html`（第 799 行区域）, `static/practice.html`（header-right 区域）

**变更**:
- `index.html` 第 799 行前插入：`<a href="/translate" title="翻译">🌐</a>`，位于 ⚙️ 之后、🎙️ 之前
- `practice.html` 的 header-right 区域添加 🌐 翻译链接（与 🎙️ 🧠 并列）
- **memory.html 本轮不动**：其当前采用 `top-bar` 布局（`← 返回对话 | 🧠 记忆管理`），无 `header-right` 导航区，统一改造留作 Follow-up
- `translate.html` header 中已包含返回首页 + 其他页面链接

**验收**:
- 主页 header 出现 🌐 翻译入口，视觉上与 🎙️ 🧠 平级
- 从首页和 practice 页可跳转到 /translate

**验证命令**:
- 启动服务后访问 `http://localhost:8000/`，确认 header 出现 🌐 翻译
- 点击 🌐 跳转到 `/translate` 页面
- 从 `/practice` 页面点击 🌐 跳转到 `/translate`

**测试**: 手动验收

**映射 AC**: AC1

---

### Step 6: 自动化测试

**涉及文件**: `tests/test_v05_step2.py` (新建), `tests/test_v05_step3.py` (新建)

**变更**:
- 测试 user_id 分别为 `test_user_v05_step2`、`test_user_v05_step3`
- autouse fixture 清理 vocabulary 表
- Mock `model_client.complete()` 返回固定译文（不 Mock 内部服务）
- 覆盖: 正常翻译（双向）、空输入、中英混合、超长输入、无效 direction、CRUD 全生命周期、模型异常

**验收**:
- `pytest tests/test_v05_step2.py tests/test_v05_step3.py -v` 全绿
- `pytest tests/ -v` 全量回归全绿

**验证命令**:
```bash
pytest tests/test_v05_step2.py tests/test_v05_step3.py -v
pytest tests/ -v  # 全量回归
```

**映射 AC**: 所有 AC 的间接覆盖

---

### Step 7: 文档同步

**涉及文件**: `.claude/CLAUDE.md`, `README.md`

**变更**:
- CLAUDE.md:
  - 数据表清单新增 `vocabulary | V0.5 | 翻译生词本收藏`
  - API 接口清单新增 5 条 /translate 路由
  - 目录结构新增 translate.py / translate_service.py / translate.py(prompts)
  - 版本状态更新 V0.5 进度
- README.md: 功能列表新增 V0.5 翻译模块说明

**验收**: 文档内容与实际代码一致

**验证命令**:
```bash
git diff .claude/CLAUDE.md  # 确认数据表清单、API 清单、目录结构已更新
git diff README.md           # 确认 V0.5 功能说明已添加
```

**映射 AC**: 无直接 AC，属项目规范要求

---

## C. AC 覆盖映射

| AC | 描述 | 覆盖 Step | 验证方式 |
|---|---|---|---|
| AC1 | Header 出现 🌐 翻译入口 | Step 5 | 手动：主页 header 可见 |
| AC2 | /translate 页面加载 < 1s | Step 3+4 | 手动：浏览器 Network 面板 |
| AC3 | 页面包含完整 UI 组件 | Step 4 | 手动：逐项检查 6 个组件 |
| AC4 | 双向翻译正常工作 | Step 2+3 | 自动：test_translate_zh2en_basic / test_translate_en2zh_basic + 手动 |
| AC5 | 朗读功能 | Step 4 | 手动：点击 🔊 播放 |
| AC6 | 收藏写入 vocabulary + toast | Step 2+3+4 | 自动：test_save_vocabulary + 手动 toast |
| AC7 | 生词本列表展示 | Step 2+3+4 | 自动：test_list_vocabulary + 手动 UI |
| AC8 | 生词本删除 | Step 2+3+4 | 自动：test_delete_vocabulary + 手动 UI |
| AC9 | 1000 字符限制 | Step 3+4 | 自动：test_translate_text_exceeds_limit + 手动 UI |
| AC10 | 错误提示不静默 | Step 3+4 | 自动：test_translate_text_model_error + 手动 UI |

---

## D. 风险提示

1. **Sync/Async Session 混用**：translate_service.py 的 CRUD 操作将使用 sync `OrmSession(engine)`（与 practice_service.py 一致），翻译调用使用 async `model_client.complete()`。需确保 `complete()` 内部的 `run_in_executor` 不会阻塞事件循环。已有 practice/memory 模块验证过此模式，风险可控。

2. **翻译 Prompt 鲁棒性**：用户输入可能包含中英混合、特殊符号、纯空格/换行。Prompt 需明确指示"只输出译文，不加解释"；service 层需 strip 空白并校验非空。建议在 Step 2 中加入 edge case 测试。

3. **前端 Fetch 错误处理**：现有 practice.html 的 fetch 错误处理风格不完全统一。translate.html 需建立统一 pattern：`catch` 块写入结果框可见区域 + 红色样式提示，确保 AC10 通过。

---

## ADR（供 Architect 确认）

- **Decision**: V0.5 翻译 MVP 采用独立 /translate SPA + 轻量 vocabulary 表 + 独立 translate_service 层
- **Drivers**: 1-2 天工期、数据隔离、前端一致性
- **Alternatives**: (1) 嵌入聊天窗口 — 排除：UX 残缺 + 反向翻译困难；(2) 复用 FSRS 卡表 — 排除：spec 明确不接 FSRS；(3) Router 内联逻辑 — 可行但不利于 prompt 迭代
- **Why chosen**: 最小切面满足全部 10 条 AC，同时保留后续升级为 FSRS 学习闭环的路径
- **Consequences**: 新增 3 个文件 + 修改 5 个文件，vocabulary 表后续若接 FSRS 需加字段迁移
- **Follow-ups**: V0.6+ 可考虑 vocabulary → FSRS 升级、翻译历史、自动语言检测、memory.html header 统一改造为 header-right 导航风格

---

## Revision Log (v2)

### 本轮修复（对应 Critic ITERATE verdict）
- **Must Fix 1**: `/translate/do` → `/translate/text` — 全文替换路由名 + 测试函数名，对齐 REST 名词性路径约定
- **Must Fix 2**: temperature 策略采用 **Prompt 层约束方案 (b)** — 不修改 `model_client.complete()` 接口，在翻译 prompt 中明确"直译、不润色、保留专有名词与数字"约束
- **Must Fix 3**: Step 5 移除 `memory.html` header 改动 — 确认其当前为 `top-bar` 布局无 `header-right`，本轮只改 `index.html` + `practice.html`，memory.html 改造移入 Follow-ups
- **Must Fix 4**: 测试命名统一 `tests/test_v05_stepN.py` + user_id `test_user_v05_stepN` — 对齐 V0.3/V0.4 项目约定
- **FYI 5**: `app/prompts/__init__.py` 为空包标记，新增 `translate.py` 无需修改，直接导入即可
- **Enhancement 6**: 每 Step 补具体验证命令（python/sqlite3/pytest/curl/git diff）
- **Enhancement 7**: Step 2 测试加 edge case — `test_translate_zh2en_basic`、`test_translate_en2zh_basic`、`test_translate_mixed_input`（中英混合）、`test_translate_long_input_over_1000_raises`（AC9）
