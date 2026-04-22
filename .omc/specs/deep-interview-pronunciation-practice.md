# Deep Interview Spec: BBC Learning English 发音练习模块

## Metadata
- Interview ID: pronunciation-practice-2026-04-16
- Rounds: 9
- Final Ambiguity Score: 17%
- Type: brownfield
- Generated: 2026-04-16
- Threshold: 20%
- Status: PASSED

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.90 | 0.35 | 0.315 |
| Constraint Clarity | 0.80 | 0.25 | 0.200 |
| Success Criteria | 0.80 | 0.25 | 0.200 |
| Context Clarity | 0.75 | 0.15 | 0.113 |
| **Total Clarity** | | | **0.828** |
| **Ambiguity** | | | **17%** |

## Goal

为 Speakeasy 新增「发音练习」模块：用户提供 Bilibili 视频链接（或手动粘贴字幕文本），系统自动解析字幕；用户在字幕列表中标注陌生词汇和句子，然后逐句进行发音/连读跟读练习——听标准 TTS 发音、自己录音、回放对比，自判满意后进入下一句。标注的内容进入 FSRS 间隔复习系统，到期提醒再练。

### 核心用户旅程
```
粘贴 B站链接 → 自动提取字幕 → 浏览字幕列表 → 标注生词/难句
→ 进入练习模式 → 听 TTS 标准发音 → 跟读录音 → 回放对比
→ 自判满意 → 下一句 → 标注内容进入 FSRS 复习
```

## Constraints

### 一期（V0.4 或独立版本）
- **内容输入**：链接优先自动解析，失败时提示用户手动粘贴字幕文本
- **发音评估**：录音回放 + TTS 对比，用户自判（不接入外部评分 API）
- **技术栈**：复用现有 FastAPI + SQLite + 前端原生 JS 架构
- **UI**：新建 `practice.html` 独立页面，从主页导航栏进入
- **后端复用**：TTS 接口(`/tts`)、Web Audio 录音、FSRS 调度引擎

### 二期
- **发音评估升级**：对接外部发音评估 API（如 Azure Speech Assessment）
- **字幕提取增强**：更多视频平台支持

### 技术约束
- B站反爬严格，字幕提取可能不稳定，手动粘贴作为兜底方案
- 现有 TTS 使用 edge-tts（Microsoft Neural Voices），发音质量足够做标准参考
- 录音使用前端 Web Audio API（已有 VAD 基础设施可参考）
- FSRS 复用现有 `py-fsrs` 实现和 `grammar_cards` 模式

## Non-Goals
- ❌ 不做视频播放器（只提取字幕文本）
- ❌ 一期不做 AI 发音评分（二期再接入）
- ❌ 不做课程体系/教学大纲（这是练习工具，不是课程平台）
- ❌ 不修改现有对话功能（Alex 聊天流程不变）
- ❌ 不做实时语音对比（先录完再回放对比）

## Acceptance Criteria

### 内容输入
- [ ] 用户粘贴 B站视频链接，系统尝试提取字幕并展示
- [ ] 字幕提取失败时，显示手动粘贴文本框，用户可粘贴字幕文本
- [ ] 字幕按句子/段落分行展示，支持滚动浏览

### 标注功能
- [ ] 用户可点击/长按标注字幕中的生词或整句为"需练习"
- [ ] 标注的内容高亮显示，可取消标注
- [ ] 标注列表可独立查看（练习队列）

### 发音练习
- [ ] 选中标注内容后进入练习模式
- [ ] 点击播放：TTS 朗读标准发音（复用现有 /tts 接口）
- [ ] 点击录音：用户跟读并录音
- [ ] 点击回放：播放用户录音
- [ ] 可反复听 TTS + 反复录音对比，不限次数
- [ ] 用户手动点击"下一句"进入下一个标注项

### FSRS 复习闭环
- [ ] 练习完成的标注内容自动创建 FSRS 卡片
- [ ] FSRS 卡片到期时在练习页提醒用户复习
- [ ] 复习时重新进入录音对比练习流程

### 页面与导航
- [ ] 新建 `practice.html` 独立页面
- [ ] 主页 `index.html` 导航栏新增练习入口
- [ ] 页面风格与现有暖色调一致

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| 需要 AI 评分才能练发音 | Contrarian: 录音对比自判能否解决 80% 需求？ | 一期录音对比自判，二期再接外部 API |
| B站字幕可以轻松提取 | 用户不确定视频是否有 CC 字幕 | 链接优先尝试，失败时手动粘贴兜底 |
| 功能应融入聊天页 | 交互模型完全不同，会互相干扰 | 新建独立 practice.html 页面 |
| 练完就结束 | 练一次不够，需要长期记忆 | 标注内容进入 FSRS 间隔复习 |

## Technical Context

### 现有可复用基础设施
- **TTS**: `/tts` 接口 (edge-tts)，支持 3 种语音 + 3 种语速 → 直接用于标准发音播放
- **录音**: 前端 Web Audio API + VAD 基础设施 (`static/js/stt-provider.js`) → 改造为纯录音+回放
- **FSRS**: `py-fsrs` + `grammar_cards` 表模式 → 新建 `pronunciation_cards` 表或扩展卡片类型
- **前端模式**: 原生 HTML/JS/CSS，暖色调设计系统 → practice.html 遵循同一风格
- **数据库**: SQLite + SQLAlchemy → 新增字幕/练习相关表

### 需要新建的部分
- **字幕解析服务**: 解析 B站链接提取字幕（可能需要调用 B站 API 或第三方库）
- **练习数据模型**: 存储字幕内容、标注项、练习记录
- **practice.html**: 全新前端页面
- **练习相关 API**: 字幕解析、标注管理、练习记录、FSRS 卡片创建

## Ontology (Key Entities)

| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| User | core domain | user_id | has many PracticeSessions, has many PronunciationCards |
| BilibiliVideo | external source | url, bv_id, title | has one SubtitleSet |
| SubtitleSet | core domain | video_id, source(auto/manual), raw_text, parsed_lines[] | belongs to BilibiliVideo, has many SubtitleLines |
| SubtitleLine | core domain | index, text, start_time, end_time | belongs to SubtitleSet, can be marked |
| VocabularyMark | core domain | line_id, word_or_phrase, position | belongs to SubtitleLine, creates PronunciationCard |
| PracticeSession | core domain | user_id, subtitle_set_id, started_at, progress | belongs to User, has many PracticeAttempts |
| PracticeAttempt | supporting | mark_id, recording_blob, attempt_number, created_at | belongs to PracticeSession and VocabularyMark |
| PronunciationCard | core domain | user_id, content, example_sentence, fsrs_card_data, status | belongs to User, scheduled by FSRS |
| TTS (existing) | external system | voice, speed, audio_cache | provides standard pronunciation |
| Alex (existing) | core domain | persona, system_prompt | unchanged, not directly involved |

## Ontology Convergence

| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 5 | 5 | - | - | N/A |
| 2 | 7 | 2 | 2 | 3 | 71% |
| 3 | 8 | 1 | 0 | 7 | 88% |
| 4-6 | 9 | 1 | 0 | 8 | 89% |
| 7 | 10 | 1 | 0 | 9 | 90% |
| 8-9 | 10 | 0 | 0 | 10 | 100% |

## Interview Transcript
<details>
<summary>Full Q&A (9 rounds)</summary>

### Round 1
**Q:** 你说'有些单词、句子、发音、连读不会'——当你在 Bilibili 看 BBC Learning English 视频时，遇到不会的内容，你理想中希望 Speakeasy 怎么帮你？
**A:** 主要练发音/连读
**Ambiguity:** 82% (Goal: 0.30, Constraints: 0.10, Criteria: 0.10, Context: 0.20)

### Round 2
**Q:** 你说核心是练发音和连读。具体来说，你想象中的练习场景是什么样的？
**A:** 提供bilibili链接，ai自动解析字幕，我可以标注陌生词汇及句子，以及多次练习发音、连读
**Ambiguity:** 68% (Goal: 0.60, Constraints: 0.15, Criteria: 0.15, Context: 0.25)

### Round 3
**Q:** 当你说'多次练习发音、连读'时，具体的交互是怎样的？你跟读一句话后，Speakeasy 应该做什么？
**A:** 跟读 + AI 评分反馈
**Ambiguity:** 59% (Goal: 0.75, Constraints: 0.20, Criteria: 0.20, Context: 0.30)

### Round 4 (Contrarian Mode)
**Q:** 你希望 AI 评分发音，但这需要专业的发音评估 API。如果换一种方式——录音回放 + TTS 对比自判，能解决 80% 的问题吗？
**A:** 一期录音对比，二期再对接外部 API
**Ambiguity:** 48% (Goal: 0.80, Constraints: 0.50, Criteria: 0.25, Context: 0.35)

### Round 5
**Q:** Bilibili 字幕提取是整个功能的入口。你平时看的 BBC Learning English 视频，字幕情况是怎样的？
**A:** 不确定
**Ambiguity:** 47% (Goal: 0.80, Constraints: 0.50, Criteria: 0.25, Context: 0.40)

### Round 6 (Simplifier Mode)
**Q:** 想象你用这个功能练了一句话的发音。什么时候你会觉得'这句练得差不多了，可以下一句了'？
**A:** 自己觉得像就行
**Ambiguity:** 40% (Goal: 0.80, Constraints: 0.50, Criteria: 0.55, Context: 0.40)

### Round 7
**Q:** 字幕来源不确定，那我们一期用最简单的方式解决输入问题。你接受哪种方式？
**A:** 链接优先，手动兜底
**Ambiguity:** 31% (Goal: 0.85, Constraints: 0.70, Criteria: 0.60, Context: 0.45)

### Round 8
**Q:** 你标注的生词和句子，练完之后应该怎么处理？
**A:** 进入 FSRS 复习
**Ambiguity:** 25% (Goal: 0.85, Constraints: 0.70, Criteria: 0.80, Context: 0.55)

### Round 9
**Q:** 功能入口方案：新建 practice.html 独立页面，从主页导航进入。是否同意？
**A:** 同意，继续
**Ambiguity:** 17% (Goal: 0.90, Constraints: 0.80, Criteria: 0.80, Context: 0.75)

</details>
