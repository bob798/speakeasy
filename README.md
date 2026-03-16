# Speakeasy

> 你的英语水平够用。卡住你的不是知识，是开口的那一秒。

[English](./README_EN.md)

---

## 这个产品在解决什么

中国职场人的英语卡壳，通常不是因为不会——是因为怕。

怕说错被人笑，怕发音不标准，怕语法出错显得不专业。市面上的学习 App 在这件事上反而帮了倒忙：评分、纠错、失去爱心，让人开口前先紧张。练得越多，越怕开口。

**Speakeasy 的切入点不是"教你英语"，而是"帮你不再怕开口"。**

---

## Speakeasy 是什么

一个有记忆的英语母语朋友，叫 Alex。

你们聊你真实生活里的事——今天的会议、遇到的麻烦、周末去了哪里。Alex 永远不纠错你，但你不知不觉说得越来越准。Alex 记得你说过的事，下次自然续接。Alex 知道你在练什么，话题和词汇开始贴合你的工作和生活。

不是课程，不是练习题，不是 AI 老师。**是朋友。**

---

## 和直接用 ChatGPT 练英语有什么区别

| | ChatGPT | Speakeasy（Alex） |
|---|---|---|
| 记得你说过什么？ | 不记得，下次重头开始 | 记得。会追问上次那件事后来怎样了 |
| 记得你的语法习惯？ | 不记得 | 记得，会在对话中自然多用正确表达 |
| 知道你是做什么的？ | 不知道 | 知道，话题会往你的职业场景靠 |
| 会纠错吗？ | 会，而且很直接 | 不会。他用自然示范代替纠错 |
| 适合练什么？ | 什么都行，但没有积累 | 长期口语习惯养成，尤其是职场英语 |

---

## 核心机制

```
你说："Yesterday I go to a meeting with my boss..."
                        ↓
Alex 不纠错，自然回应：
"Oh that sounds tough — how did the meeting go?
 I went to a really long one last week too..."
                        ↓
对话结束，Alex 生成复盘：
  - 今天说得地道的表达（你做对了什么）
  - 可以更自然的地方（不是"你错了"，是"更好的说法"）
                        ↓
下次对话，Alex 记得：
  - 你有过去时态的问题（悄悄在对话里多用 went/had/was）
  - 你上次和老板开会很紧张（可能自然问一句"那次会后来怎么样了？"）
  - 你是产品经理，话题往产品、团队、用户研究方向靠
```

**三个设计原则：**

| 原则 | 是什么 | 不是什么 |
|---|---|---|
| **零评判** | 没有评分、没有标注、没有"你应该说..." | 不是"宽松版老师" |
| **自然习得** | Alex 在回复里植入正确表达，你在接收中吸收 | 不是隐藏的语法课 |
| **Alex 记住你** | 错误历史 + 你的生活事件 + 你的职业画像 | 不只是对话历史 |

---

## Alex 的记忆是怎么工作的

```
每次对话之后：
  对话内容
     │
     ├─► grammar_cards   反复出现的语法错误
     │   （FSRS 算法调度：什么时候在对话里重点强化）
     │
     ├─► user_facts      发生了什么事
     │   LLM 提取 2-3 条："用户本周有重要演示"
     │
     └─► user_profile    你是谁
         职业背景 / 学习目标 / 话题偏好 / 英语水平

下次对话开始时，三层记忆注入 Alex 的上下文：
Alex 知道你犯过什么错、上周发生了什么、你在练什么目标
```

这不是技术设计，是"Alex 认识你"的实现方式。

---

## 当前状态

| 版本 | 功能 |
|---|---|
| V0.1 ✅ | 文本对话（Alex 角色）+ 今日一句 + 多模型支持 |
| V0.2a ✅ | 语音输入 STT + 语音输出 TTS + 流式输出 + 对话历史持久化 |
| V0.2b ✅ | 对话复盘（错误分析 + 亮点）+ FSRS 错误调度 + 点击追问 UI |
| V0.3 🔧 | 用户画像 + Level 评估 + 跨会话事实记忆 + 记忆管理页面 |

---

## 快速启动

```bash
# 1. 克隆
git clone https://github.com/your-username/speakeasy.git
cd speakeasy

# 2. 安装依赖
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env，四选一：
# MODEL_PROVIDER=anthropic / deepseek / volcengine / zhipu
```

| 提供商 | 获取 Key | 推荐场景 |
|---|---|---|
| Anthropic | https://console.anthropic.com | 最佳英文质量 |
| DeepSeek | https://platform.deepseek.com | 性价比首选 |
| 火山方舟 | https://console.volcengine.com/ark | 国内稳定访问 |
| 智谱 GLM | https://bigmodel.cn | 免费调试 |

```bash
# 4. 启动
uvicorn app.main:app --reload
# 打开 http://localhost:8000
```

---

## 技术架构

```
前端                     后端                     AI 层
─────────────           ─────────────           ──────────────────
HTML / CSS / JS  ──────► FastAPI (Python)  ─────► Claude / DeepSeek
（Vanilla）              SQLAlchemy 2.0           Doubao / GLM
                         SQLite + aiosqlite       （via OpenRouter）
                              │
                         STT: faster-whisper（本地推理）
                         TTS: edge-tts（本地，无 API 费用）
                         记忆: py-fsrs (FSRS 6 算法)
```

---

## 常见问题

**httpx 报 SOCKS 代理错误**

macOS 上 Clash / Surge 等开启"系统代理"后，httpx 默认读取系统代理配置。代码里已加 `trust_env=False`，若仍报错检查是否有多处 httpx 初始化未处理。

**STT 没有转录结果**

首次运行会自动下载 faster-whisper 模型文件（约 150MB），需等待完成。

---

## License

MIT
