# Speakeasy 🌿

> 一个无评判的 AI 英语口语练习伙伴，让你在不知不觉中变得更流利。

[English](./README_EN.md)

---

## 为什么做这个

市面上的英语学习 App 有两个核心问题：

1. **内容脱节** — 练的都是教材场景，和真实生活严重脱节
2. **评判压力** — 发音评分、语法纠错，让人开口前就紧张

**Speakeasy 的思路不同**：AI 扮演一个英语母语朋友 Alex，和你聊你真实生活里的事，永远不显性纠错，而是在对话中自然示范更好的表达方式。

---

## 核心机制

```
用户说："Yesterday I go to a meeting..."
                ↓
Alex 不纠错，自然回应：
"Oh nice! How did the meeting go? I went to one last week too..."
                ↓
对话结束，推送今日一句：
"试试用 'went' 替换 'go'，过去式让你听起来更自然"
```

**三个设计原则：**

| 原则 | 说明 |
|---|---|
| 🚫 零评判 | 没有评分，没有红色标注，没有"你应该说..." |
| 🌱 自然习得 | AI 在回复中植入正确表达，用户不知不觉吸收 |
| ✨ 一句收获 | 每次对话结束只给一条建议，轻松，不构成压力 |

---

## 技术架构

```
前端              后端              AI 层
──────────        ──────────        ──────────────────────
HTML/CSS/JS  ───► FastAPI      ───► Claude Sonnet / Haiku
                  (Python)          DeepSeek V3
                                    火山方舟豆包
                                    智谱 GLM-4-Flash
```

**核心技术选型：**
- **FastAPI** — 异步高性能，自动生成 API 文档
- **多模型兼容** — 一行配置切换四家模型提供商
- **服务端无状态** — 对话历史由前端维护，架构简单易扩展
- **Prompt Engineering** — 核心差异化在 System Prompt 设计

---

## 项目结构

```
english-buddy/
├── main.py                  # FastAPI 入口
├── index.html               # 前端聊天界面
├── requirements.txt
├── .env.example             # 环境变量模板
│
├── app/
│   ├── api/
│   │   └── chat.py          # 路由层
│   ├── services/
│   │   └── model_client.py  # 多模型客户端
│   └── prompts/
│       ├── system.py        # Alex 人设 Prompt
│       └── summary.py       # 今日一句 Prompt
```

---

## 快速启动

### 1. 克隆项目

```bash
git clone https://github.com/your-username/english-buddy.git
cd english-buddy
```

### 2. 安装依赖

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，选择一个模型提供商填入 Key：

```bash
# 四选一
MODEL_PROVIDER=anthropic        # or: deepseek / volcengine / zhipu
ANTHROPIC_API_KEY=your_key_here
```

| 提供商 | 获取 Key | 推荐场景 |
|---|---|---|
| Anthropic | https://console.anthropic.com | 最佳英文质量 |
| DeepSeek | https://platform.deepseek.com | 性价比首选 |
| 火山方舟 | https://console.volcengine.com/ark | 国内稳定 |
| 智谱 GLM | https://bigmodel.cn | 免费调试 |

### 4. 启动服务

```bash
# 终端 1 — 后端
uvicorn main:app --reload --port 8000

# 终端 2 — 前端
python3 -m http.server 3000
```

打开浏览器访问 **http://localhost:3000/index.html**

---

## 模型价格参考

| 模型 | 输入 | 输出 | 推荐阶段 |
|---|---|---|---|
| GLM-4-Flash | 免费 | 免费 | 调试 |
| DeepSeek V3 | ¥2/百万 | ¥8/百万 | 开发验收 |
| Claude Haiku 4.5 | $1/百万 | $5/百万 | 上线 |
| Claude Sonnet 4.6 | $3/百万 | $15/百万 | 高质量场景 |

---

## API 接口

启动后访问 **http://localhost:8000/docs** 查看完整交互式文档。

| 接口 | 说明 |
|---|---|
| `GET /health` | 服务健康检查 |
| `POST /chat` | 发送消息，获取 AI 回复 |
| `POST /chat/summary` | 结束对话，生成今日一句 |
| `GET /debug/status` | 查看当前模型配置 |

---

## 产品路线图

- [x] V1 — 文本对话 + 今日一句
- [ ] V2 — 语音输入输出（Whisper + TTS）
- [ ] V2 — 跨 session 记忆（记住用户习惯性错误）
- [ ] V3 — 场景解锁（职场、旅行、面试模式）
- [ ] V3 — 进步可视化（表达变化轨迹）

---

## 产品洞察

这个项目的核心不是技术，而是**对用户心理的洞察**：

> 大多数中国成年人英语水平足够，但一开口就卡壳——不是不会，是**怕**。
> 现有产品都在优化"学得更快"，没有人认真解决"敢开口"这个问题。

Speakeasy 的差异化不在于功能，而在于**消除这种心理障碍**。

这也是我做这个产品的起点——我自己就是这个用户。


---

## License

MIT
