# Speakeasy

> 你的 AI 陪伴式私教，越聊越懂你。

[English](./README_EN.md)

---

## 这个产品在解决什么

学英语的人不缺资源，缺的是**真正认识你的练习对象**。

背单词、刷题、上课——练完就忘，下次重头。每个 App 对你一无所知：不知道你是做什么的，不记得你上次说过什么，不知道你哪里弱、哪里已经很好。练了三个月，系统对你的了解和第一天一样。

通用 AI（ChatGPT）能聊，但同样的问题：每次对话结束，一切清零。它不积累，不进化，不认识你。

**Speakeasy 的切入点是：一个真正在积累对你的了解的英语私教。**

---

## Speakeasy 是什么

一个 AI 陪伴式私教，叫 Alex。

你们聊你真实生活里的事——今天的会议、遇到的麻烦、周末去了哪里。Alex 持续积累对你的认知：你是做什么的、你哪里容易出错、你上周发生了什么。每次对话，Alex 比上次更懂你——话题更贴合你，引导更精准，强化的点更有针对性。

Alex 有两种方式带你进步：

**隐式（你感知不到，但在发生）**
对话过程中，Alex 自然地在回复里植入你需要强化的表达。你以为在聊天，Alex 知道你在进步。

**显式（对话后，你主动回顾）**
每次对话结束，Alex 生成复盘：今天哪里说得地道，哪里有更自然的说法。你选择深入追问，或继续下一次对话。

不是课程，不是练习题，不是 AI 老师。**是越聊越懂你的私教。**

---

## 和直接用 ChatGPT 练英语有什么区别

| | ChatGPT | Speakeasy（Alex） |
|---|---|---|
| 记得你说过什么？ | 不记得，每次重头 | 记得，会追问上次那件事后来怎样了 |
| 记得你的语法习惯？ | 不记得 | 记得，持续在对话中针对性强化 |
| 知道你是做什么的？ | 不知道 | 知道，话题和词汇贴合你的职业场景 |
| 随时间进化吗？ | 不会，每次一样 | 会，越聊越精准 |
| 怎么带你进步？ | 靠你自己引导 | 隐式引导 + 显式复盘，双路径同步 |

---

## Alex 怎么认识你

```
每次对话之后：
  对话内容
     │
     ├─► grammar_cards   你反复出现的语法习惯
     │   （FSRS 算法调度：何时在对话里针对性强化）
     │
     ├─► user_facts      你的生活在发生什么
     │   LLM 提取 2-3 条："用户本周有重要演示"
     │
     └─► user_profile    你是谁
         职业背景 / 英语水平 / 话题偏好 / 学习目标

下次对话开始时，三层记忆注入 Alex 的上下文：
Alex 知道你的语言习惯、上周发生了什么、你在朝什么方向走
```

这不是技术设计，是"Alex 真正认识你"的实现方式。

---

## 核心示例

```
你说："Yesterday I go to a meeting with my boss..."

Alex 自然回应（隐式引导，对话中无感发生）：
"Oh that sounds tough — how did the meeting go?
 I went to a really long one last week too..."
  ↑ 用了 went，你的弱点，Alex 悄悄示范

对话结束，Alex 生成复盘（显式回顾）：
  ✓ 今天说得地道的表达
  → 可以更自然的地方（不是"你错了"，是"更好的说法是"）

下次对话，Alex 已经更新了对你的认识：
  · 多用过去时，针对你的 go/went 习惯
  · 记住你和老板开会这件事，可能会自然续接
  · 知道你是产品经理，话题往产品和团队方向靠
```

**三个设计原则：**

| 原则 | 是什么 | 不是什么 |
|---|---|---|
| **认识你** | 职业画像 + 语法习惯 + 生活事件，持续积累 | 不只是对话历史 |
| **带你走** | 话题、难度、强化点动态调整，隐式 + 显式双路径 | 不是固定课程表 |
| **陪着你** | 跨 session，没有终点，越用越专属 | 不是一次性工具 |

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
