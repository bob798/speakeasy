# Speakeasy V0.3 产品规划文档

> 版本定位：认识你
> 状态：规划中
> 前置条件：V0.2b 全部验收通过
> 负责人：Claude（规划）+ Claude Code（执行）
> 最后更新：2026-03-18

---

## 一、版本定位

**V0.3 的核心主题：Alex 开始真正认识你。**

V0.1 实现了对话，V0.2a 加上了声音，V0.2b 让学习留下了痕迹（错误卡片）。但到目前为止，Alex 对你一无所知——每次对话都从零开始，不知道你是做什么的、在练什么、上次聊了什么。

V0.3 要改变这件事。

具体来说，V0.3 交付三个用户可感知的变化：

1. **Alex 知道你是谁** — 职业背景、话题偏好、学习目标注入对话，Alex 的话题和词汇选择开始贴合你的生活
2. **Alex 记得发生过的事** — 每次对话后提取 2-3 条事实存入记忆，下次对话时 Alex 能自然续接
3. **你能看到自己的积累** — 一个页面展示：你的语言档案、正在复习的错误、Alex 记得的事

这不是"更多功能"，而是从"练习工具"到"认识你的朋友"的质变。

---

## 二、竞品对比

### 各产品定位速览

| 产品 | 核心定位 | 记忆深度 | 纠错方式 | 语音支持 | 主要用户 |
|---|---|---|---|---|---|
| **Speakeasy** | AI 英语朋友，零评判，记住你这个人 | 跨会话语义记忆 + FSRS 错误调度 | 无显性纠错，自然示范 | STT + TTS（服务端） | 中国职场人 |
| **Duolingo** | 游戏化课程，习惯养成 | 词汇 SRS（Half-Life Regression），无对话记忆 | 答题对错立即反馈，失去爱心 | 部分练习有发音检测 | 零基础、习惯养成 |
| **Speak** | 语音优先的口语教练，发音评分 | 指标型（发音分数/口语时长），无语义记忆 | 发音评分 + 结构课程 | 核心功能（语音优先） | 亚洲市场，短期提升 |
| **Talkpal** | AI 情景对话，实时纠错 | 会话级别，无跨会话记忆 | **实时显性纠错**（中断对话流） | 文字 + 语音 | 快速口语热身 |
| **Langua** | 极简 AI 对话沙盒，无需注册 | 会话级别，词汇列表 | 无显性纠错 | 核心版本无语音 | 自主探索型学习者 |

### 五维度深度对比

| 维度 | Speakeasy | Duolingo | Speak | Talkpal | Langua |
|---|---|---|---|---|---|
| **记忆能力** | ★★★★★ 跨会话：错误卡片 FSRS + 用户画像 + 事实提取 | ★★☆☆☆ 词汇 SRS，无对话内容记忆 | ★★☆☆☆ 发音指标追踪，无语义记忆 | ★☆☆☆☆ 无持久记忆，每次对话独立 | ★☆☆☆☆ 词汇列表，无跨会话上下文 |
| **个性化程度** | ★★★★★ 职业/话题/错误历史驱动对话内容 | ★★☆☆☆ 固定课程路径 | ★★★☆☆ 发音个性化，课程内容固定 | ★★☆☆☆ 话题模板，无用户画像 | ★☆☆☆☆ 无画像，内容通用 |
| **判断压力** | ★★★★★ 零压力：无评分、无标注、无"你错了" | ★☆☆☆☆ 高压：爱心机制、答题对错立即反馈 | ★★★☆☆ 中：发音评分存在压迫感 | ★★★☆☆ 中：实时纠错打断对话流 | ★★★★☆ 低：对话为主 |
| **会话自然度** | ★★★★★ 自由话题，Alex 风格一致，无脚本 | ★★☆☆☆ 脚本式句子，非真实对话 | ★★★☆☆ 结构化练习，引导感明显 | ★★★☆☆ 情景对话，但无持续关系 | ★★★★☆ 自由对话，但 AI 无记忆 |
| **职场场景适配** | ★★★★☆ 以职场对话为核心场景（V0.3 后更强） | ★☆☆☆☆ 内容偏基础，文化不符 | ★★☆☆☆ 无中国职场语境 | ★★☆☆☆ 通用情景，非职场定制 | ★☆☆☆☆ 无场景设定 |

### Speakeasy 的三个差异化空白

研究发现，四个竞品都没有做到的三件事：

```
1. 无显性纠错（只有 Langua 接近，但无记忆）
   Talkpal / Speak 都会打断对话流进行纠错，制造"考试感"

2. 持久语义记忆 + FSRS 调度（四个产品均没有）
   无一产品记住"你说错了什么"并在未来自然强化
   Duolingo 的 SRS 只针对词汇，不针对你的真实语法错误

3. 中国职场场景专属（四个产品均没有）
   没有产品针对"开会英语 / 写给外方客户的邮件 / 跨文化职场"这类中国职场人真实需要的场景
```

**结论：** Speakeasy 的差异化不是"更好的同类产品"，而是一个全新象限——**记住你这个人的零评判英语朋友**。

---

## 三、V0.3 功能规划

### 3.1 Level 评估

**目标：** 让 Alex 知道你的英语水平，用 CEFR 标准（A1-C2）定位，从而调整对话词汇难度和句子复杂度。

**两种评估方式并行：**

**方式 A：自评问卷（立即可用）**

用户首次使用时填写 5-6 个问题：

```
- 你能描述自己的工作内容吗？（能 / 简单描述 / 不太能）
- 你能理解英文会议的大意吗？（完全能 / 大部分 / 较难）
- 你能用英语写邮件吗？（能且流畅 / 能但费时 / 困难）
...
```

问卷结果映射到 A1-C1 区间，写入 `user_profile.cefr_level`。

**方式 B：对话评估（进阶，V0.3 可选实现）**

用户与 Alex 进行 5-10 轮专门设计的对话，LLM 根据词汇丰富度、语法复杂度、流畅度综合打分，输出 CEFR 等级建议。

对话评估比问卷更准确，但成本更高（需要完整对话 + 一次分析调用）。V0.3 优先实现方式 A，方式 B 作为可选交付。

**写入字段：** `user_profile.cefr_level` (string: "A1"/"A2"/"B1"/"B2"/"C1"/"C2")

**在对话中的体现：** `user_profile.cefr_level` 注入 system prompt，Alex 感知用户水平，B1 用户听 idiom 时 Alex 会稍作解释，C1 用户 Alex 不会刻意简化。

---

### 3.2 用户画像设置

**目标：** 让 Alex 知道你是谁，对话内容开始贴合你的真实生活。

**数据表：** 新增 `user_profile` 表

```python
class UserProfile(Base):
    __tablename__ = "user_profile"

    id               : Mapped[int]      # autoincrement PK
    user_id          : Mapped[str]      # unique
    cefr_level       : Mapped[str]      # "B1" etc, 可为空
    profession       : Mapped[str]      # 职业/行业，自由文本，如 "产品经理，互联网行业"
    topic_prefs      : Mapped[str]      # JSON list，如 ["职场沟通", "科技", "生活日常"]
    learning_goal    : Mapped[str]      # 如 "日常沟通流利" / "英文商务邮件" / "出国面试"
    personality_note : Mapped[str]      # 如 "喜欢幽默轻松的风格" / "希望对话直接、高效"
    created_at       : Mapped[datetime]
    updated_at       : Mapped[datetime]
```

**UI 形式：** 设置页面，表单形式，用户可随时修改。首次进入时显示引导提示（可跳过，跳过则用默认值）。

**注入方式：** `/chat` 接口调用 `build_system_prompt` 时，读取 `user_profile` 注入 system prompt：

```
## 关于这位用户（私有上下文，绝对不要直接提及以下信息）
- 职业：产品经理，互联网行业
- 英语水平：B1
- 话题偏好：职场沟通、科技
- 学习目标：职场英语流利表达
- 风格偏好：幽默轻松
```

---

### 3.3 user_facts 自动提取

**目标：** 每次对话后，LLM 从对话内容里提取 2-3 条具体事实，积累为 Alex 的"对你的记忆"。

**数据表：** 新增 `user_facts` 表

```python
class UserFact(Base):
    __tablename__ = "user_facts"

    id                : Mapped[int]
    user_id           : Mapped[str]     # indexed
    fact              : Mapped[str]     # 一条事实，自然语言，英文，如 "User had a presentation to their boss this week"
    tags              : Mapped[str]     # JSON list，用于过滤，如 ["workplace", "presentation"]
    source_session_id : Mapped[str]     # 可追溯来源
    created_at        : Mapped[datetime]
```

**提取时机：** `/chat/summary` 完成后，异步触发一次 LLM 调用，Prompt 如下：

```
从以下对话中提取用户生活中发生的 2-3 件具体事情，用于 AI 朋友在未来对话中自然提及。

规则：
- 只提取真实发生的事（不是假设、不是练习内容）
- 每条事实一句话，英文，第三人称
- 附上 1-2 个标签（workplace / life / family / learning / travel 等）
- 没有值得记录的事实时返回空数组

对话内容：{conversation}

返回 JSON：
[{"fact": "...", "tags": ["workplace"]}]
```

**注入方式：** `/chat` 接口 `build_system_prompt` 时，取最近 20 条 user_facts，注入 system prompt：

```
## 你记得关于这位用户的事（自然融入对话，不要直接引用原话）
- User had a tough presentation review with their boss last week
- User is preparing for an English interview at a foreign company
- User's team recently switched to a new project management tool
```

**检索策略：** V0.3 使用时间倒序 + 最近 20 条（无需向量检索，规模小于 500 条时关键词覆盖率已足够）。

---

### 3.4 记忆注入：系统整合

`build_system_prompt` 函数升级为三层注入：

```python
async def build_system_prompt(user_id: str) -> str:
    profile = await get_user_profile(user_id)       # 层 1：结构化画像
    facts   = await get_recent_facts(user_id, 20)   # 层 2：LLM 提取事实
    cards   = await get_injectable_cards(user_id, 3) # 层 3：FSRS 语法卡片

    # 按顺序叠加，各层为空时跳过
    ...
```

**三层优先级和截断规则：**

| 层 | 内容 | Token 估算 | 截断策略 |
|---|---|---|---|
| 1 | user_profile（固定） | ~100 tokens | 不截断 |
| 2 | user_facts（最近 20 条） | ~400 tokens | 按时间倒序，总 token 超 400 时截断 |
| 3 | grammar_cards（最多 3 条） | ~150 tokens | 按 FSRS stability 升序，取最多 3 条 |

---

### 3.5 记忆管理页面

**目标：** 用户能看到 Alex 记住了什么，能删除不想保留的内容。

**页面结构（单页，三个 Tab）：**

**Tab 1：我的语言档案**
```
英语水平：B1（中级）  [重新评估]
学习目标：职场英语流利表达
话题偏好：职场沟通、科技、生活日常
职业背景：产品经理，互联网行业
[编辑画像]
```

**Tab 2：正在复习的错误**
```
现有 grammar_cards 列表（V0.2b 已有数据）
每条显示：错误类型 / 出现次数 / 下次复习时间
[删除] 按钮（软删除，status='deleted'）
```

**Tab 3：Alex 记得的事**
```
最近 30 条 user_facts，按时间倒序
每条显示：事实内容 / 来源时间 / 标签
[删除] 按钮
```

**API：**

```
GET  /memory/profile          # 获取 user_profile
PUT  /memory/profile          # 更新 user_profile
GET  /memory/facts            # 获取 user_facts（分页）
DELETE /memory/facts/{id}     # 删除单条 fact
GET  /memory/cards            # 获取 grammar_cards（已有，可复用）
DELETE /memory/cards/{id}     # 软删除 grammar_card（已有）
```

---

### 3.6 Alex 的个性化表现

记忆注入后，Alex 在对话中的具体变化：

**话题关联：**
```
用户画像："产品经理，互联网行业"
→ Alex 主动用产品、用户研究、团队协作相关的例子和词汇
→ 不会举"我昨天去菜场买菜"这种与用户生活无关的例子
```

**事件续接：**
```
user_facts 里有："User had a tough presentation last week"
→ Alex 在新一次对话开头可能说："By the way, how did things go after that presentation?"
→ 不是每次都说（避免机械感），但出现时会让用户感到"Alex 记得我"
```

**词汇难度自适应：**
```
user_profile.cefr_level = "B1"
→ Alex 使用 idiom 时加一句简单解释
→ 不主动使用 C1+ 级别的低频词汇
→ B2 用户则不需要这些辅助，Alex 正常对话
```

**语法针对性：**
```
grammar_cards 注入（V0.2b 已有）
→ Alex 在自然对话中多使用用户的薄弱点对应的正确表达
→ 绝不直接提及或纠正
```

---

## 四、User Stories

> 格式：`US-[编号] As a [角色], I want [目标] so that [价值]`
> 每条 US 对应一个可验证的用户可感知变化。

### Epic A：Alex 知道你是谁（user_profile + Level 评估）

| ID | User Story | 对应 Step | 验收信号 |
|---|---|---|---|
| US-01 | 作为**首次使用的用户**，我想通过 5 分钟问卷告诉 Alex 我的英语水平，让 Alex 从第一句话起就用对难度 | Step 1, 6 | 首次进入弹窗出现，完成后 cefr_level 写入，不再弹 |
| US-02 | 作为**中级用户（B1）**，我希望 Alex 在用 idiom 时顺带解释一下，不让我听懵 | Step 2 | B1 用户 system prompt 含水平标注，LLM 回复风格对应调整 |
| US-03 | 作为**产品经理**，我希望 Alex 举的例子是开会、写邮件、跨部门协作，不是买菜烹饪 | Step 2 | system prompt 含职业注入，对话话题贴近职场 |
| US-04 | 作为**学习目标明确的用户**，我想设置"我要准备英文面试"，让 Alex 知道我在练什么方向 | Step 1, 2 | learning_goal 写入并注入 system prompt |
| US-05 | 作为**已设置画像的用户**，我想随时回来修改职业或偏好，保持 Alex 的认知是最新的 | Step 5 | 记忆管理页语言档案 Tab 可编辑，保存后 Alex 对话即生效 |

### Epic B：Alex 记得发生的事（user_facts 自动提取）

| ID | User Story | 对应 Step | 验收信号 |
|---|---|---|---|
| US-06 | 作为**持续使用的用户**，我希望对话结束后 Alex 自动记下"我上周有重要演示"，不用我手动记 | Step 3 | /chat/summary 后 user_facts 表新增 0-3 条，无感进行 |
| US-07 | 作为**回到 Alex 的用户**，我希望 Alex 开场时能自然说"你上次提到的那个演示，后来怎样了？"，感受到被记得 | Step 4 | user_facts 注入 system prompt，LLM 能自然续接历史事件 |
| US-08 | 作为**注重隐私的用户**，我想删掉 Alex 记住的某件事，不让它再出现在对话里 | Step 5 | 记忆管理页 Alex 记得的事 Tab，删除后不再注入 |

### Epic C：你能看到自己的积累（记忆管理页面）

| ID | User Story | 对应 Step | 验收信号 |
|---|---|---|---|
| US-09 | 作为**使用 3 个月的用户**，我想看到一张"Alex 对我的认知画像"，感受到积累带来的成就感 | Step 5 | 记忆管理页语言档案 Tab 正确展示 profile |
| US-10 | 作为**关注语法进步的用户**，我想看到 Alex 正在帮我强化哪些语法点，知道自己哪里在被悄悄纠正 | Step 5 | 错误 Tab 展示 grammar_cards，含错误类型 / 出现次数 |
| US-11 | 作为**不想被某条规则烦扰的用户**，我想删掉一个语法卡片，让它不再在对话里出现 | Step 5 | 删除 grammar_card 后不再注入 system prompt |

---

## 五、开发计划

### 5.1 依赖关系图

```
Step 1（数据层）
    │
    ├─► Step 2（profile 注入）── 独立可并行
    │
    └─► Step 3（user_facts 表 + 提取）
            │
            └─► Step 4（facts 注入）── 依赖 Step 3
                    │
                    └─► Step 5（记忆管理前端）── 依赖 Steps 1+3+4
                            │
                            └─► Step 6（Level 评估引导 UI）── 依赖 Step 1+5
```

**可并行执行：** Step 2 和 Step 3 均依赖 Step 1，可在 Step 1 完成后同时开发。

### 5.2 开发序列

| 阶段 | Step | 核心交付 | 依赖 | 测试文件 |
|---|---|---|---|---|
| 阶段一：数据基础 | Step 1 | user_profile 表 + GET/PUT /memory/profile + POST /assessment/self | 无 | test_v03_step1.py |
| 阶段二：后端注入 | Step 2 | profile 注入 system prompt | Step 1 | test_v03_step2.py |
| 阶段二：后端注入 | Step 3 | user_facts 表 + /chat/summary 后自动提取 + GET/DELETE /memory/facts | Step 1 | test_v03_step3.py |
| 阶段三：整合注入 | Step 4 | facts 注入 system prompt + 三层注入完整联调 | Steps 2+3 | test_v03_step4.py |
| 阶段四：前端呈现 | Step 5 | 记忆管理页（三 Tab：画像 / 错误 / 记忆） | Step 4 | test_v03_e2e.py |
| 阶段四：前端呈现 | Step 6 | Level 评估引导弹窗（首次进入触发） | Step 5 | test_v03_e2e.py（追加）|

### 5.3 User Story → Step 覆盖矩阵

| US | Step 1 | Step 2 | Step 3 | Step 4 | Step 5 | Step 6 |
|---|---|---|---|---|---|---|
| US-01 Level 评估问卷 | ✅ API | | | | | ✅ UI |
| US-02 水平难度自适应 | | ✅ | | | | |
| US-03 职业话题匹配 | | ✅ | | | | |
| US-04 学习目标注入 | ✅ | ✅ | | | | |
| US-05 画像可随时编辑 | | | | | ✅ | |
| US-06 对话后自动提取事实 | | | ✅ | | | |
| US-07 续接历史事件 | | | | ✅ | | |
| US-08 删除 Alex 记住的事 | | | ✅ | | ✅ | |
| US-09 查看认知画像 | | | | | ✅ | |
| US-10 查看正在强化的语法点 | | | | | ✅ | |
| US-11 删除语法卡片 | | | | | ✅ | |

### 5.4 MVP 定义

**V0.3 MVP（必须交付）：** Steps 1 → 2 → 3 → 4（全后端完成）

用户可感知的核心变化：Alex 开始知道你是谁，开始记得发生了什么。不需要记忆管理页，用户通过对话本身能感受到个性化。

**V0.3 完整版（Full）：** MVP + Steps 5 + 6

增加可见性：用户能看到积累，能控制画像和记忆。完整达成"越聊越懂你"的用户感知。

### 5.5 风险点

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| LLM 提取 user_facts 质量不稳定（提取出无意义内容） | US-07 体验差，Alex "乱"续接 | Prompt 加严格过滤规则；允许返回空数组；管理页面可手动删除 |
| user_profile 字段为空时 system prompt 注入乱码 | Alex 行为异常 | Step 2 测试覆盖"部分字段为空"case；build_system_prompt 各层独立 guard |
| Playwright e2e 测试在 CI 中不稳定 | Step 5/6 验收困难 | Step 5/6 优先手动验收，e2e 作辅助；API 层测试保证后端正确性 |
| system prompt 过长导致 token 超限 | 对话失败 | 三层注入有 token 估算截断逻辑（Section 3.4 已设计） |

---

## 六、Step 拆解

### Step 1：数据层 — user_profile 表 + Level 评估接口

**功能描述：**

- 创建 `user_profile` 表（SQLAlchemy model）
- 实现 `GET /memory/profile` 和 `PUT /memory/profile` 接口
- 实现 Level 自评问卷 API（`POST /assessment/self`，接收问卷答案，返回 CEFR 等级建议）

**验收标准：**

- `PUT /memory/profile` 能成功写入 profession、topic_prefs、learning_goal、cefr_level
- `GET /memory/profile` 返回正确字段
- `POST /assessment/self` 接收问卷答案，返回 `{"cefr_level": "B1", "description": "..."}`
- cefr_level 写入 user_profile 后可读取

**测试要求：**

- 测试文件：`tests/test_v03_step1.py`
- user_id：`test_user_v03_s1`
- 覆盖：创建 profile、更新 profile、问卷评估写入 cefr_level

---

### Step 2：记忆注入 — user_profile 注入 system prompt

**功能描述：**

- 升级 `build_system_prompt`，读取 `user_profile` 并注入
- 当 user_profile 为空或字段为空时，优雅跳过对应部分
- 覆盖 `/chat` 接口，确认注入生效

**验收标准：**

- 有 user_profile 时，`/chat` 返回的 system prompt 包含职业、水平、话题偏好信息
- user_profile 不存在时，system prompt 与 V0.2b 行为一致（无副作用）
- 注入内容格式：中文标注"私有上下文，绝对不要直接提及"

**测试要求：**

- 测试文件：`tests/test_v03_step2.py`
- 用 Mock 拦截 LLM 调用，验证 system prompt 内容
- 覆盖：有 profile / 无 profile / profile 字段部分为空三种情况

---

### Step 3：user_facts 表 + 自动提取

**功能描述：**

- 创建 `user_facts` 表
- 在 `/chat/summary` 完成后，异步触发 LLM 提取 2-3 条事实，写入 user_facts
- 实现 `GET /memory/facts` 接口（分页，按时间倒序）
- 实现 `DELETE /memory/facts/{id}` 接口

**验收标准：**

- `/chat/summary` 调用后，`user_facts` 表新增 0-3 条记录
- LLM 提取失败时，静默忽略（不影响 summary 正常返回）
- `GET /memory/facts` 返回正确数据，含 fact、tags、created_at、source_session_id
- `DELETE /memory/facts/{id}` 物理删除或软删除（V0.3 物理删除即可）

**测试要求：**

- 测试文件：`tests/test_v03_step3.py`
- Mock LLM 提取调用，验证写入逻辑
- 验证提取失败时 summary 接口不受影响

---

### Step 4：user_facts 注入 system prompt

**功能描述：**

- 升级 `build_system_prompt`，读取最近 20 条 user_facts，注入 system prompt
- 实现截断逻辑：总注入内容超过 token 估算阈值时，按时间倒序截断

**验收标准：**

- 有 user_facts 时，`/chat` system prompt 包含最近事实
- user_facts 超过 20 条时，只注入最近 20 条
- user_facts 为空时，system prompt 无对应注入块（无空白段落）
- 三层注入（profile + facts + grammar_cards）同时存在时，格式正确，无重复内容

**测试要求：**

- 测试文件：`tests/test_v03_step4.py`
- 覆盖：0 条 / 少量 / 超过 20 条三种 user_facts 情况
- 覆盖：三层同时注入的 system prompt 格式验证

---

### Step 5：记忆管理页面（前端）

**功能描述：**

- 新增「我的档案」页面入口（导航或设置按钮）
- 实现三个 Tab：语言档案 / 正在复习的错误 / Alex 记得的事
- 语言档案 Tab：显示 + 编辑 user_profile 表单
- 错误 Tab：复用 V0.2b grammar_cards 数据，新增删除功能
- 记忆 Tab：显示 user_facts 列表，支持删除单条

**验收标准：**

- 三个 Tab 数据正确加载
- 编辑语言档案后保存，刷新页面数据仍保留
- 删除 grammar_card 后，该 card 不再出现在列表中
- 删除 user_fact 后，该条目不再出现
- 首次使用（无数据）时，各 Tab 显示合理的空状态提示

**测试要求：**

- 测试文件：`tests/test_v03_e2e.py`（e2e，Playwright）
- 覆盖：编辑画像 → 保存 → 刷新 → 数据仍在
- 覆盖：删除 grammar_card → 列表消失
- 覆盖：删除 user_fact → 列表消失
- 覆盖：空状态各 Tab 的 UI 表现

---

### Step 6：Level 评估引导 UI（前端）

**功能描述：**

- 首次进入应用时（user_profile.cefr_level 为空），显示一次引导弹窗
- 弹窗内容：5-6 个自评问题，可跳过
- 完成后写入 cefr_level，关闭弹窗
- 已完成评估的用户不再显示弹窗（状态存 localStorage + 后端 user_profile）

**激活入口检查：**

```
功能：Level 评估引导
激活入口：
  [x] 用户主动操作（点击"开始评估"按钮）
  [x] 页面加载时恢复（DOMContentLoaded 检查 user_profile.cefr_level）
  [x] 跳过后不再显示（localStorage 标记 + 后端状态双重检查）
  [x] 已评估用户不显示
测试覆盖：
  [x] 单元/API：POST /assessment/self 写入逻辑
  [x] e2e：首次加载弹窗出现 → 完成评估 → 刷新不再出现
  [x] e2e：跳过 → 刷新不再出现
```

**验收标准：**

- 首次进入显示弹窗，完成问卷后弹窗消失，user_profile.cefr_level 已写入
- 刷新页面不再出现弹窗
- 跳过后刷新不再出现弹窗
- 已有 cefr_level 的用户进入时不显示弹窗

**测试要求：**

- 追加到 `tests/test_v03_e2e.py`
- 覆盖所有四个激活入口

---

## 七、上线版本建议

### 结论

**V0.2b 完成后即可向第一批真实用户开放。**

不必等到 V0.3。

### 理由

**V0.2b 已交付的功能足够产生真实价值：**

| 功能 | 用户价值 |
|---|---|
| 自由文本对话（Alex） | 随时可以开口说英语，无需安排时间和场地 |
| 语音输入 + 语音输出 | 接近真实对话体验，不是打字练习 |
| 对话复盘（错误 + 亮点） | 练完有收获，不是聊完就消失 |
| FSRS 错误调度 | 反复出现的错误会被 Alex 自然强化，不需要用户主动管理 |
| 零评判原则 | 敢开口是第一步，V0.2b 已经解决这个核心障碍 |

**V0.3 是"更好"，不是"必须有才能用"：**

V0.3 让 Alex 更了解你，但即便 Alex 不了解你，他仍然是一个比任何现有产品都更无压力、更自然的练习对象。

**早开放的理由：**

- 真实用户反馈比规划更有价值，V0.3 的功能优先级应该由用户行为决定
- 记忆系统（user_profile + user_facts）建立在真实对话数据之上，越早积累越好
- V0.2b 的核心差异化（零评判 + FSRS + 语音）已经构成完整的产品假设，需要验证

**建议的开放方式：**

小范围（5-10 个真实用户）内测，观察：
- 用户是否主动查看复盘（检验复盘是否有价值）
- 用户对话后是否回来（检验 FSRS 注入是否产生效果）
- 用户卡在哪里（为 V0.3 优先级排序提供依据）

这比在封闭开发 V0.3 后再开放，能节省 1-2 个版本的错误迭代。

---

## 附：技术决策备忘

| 决策 | 结论 | 依据 |
|---|---|---|
| 记忆方案 | user_profile + user_facts（SQLite），不引入 mem0 | mem0 三项否决，SQLite 五项全绿 |
| 向量检索 | 不引入（user_facts < 500 条时关键词检索足够） | V0.4+ 备选：sqlite-vec |
| user_facts 检索 | 时间倒序 + 最近 20 条 | 规模小，text 检索已覆盖 80% 场景 |
| CEFR 评估方式 | 自评问卷（V0.3 主线）+ 对话评估（可选） | 问卷零成本，对话评估后期补充 |
| 记忆管理页面入口 | 独立页面（非模态弹窗） | 内容量大，需要完整页面空间 |
