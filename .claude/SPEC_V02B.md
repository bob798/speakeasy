# Speakeasy V0.2b 规格文档

> 版本定位：学习闭环
> 前置条件：V0.2a 全部验收通过，sessions / messages 表已存在
> 负责人：Claude（规划）+ Claude Code（执行）
> Human 职责：验收最终结果

---

## 一、版本目标

| 功能 | 核心价值 |
|---|---|
| 对话复盘 | 把聊天时间变成有记录的成长 |
| FSRS 记忆调度 | 科学安排错误复习时机 |
| 点击提问 UI | 不懂的词一键发问 |

**交付后用户感知：**
- 聊完有总结（复盘）
- 知道自己哪里出错、怎么改
- Alex 开始在对话里强化薄弱点（FSRS 注入）

---

## 二、数据表设计

### 2.1 grammar_cards

```python
class GrammarCard(Base):
    __tablename__ = "grammar_cards"

    id             : Mapped[int]       # autoincrement PK
    user_id        : Mapped[str]       # indexed
    key            : Mapped[str]       # 唯一标识 snake_case，如 "go_went"
    content        : Mapped[str]       # 错误描述，中文
    example_wrong  : Mapped[str]       # 用户原话（最近一次出错）
    example_right  : Mapped[str]       # 纠正后的表达
    explanation_zh : Mapped[str]       # 中文解释
    frequency      : Mapped[int]       # 累计出现次数，默认 1
    fsrs_card_data : Mapped[str]       # py-fsrs Card 序列化 JSON，pending 时为空字符串
    status         : Mapped[str]       # 'pending' | 'active' | 'deleted'，默认 'pending'
    created_at     : Mapped[datetime]
    updated_at     : Mapped[datetime]

    __table_args__ = (UniqueConstraint("user_id", "key"),)
```

**状态机：**
```
首次出现  → status='pending'，fsrs_card_data=''，frequency=1
第二次出现 → status='active'，创建 FSRS Card，frequency=2
用户删除  → status='deleted'（软删除）
```

### 2.2 session_reviews

```python
class SessionReview(Base):
    __tablename__ = "session_reviews"

    id             : Mapped[int]
    session_id     : Mapped[str]    # FK → sessions.id，unique
    user_id        : Mapped[str]
    errors         : Mapped[str]    # JSON
    highlights     : Mapped[str]    # JSON
    stats          : Mapped[str]    # JSON：turns, duration_seconds
    is_user_rated  : Mapped[bool]   # 用户是否已在复盘页手动打分，默认 False
    created_at     : Mapped[datetime]
```

---

## 三、复盘功能

### 3.1 设计原则

- 形式：朋友的总结便签，不是老师的红笔批注
- 错误：用"更地道的说法"引导，不用"你错了"定性
- 亮点：独立展示，不被错误板块淹没
- 降级：LLM 失败时展示今日一句  **SPEC-07**

### 3.2 触发时机

> **SPEC-01**：结束对话触发 · **SPEC-02**：超过10轮轻提示 · **SPEC-03**：历史记录复盘入口

- 用户点击「结束对话」→ 自动触发
- 对话超过 10 轮 → 顶部轻提示（可忽略）
- 历史记录进入 → 右上角「查看复盘」（如有数据）

### 3.3 复盘卡片三层结构

**SPEC-04**  第一层：摘要卡（默认展示，异步加载）
```
加载中：⏳ Alex 正在整理今天的对话...

加载完成：
  🎯 今天聊了 N 轮，约 N 分钟
  📌 Alex 注意到 N 个可以改进的地方
  ✨ N 个你用得很地道的表达
  [查看详情] [下次再说]

降级：
  ✨ 今日一句
  {今日一句内容}
```

**SPEC-05**  第二层：错误详情（点击「查看详情」展开）
```
错误类型：出现 N 次
你说：   原句
更地道：  纠正后
为什么？  中文解释
[👍 我记住了]  [🔁 再给我讲一遍]
```

👍 → FSRS Rating.Good
🔁 → FSRS Rating.Again

**SPEC-06**  第三层：亮点时刻（独立板块）
```
✨ 今天用得很地道
你说：   原句
👏 中文夸赞
```

### 3.4 进度追踪

从 `grammar_cards.frequency` 计算，展示每个错误的出现趋势。

---

## 四、LLM 分析 Prompt  <!-- SPEC-08 -->

文件位置：`app/prompts/review.py`

```python
REVIEW_PROMPT = """
你是一个专业的英语学习分析助手。
分析以下对话中用户（role: user）的英语表达，严格按 JSON 格式返回。

对话内容：
{conversation}

分析规则：
1. 只分析明确的语法错误（时态、主谓一致、冠词、不规则动词等）
2. 排除正确用法，例如：
   - "I go to the gym every day" → 一般现在时表习惯，正确，不报告
   - "I go to the meeting yesterday" → 过去时间用一般现在时，错误，报告
3. 识别地道的口语表达作为亮点
4. 置信度低于 0.7 的不返回
5. 每类错误最多报告 1 个最典型的例子

返回格式：
{
  "errors": [
    {
      "key": "唯一标识 snake_case，如 go_went",
      "type": "grammar",
      "subtype": "past_tense",
      "original": "用户原话（完整句子）",
      "corrected": "纠正后的完整句子",
      "explanation_zh": "中文解释，1-2 句话",
      "count": 出现次数,
      "confidence": 0.0-1.0
    }
  ],
  "highlights": [
    {
      "original": "用户原话",
      "praise_zh": "中文夸赞，说明为什么地道"
    }
  ]
}

只返回 JSON，不要任何其他内容。
"""
```

---

## 五、FSRS 调度

### 5.1 依赖
```bash
pip install fsrs
```

### 5.2 两个入口优先级  <!-- SPEC-09：用户显式评分入口 -->

```
入口 1（高优先级）：用户在复盘页显式操作
  👍 → Rating.Good
  🔁 → Rating.Again
  操作后设置 session_reviews.is_user_rated = true

入口 2（低优先级）：分析层隐式信号
  对话中再次出现  → Rating.Hard
  本次未出现      → Rating.Good
  如 is_user_rated=true，则跳过本次 session 的入口 2
```

### 5.3 注入条件  <!-- SPEC-10：记忆注入 Alex system prompt -->

```python
# due <= now 的 active card 才注入
# 按 stability 升序，最多 3 条
```

### 5.4 System Prompt 构建

```python
async def build_system_prompt(user_id: str) -> str:
    cards = await get_injectable_cards(user_id, limit=3)
    if not cards:
        return SYSTEM_PROMPT

    memory_lines = [
        f"该用户有一个待改善的语法习惯：{card.content}。"
        f"在对话中自然多使用正确形式即可，绝对不要直接指出或提及这条记录。"
        for card in cards
    ]
    return SYSTEM_PROMPT + "\n\n## About This User（私有上下文，绝对不要直接提及）\n" + \
           "\n".join(f"- {l}" for l in memory_lines)
```

---

## 六、API 接口

<!-- 接口覆盖：SPEC-01~SPEC-10，以下接口为实现手段，非独立功能点 -->

| 接口 | 方法 | 说明 |
|---|---|---|
| `/chat` | POST | 升级：注入 grammar_cards |
| `/chat/summary` | POST | 升级：返回复盘数据，触发 FSRS |
| `/review/{session_id}` | GET | 获取复盘数据 |
| `/review/{session_id}/rate` | POST | 用户评分，更新 FSRS |

**POST /chat/summary Response（正常）：**
```json
{
  "type": "review",
  "stats": {"turns": 14, "duration_seconds": 480},
  "errors": [...],
  "highlights": [...]
}
```

**POST /chat/summary Response（降级）：**
```json
{
  "type": "tip",
  "tip": "今日一句内容..."
}
```

**POST /review/{session_id}/rate：**
```json
// Request
{"card_key": "go_went", "rating": "good"}

// Response
{"next_review": "2025-03-10T14:30:00Z"}
```

---

## 七、不在 V0.2b 范围内

```
❌ Level 评估
❌ Preference 提取
❌ 记忆管理页面
❌ 无痕模式
❌ Plugin Registry
```

---

## 八、验收标准

### 接口验收（自动化）
- [ ] POST /chat/summary 返回 type="review"
- [ ] POST /chat/summary LLM 失败时返回 type="tip"
- [ ] GET /review/{session_id} 返回完整复盘数据
- [ ] POST /review/{session_id}/rate 更新 FSRS Card
- [ ] POST /chat system prompt 包含到期 grammar_cards

### 行为验收（Human 最终验收）
- [ ] 复盘：错误正确展示，中文解释清晰
- [ ] 复盘：亮点独立，不与错误混排
- [ ] 复盘：👍/🔁 操作后下次复习时间正确
- [ ] 复盘：LLM 失败优雅降级
- [ ] 记忆：两次相同错误后，第三次对话 Alex 有针对性
- [ ] 点击提问：Alex 用简单语言重新解释
