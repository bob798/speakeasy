# Speakeasy - V1 MVP 开发规格文档

> 本文档是 Claude Code 的执行规格，所有开发严格按照此文档进行。

---

## 零、Claude Code 工作指令（必须首先阅读）

请先完整阅读本文档，阅读完后：
1. 用 3 条以内告诉我你的理解摘要
2. 告诉我你准备先做什么
3. 请完整阅读本文档，然后按「十一、开发顺序」的 Step 1-8 依次执行，
遇到文档未覆盖的情况再问我。完成后告诉我可以验收了。

**执行规则：**
- 每完成文档「十一、开发顺序」中的一个 Step，停下来等我验证，不要连续完成多个步骤
- 如果遇到本文档没有覆盖的情况，先问我，不要自行决策
- 所有 pip install 命令必须在当前激活的 venv 环境中执行，不要使用 sudo
- 验收测试使用 FastAPI 自带的 /docs 页面（http://localhost:8000/docs），不需要写 curl 命令

---

## 一、产品概述

**产品名称**：Speakeasy

**核心价值**：用户用英语和 AI 自由聊天，AI 像真实朋友一样回应，永不评判，
在对话中自然植入更好的表达方式，对话结束后推送「今日一句」。

**目标用户**：30-45 岁在职中国人，有英语口语提升需求，但害怕被评判、
缺乏真实对话场景。

**V1 核心体验**：
1. 用户输入今天想聊的话题
2. 和 AI 用英语自由对话（纯文本）
3. AI 在对话中自然示范更好的表达（不显性纠错）
4. 对话结束，收到「今日一句」总结卡片

---

## 二、项目结构

请按以下结构组织项目文件：

```
speakeasy/
├── main.py                  # FastAPI 入口
├── .env                     # 环境变量（不提交 git）
├── .env.example             # 环境变量模板
├── .gitignore               # Git 忽略文件
├── requirements.txt         # Python 依赖
├── SPEC.md                  # 本文档
│
├── app/
│   ├── __init__.py
│   ├── config.py            # 配置加载
│   ├── models.py            # Pydantic 数据模型
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── chat.py          # /chat 相关路由
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── claude.py        # Claude API 调用封装
│   │
│   └── prompts/
│       ├── __init__.py
│       ├── system.py        # 主系统 Prompt
│       └── summary.py       # 今日一句 Prompt
│
└── tests/
    ├── __init__.py
    └── test_chat.py         # 基础接口测试
```

---

## 三、.gitignore 文件内容

```
.env
__pycache__/
*.pyc
*.pyo
.venv/
venv/
.DS_Store
*.egg-info/
dist/
.pytest_cache/
```

---

## 四、环境变量

**.env.example 文件内容：**

```
ANTHROPIC_API_KEY=your_api_key_here
MAX_TOKENS=1024
MODEL_NAME=claude-sonnet-4-20250514
ALLOWED_ORIGINS=http://localhost:3000
```

---

## 五、依赖包

**requirements.txt 内容：**

```
fastapi==0.115.0
uvicorn==0.30.0
anthropic==0.40.0
python-dotenv==1.0.0
pydantic==2.9.0
```

---

## 六、数据模型

**app/models.py 定义以下模型：**

```python
from pydantic import BaseModel

# 单条消息
class Message(BaseModel):
    role: str          # "user" 或 "assistant"
    content: str       # 消息内容

# 对话请求
class ChatRequest(BaseModel):
    session_id: str           # 会话唯一ID，由调用方生成 UUID
    message: str              # 用户当前输入
    history: list[Message]    # 历史消息列表，由调用方维护和传入

# 对话响应
class ChatResponse(BaseModel):
    reply: str                # AI 回复内容
    session_id: str           # 回传 session_id

# 结束对话请求
class EndSessionRequest(BaseModel):
    session_id: str
    history: list[Message]    # 完整对话历史

# 今日一句响应
class SummaryResponse(BaseModel):
    tip: str                  # 今日一句内容
    session_id: str

# 统一错误响应
class ErrorResponse(BaseModel):
    error: str                # 错误描述
    session_id: str = ""      # 如果有 session_id 则回传
```

**重要说明：V1 服务端完全无状态。**
- history 由调用方（测试脚本或未来前端）负责维护和每次传入
- 服务端不存储任何对话历史
- 不需要实现任何 MemoryService

---

## 七、API 接口规格

### 7.1 健康检查

```
GET /health

Response 200:
{
  "status": "ok"
}
```

---

### 7.2 发送消息

```
POST /chat

Request Body:
{
  "session_id": "uuid-string",
  "message": "Hey, I had a really good day today",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}

Response 200:
{
  "reply": "Oh that's great! What made it so good?",
  "session_id": "uuid-string"
}

Response 422: 参数校验失败（FastAPI 自动处理）

Response 500:
{
  "error": "Claude API 调用失败：具体错误信息",
  "session_id": "uuid-string"
}
```

**实现要求：**
- 将 history 转换为 Claude messages 格式，在末尾加入当前 message
- 系统 Prompt 使用 app/prompts/system.py 中定义的 SYSTEM_PROMPT
- 超时时间设置为 30 秒
- 捕获所有异常，统一返回 ErrorResponse 格式的 500 响应

---

### 7.3 结束对话，生成今日一句

```
POST /chat/summary

Request Body:
{
  "session_id": "uuid-string",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}

Response 200:
{
  "tip": "今天试试用 'That sounds amazing!' 替换 'very good'，听起来更像 native speaker。",
  "session_id": "uuid-string"
}

Response 500:
{
  "error": "今日一句生成失败：具体错误信息",
  "session_id": "uuid-string"
}
```

**实现要求：**
- 将完整 history 格式化为文本后传给 Claude
- 使用 app/prompts/summary.py 中的 SUMMARY_PROMPT
- 今日一句必须是中文
- 长度控制在 50 字以内

---

## 八、核心 Prompt

### 8.1 主系统 Prompt（app/prompts/system.py）

```python
SYSTEM_PROMPT = """
You are Alex, a native English speaker and warm, curious friend of the user.
Your role is to have genuine, engaging conversations in English.

## Your Personality
- Warm, curious, and genuinely interested in the user's life
- Casual and natural, like texting a close friend
- Positive and encouraging, never critical

## Core Rules - NEVER break these

1. NEVER correct the user's grammar or pronunciation explicitly
   - Do NOT say: "You should say..." or "The correct form is..."
   - Do NOT highlight errors in any way

2. Natural Modeling - Plant better expressions organically
   - If user says "Yesterday I go to meeting", you naturally say
     "Oh nice, how did the meeting go? I went to one last week too..."
   - Use the correct form naturally in YOUR response, never point it out
   - Only model ONE correction per 3-4 conversation turns, don't overdo it

3. Keep conversations flowing naturally
   - Ask one genuine follow-up question per response
   - Show real curiosity about their stories and experiences
   - Share brief relatable reactions ("Oh wow", "That's so interesting", etc.)

4. Response length
   - Keep responses concise: 2-4 sentences
   - Match the user's energy level

5. If user writes in Chinese
   - Gently respond in English, but acknowledge you understood
   - Never make them feel embarrassed about switching languages

## Conversation Goal
Make the user feel: "I was just chatting with a friend, but somehow my English
got better." The magic is invisible. The progress is real.
"""
```

---

### 8.2 今日一句 Prompt（app/prompts/summary.py）

```python
SUMMARY_PROMPT = """
你是一位英语学习顾问。请分析以下对话记录，找出用户最值得学习的一个表达改进点。

要求：
1. 只给一条建议，不要多条
2. 必须用中文输出
3. 格式：「今天试试用 [更好的表达] 替换 [用户用的表达]，[一句话说明为什么更自然]」
4. 如果用户表达已经很好，就给一个他用得不错的地方做正向强化
5. 字数控制在 50 字以内
6. 语气轻松友好，不要像老师评分

对话记录如下：
"""
```

---

## 九、核心服务实现要求

### 9.1 app/config.py

```python
# 使用 python-dotenv 加载 .env 文件
# 暴露以下配置项：
# - ANTHROPIC_API_KEY
# - MAX_TOKENS（默认 1024）
# - MODEL_NAME（默认 claude-sonnet-4-20250514）
# - ALLOWED_ORIGINS（默认 http://localhost:3000）
```

### 9.2 app/services/claude.py

```python
# 实现 ClaudeService 类，包含以下两个方法：

def chat(self, message: str, history: list[dict]) -> str:
    """
    调用 Claude API 进行对话
    - 使用 SYSTEM_PROMPT 作为系统提示
    - 将 history 转换为 Claude messages 格式
    - 在 history 末尾加入当前 message
    - 返回 AI 回复的纯文本字符串
    - 超时 30 秒
    - 异常时抛出包含错误信息的 Exception
    """

def generate_summary(self, history: list[dict]) -> str:
    """
    基于完整对话历史生成今日一句
    - 将 history 格式化为 role: content 的纯文本
    - 拼接 SUMMARY_PROMPT + 格式化历史
    - 调用 Claude API
    - 返回今日一句纯文本字符串
    """
```

---

## 十、main.py 入口要求

```python
# main.py 需要包含：
# 1. FastAPI 实例初始化，设置 title="Speakeasy API"
# 2. CORS 中间件配置，允许来自 ALLOWED_ORIGINS 的跨域请求
# 3. 注册路由：GET /health，POST /chat，POST /chat/summary
# 4. 所有路由实现在 app/api/chat.py 中，main.py 只做注册

# 启动命令（只在终端执行，不要写进代码）：
# uvicorn main:app --reload --port 8000
```

---

## 十一、开发顺序（严格按步骤执行，每步完成后等待确认）

```
Step 1: 创建 .gitignore 和 requirements.txt
Step 2: 创建 .env.example 和 app/config.py，验证配置加载正常
Step 3: 定义数据模型 app/models.py
Step 4: 实现 Prompt 文件 app/prompts/system.py 和 app/prompts/summary.py
Step 5: 实现 ClaudeService chat 方法（app/services/claude.py）
Step 6: 实现 chat 路由和 main.py，跑通 /health 和 /chat 接口
Step 7: 实现 generate_summary 方法和 /chat/summary 接口
Step 8: 打开 http://localhost:8000/docs 完成全部验收测试
```

---

十二、自测试（Step 8 执行，人工验收前必须全部通过）
开发完成后，按以下步骤自动测试：
Step 8.1：后台启动服务
bashuvicorn main:app --port 8000 &
sleep 2  # 等待服务启动
Step 8.2：编写并执行测试脚本 tests/self_test.py
测试脚本需覆盖以下 5 个用例，每个用例打印「测试名称 / Pass or Fail / 实际返回内容」：
用例 1：健康检查
  - GET /health
  - 断言：返回 {"status": "ok"}

用例 2：空历史对话
  - POST /chat，history=[]，message="Hi, I had a great day today"
  - 断言：reply 非空，长度大于 10 个字符

用例 3：多轮对话连贯性
  - POST /chat，携带 2 轮历史，发送第 3 条消息
  - 断言：reply 非空，且不包含 "you should say" / "the correct form"

用例 4：今日一句生成
  - POST /chat/summary，传入至少 2 轮对话历史
  - 断言：tip 非空，包含中文字符，长度小于 100 个字符

用例 5：错误参数处理
  - POST /chat，缺少必填字段 message
  - 断言：返回 422 状态码
Step 8.3：输出测试报告
======= 自测试报告 =======
用例 1 健康检查:        ✅ Pass
用例 2 空历史对话:      ✅ Pass
用例 3 多轮对话连贯性:  ✅ Pass
用例 4 今日一句生成:    ✅ Pass
用例 5 错误参数处理:    ✅ Pass
========================
全部通过，可以开始人工验收。
打开浏览器访问：http://localhost:8000/docs
如有失败用例，输出失败原因并自动修复，修复后重新执行自测试直到全部通过。

十三、人工验收标准
测试方式：打开 http://localhost:8000/docs，使用页面内的交互界面测试。
13.1 接口验收

 GET /health 返回 {"status": "ok"}
 POST /chat 传入空 history，返回 AI 自然开场回复
 POST /chat 传入 3 轮历史，AI 回复保持对话连贯性
 POST /chat/summary 传入对话历史，返回中文今日一句
 POST /chat 传入错误参数，返回统一 ErrorResponse 格式

13.2 行为验收（人工判断）

 AI 回复语气自然，像朋友而不是老师
 AI 绝对不显性纠错（无 "you should say" 等表达）
 对话中能观察到自然示范（AI 用更好的表达复述同一话题）
 今日一句是中文，50 字以内，语气友好
 用中文输入时，AI 用英文回应但不让用户尴尬


十四、不在 V1 范围内（禁止提前实现）

❌ 语音输入 / 输出（STT / TTS）
❌ 数据库 / 持久化存储
❌ 用户登录 / 注册
❌ 前端页面
❌ 流式输出（Streaming）
❌ 学习进度追踪
❌ 任何形式的 MemoryService

以上功能全部在 V2 实现，V1 只做：后端 API 跑通核心对话体验。