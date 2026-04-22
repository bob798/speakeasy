# Deep Interview Spec: V0.5 翻译 MVP（/translate 独立页 + 生词本）

## Metadata
- Interview ID: di-translate-mvp-20260417
- Rounds: 3
- Final Ambiguity Score: 17.5%
- Type: brownfield (Speakeasy V0.4 → V0.5)
- Generated: 2026-04-17
- Threshold: 20%
- Status: PASSED

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.85 | 0.35 | 0.298 |
| Constraint Clarity | 0.75 | 0.25 | 0.188 |
| Success Criteria | 0.85 | 0.25 | 0.213 |
| Context Clarity | 0.85 | 0.15 | 0.128 |
| **Total Clarity** | | | **0.825** |
| **Ambiguity** | | | **0.175** |

## Goal

在 Speakeasy V0.5 中新增一个**独立双向中英翻译工具页（/translate）**，作为顶部导航栏第三个平级入口（与 🎙️练习、🧠记忆并列），支持用户把译文"收藏到生词本"作为轻量学习材料留存，**不进 FSRS 调度**。战略定位：MVP 级辅助工具，验证"翻译入口"本身的用户需求，不与现有三层记忆体系强耦合。

## Constraints

- **战略预算**：1-2 天工作量上限
- **独立页形态**：/translate 新 SPA（复用 /practice、/memory 的独立页模式），不嵌入主聊天窗口
- **不接 FSRS**：V0.5 明确不将译文送入 grammar_cards / pronunciation_cards 任一现有 FSRS 管线
- **独立数据表**：新建轻量 `vocabulary` 表存生词本（无 FSRS 字段），不污染现有卡表
- **复用现有资产**：
  - LLM 翻译引擎复用 `app/services/model_client.py`（当前 MODEL_PROVIDER=volcengine, MODEL_NAME=deepseek-v3-250324）
  - 朗读 TTS 复用现有 edge-tts 链路
  - 前端风格沿用主站 warm color 主题
- **双向对等**：UI 采用 `[中 ⇄ 英]` 手动切换按钮，不做自动语言检测（MVP 留简）

## Non-Goals

- ❌ 不做 FSRS 调度 / 复习闭环（留给后续版本可能升级）
- ❌ 不与聊天窗口耦合（不在 message action-bar / 不做侧边抽屉）
- ❌ 不做整段长文翻译（输入软上限 1000 字符，超出提示截断）
- ❌ 不做历史记录（只有"收藏"的条目留存，未收藏的翻译过后即走）
- ❌ 不做自动语言检测（方向由用户按钮切换）
- ❌ 不做多语种（只支持中 ⇄ 英两向）
- ❌ 不做翻译质量评分 / 对比 / 多模型选择

## Acceptance Criteria

Day 1 上线验收（全部必须通过）：

- [ ] **AC1**：主页顶部 header 出现第三个入口 `🌐 翻译`，与 🎙️练习、🧠记忆视觉平级
- [ ] **AC2**：点击 🌐 翻译 进入 `/translate` 页，页面加载耗时 < 1s
- [ ] **AC3**：/translate 页包含：方向切换按钮 `[中 ⇄ 英]`、输入框、翻译结果框、朗读按钮、收藏按钮、"📖 生词本 (N)" 入口
- [ ] **AC4**：用户输入中文 → 点翻译 / 或直接触发 → 翻译结果出现在结果框；反向同理
- [ ] **AC5**：点击 🔊 朗读 可朗读结果框内容（使用现有 edge-tts 链路）
- [ ] **AC6**：点击 ⭐ 收藏 → 当前 (zh, en) 对写入 `vocabulary` 表，页面内 toast 反馈，计数 "(N)" +1
- [ ] **AC7**：点击 📖 生词本 打开列表视图，显示所有收藏条目（中/英对照 + 时间）
- [ ] **AC8**：生词本列表支持删除单条（软删除或物理删除二选一，实现时决定）
- [ ] **AC9**：输入超过 1000 字符时阻止提交，给出 UI 提示
- [ ] **AC10**：翻译请求失败（网络/模型错误）时在结果框给出明确错误提示，不静默失败

## Assumptions Exposed & Resolved

| Assumption | Challenge | Resolution |
|---|---|---|
| "翻译" 就是单方向词典工具 | Round 1 ontology 问题暴露 4 种候选定位 | 锁定为"双向通用翻译工具 + 可选学习沉淀"（选项 3 + 扩展） |
| 翻译产物应进入 FSRS 学习闭环 | Round 2 权衡对比揭示新建表 vs 复用 vs 收藏 的 1-2 天 / 2-3 天 / 5-7 天成本阶梯 | MVP 明确**不进 FSRS**，只做轻量收藏；保留后续升级空间 |
| 翻译应嵌入现有聊天窗口（用户原话"现有聊天窗口 增加 选型"） | Round 3 四方案对比显示 action-bar / 抽屉会导致"用户反向翻译"能力残缺、UX 混乱 | 选择独立 /translate 页 + header 第三入口，放弃嵌入聊天 |
| 需要自动语言检测 | 增加实现复杂度 | MVP 留简：用户手动 `[中 ⇄ 英]` 切换，明确写入 Non-Goals |
| 需要记录所有翻译历史 | 生词本本身已是用户主动选择的"想留"的条目 | 不做历史，只留收藏，降低数据模型复杂度 |

## Technical Context

### 新增文件
- `static/translate.html` — 翻译 SPA（参考 `static/memory.html`、`static/practice.html` 结构）
- `app/routers/translate.py` — 新 router，挂载 `/translate` 页面 + API
- `app/services/translate_service.py` — 翻译业务逻辑（可选，直接在 router 中调用 model_client 也可）

### 新增数据表
```python
class Vocabulary(Base):
    __tablename__ = "vocabulary"
    id: int PK
    user_id: str (default 'default_user')
    source_text: str  # 用户输入原文
    translated_text: str  # 翻译结果
    direction: str  # 'zh2en' | 'en2zh'
    context: str | None  # 可选上下文备注
    created_at: datetime
    status: str  # 'active' | 'deleted' (软删除用)
```

### 新增 API 路由
| 接口 | 方法 | 说明 |
|---|---|---|
| `/translate` | GET | 返回 translate.html |
| `/translate/do` | POST | 请求翻译，body: {text, direction}, return: {translated_text} |
| `/translate/vocabulary` | POST | 收藏一条，body: {source, translated, direction} |
| `/translate/vocabulary` | GET | 获取生词本列表（分页） |
| `/translate/vocabulary/{id}` | DELETE | 删除一条 |

### main.py 变更
```python
from app.routers import translate
app.include_router(translate.router)
```

### static/index.html 变更
- Header 右侧第 799 行区域新增 `<a href="/translate">🌐 翻译</a>`，顺序：🌐翻译 → 🎙️练习 → 🧠记忆

### 复用组件
- `model_client.chat()` —— 翻译 prompt 直接调用
- `app/routers/tts.py` —— 朗读使用现有 `/tts` 接口
- `app/database.py` —— create_tables() 自动建表（SQLAlchemy 模式）
- warm color CSS 主题变量

### CLAUDE.md / README 更新
- CLAUDE.md：更新"数据表清单"加 vocabulary；更新"API 接口清单"加 /translate 五条
- README：更新功能列表，加入 V0.5 翻译模块

## Ontology (Key Entities)

| Entity | Type | Fields | Relationships |
|---|---|---|---|
| TranslationTool | core | zh_text, en_text, direction, model | User uses TranslationTool |
| Vocabulary | supporting | id, user_id, source_text, translated_text, direction, context, created_at, status | TranslationTool writes to Vocabulary; User has many Vocabulary |
| User | core | user_id | User owns Vocabulary |

## Ontology Convergence

| Round | Entity Count | New | Changed | Stable | Removed | Stability Ratio |
|---|---|---|---|---|---|---|
| 1 | 4 (TranslationTool, TranslationEntry, MemorySystem, User) | 4 | - | - | - | N/A |
| 2 | 4 (TranslationTool, Vocabulary, MemorySystem, User) | 0 | 1 (TranslationEntry→Vocabulary) | 3 | 0 | 100% |
| 3 | 3 (TranslationTool, Vocabulary, User) | 0 | 0 | 3 | 1 (MemorySystem scoped out) | 100% |

本体自 Round 2 起稳定，Round 3 明确移除 MemorySystem（MVP 不接 FSRS），最终 3 个核心/支持实体全部 stable，收敛完毕。

## Interview Transcript

<details>
<summary>Full Q&A (3 rounds)</summary>

### Round 1
**Q:** 这个「翻译」在 Speakeasy 的学习闭环里，到底扮演什么角色？
**A:** 偏向"双向通用翻译工具"，但译文内容也能进入记忆，然后学习
**Ambiguity:** 63% (Goal: 0.55, Constraints: 0.20, Criteria: 0.20, Context: 0.50)

### Round 2
**Q:** 翻译功能在 V0.5 里的战略位置是什么？（走方案 A 新建 FSRS 卡表 / B 复用发音卡 / C 只做收藏 / D 我还没想清）
**A:** （先请求权衡对比）→ V0.5 一个快速上线的辅助工具 MVP（→ 方案 C）
**Ambiguity:** 49% (Goal: 0.70, Constraints: 0.55, Criteria: 0.20, Context: 0.50)

### Round 3
**Q:** 请选一个最能接受的 "翻译 MVP 上线 Day 1" 用户路径（4 方案含 ASCII 预览）
**A:** 独立 /translate 页 + header 入口 + 手动收藏（Recommended）
**Ambiguity:** 17.5% (Goal: 0.85, Constraints: 0.75, Criteria: 0.85, Context: 0.85)

</details>
