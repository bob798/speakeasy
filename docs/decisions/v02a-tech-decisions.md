# Speakeasy V0.2a 技术决策记录

> **用途：存档决策背景，供回顾和升级参考。不进入 Claude Code 执行流程。**

---

## 一、STT 方案选型对比

| 方案 | 费用 | 部署成本 | 准确率 | 延迟 | 中文 | 主要风险 |
|------|------|----------|--------|------|------|----------|
| **Groq Whisper** ✅ V0.2a | 免费 7200秒/天 | 零（API Key） | ★★★★★ | ~300ms | ✅ 优秀 | 免费额度上限 |
| WebSpeech API | 完全免费 | 零 | ★★★☆☆ | 实时 | ✅ 一般 | 仅 Chrome/Edge；非 HTTPS 不可用 |
| OpenAI Whisper API | $0.006/分钟 | 零 | ★★★★★ | <1s | ✅ 优秀 | 需绑卡 |
| faster-whisper（自建） | 免费 | GPU 服务器 ¥500+/月 | ★★★★★ | <1s | ✅ 优秀 | 运维成本 |
| FunASR（阿里） | 免费 | GPU 服务器 | ★★★★☆ | <1s | ✅ 最佳 | 运维成本；中文专项 |
| Vosk | 免费 | CPU 可跑 | ★★★☆☆ | 实时 | ✅ 一般 | 准确率低；不适合口语练习 |
| whisper.cpp | 免费 | 本地 CPU | ★★★★☆ | 3-8s | ✅ 好 | 延迟过高 |

**决策理由：** Groq 免费额度 7200秒/天，按口语练习场景（平均每句 8 秒，每用户每天 160 秒）可支撑约 45 用户/天，早期完全够用。速度比 OpenAI 官方快 10x+，无需绑卡。WebSpeech 降为兼容兜底，不作主路径。

---

## 二、TTS 方案选型对比

| 方案 | 费用 | 部署成本 | 音质 | 延迟 | 声音克隆 | 主要风险 |
|------|------|----------|------|------|----------|----------|
| **edge-tts** ✅ V0.2a | 完全免费 | pip install | ★★★★☆ | <1s | ❌ | 依赖微软非公开 API |
| WebSpeech TTS | 完全免费 | 零 | ★★★☆☆ | 实时 | ❌ | 声音机械感强 |
| OpenAI TTS | $0.015/千字 | 零 | ★★★★★ | <1s | ❌ | 需绑卡 |
| CosyVoice（阿里） | 免费 | GPU 服务器 | ★★★★★ | 2-5x实时 | ✅ 3秒克隆 | 高运维成本 |
| XTTS-v2 | 免费 | 4GB+ GPU | ★★★★☆ | 1-2x实时 | ✅ | 运维成本 |
| piper | 免费 | CPU 可跑 | ★★★☆☆ | 实时 | ❌ | 音质偏机械 |

**决策理由：** edge-tts 调用与付费版 Azure TTS 同源的微软神经语音，`en-US-JennyNeural` 自然度显著优于浏览器内置 WebSpeech，零成本零部署。风险是依赖非公开接口，但项目自 2021 年持续稳定，社区活跃，V0.3 前不会有问题。

---

## 三、完整升级路径

```
V0.2a   Groq Whisper（免费）+ edge-tts（免费）
          ↓  当 DAU 超过 50 或 Groq 额度不足
V0.3    OpenAI Whisper API + OpenAI TTS   ← 按量付费，稳定可靠
          ↓  当需要声音定制或成本优化
Scale   自建 faster-whisper + CosyVoice  ← 完全可控，DAU>500 合算
```

**工厂函数切换点：** 前端 `createSTTProvider()` 和 `createTTSProvider()` 各一行代码。后端 `stt_service.py` 和 `tts_service.py` 替换实现，接口签名不变。

---

## 四、部署方向判断

**结论：V0.2a 不需要 Nginx。**

Speakeasy 的部署路径更可能是：

| 阶段 | 部署方式 | 是否需要 Nginx |
|------|----------|----------------|
| 本地开发 | `uvicorn main:app --reload` | ❌ |
| 早期上线 | VPS + docker-compose + Caddy（当前方案） | ❌（Caddy 自动 HTTPS + 反代） |
| 规模化 | 容器化 → 云平台 LB | ❌（云 LB 原生支持 SSE） |
| 特殊场景 | 自管服务器 | ✅ 届时配置 |

保留 `X-Accel-Buffering: no` 响应头：Nginx 场景需要（防止流式被缓冲），非 Nginx 场景无害。

---

## 五、可行性验证记录

### 5.1 端到端延迟估算
```
用户录音 10 秒
  → MediaRecorder 生成 blob：<10ms
  → 上传到 /stt：局域网 <50ms，公网 <300ms
  → Groq 转录：~300-500ms
  → 文字填入 + 用户确认/自动发送
  → /chat/stream 第一个 delta：<500ms（Anthropic API）
  → 流式输出完成：1-4s（视回复长度）
  → /tts 生成音频：~500ms
  → 音频开始播放

总感知延迟（录音结束到听到回复）：2-6 秒
评估：可接受，口语练习场景用户预期延迟高于纯文字场景
```

### 5.2 Groq 免费额度压力测试
```
免费额度：7,200 秒/天
单次录音：平均 8 秒
每用户每天（30分钟练习）：约 160 秒

可承载用户数：7200 / 160 ≈ 45 用户/天

超额处理：Groq 返回 429 → 后端返回 fallback 信号 → 前端降级 WebSpeech
结论：早期产品完全够用，不会崩溃
```

### 5.3 音频格式兼容性矩阵
```
浏览器           MediaRecorder 默认格式   Groq 是否接受
Chrome/Edge      audio/webm;codecs=opus   ✅
Firefox          audio/ogg;codecs=opus    ✅
Safari           audio/mp4               ✅
旧 Safari        不支持 MediaRecorder     → 降级 WebSpeech 或提示

解决方案：_getMime() 运行时格式协商，不硬编码 webm
```

### 5.4 SSE 流式 + DB 写入竞态
```
问题：流式输出时 delta 逐块到达，何时写入 DB？

决策：stream 结束（done 事件）时一次性写入完整内容
- 优点：逻辑简单，无竞态，原子写入
- 缺点：中途断连丢失该条消息
- 评估：口语练习场景断连概率低，丢单条消息可接受
  用户重发即可，V0.3 再考虑断点续传
```

### 5.5 Session 生命周期
```
user_id：localStorage，永久持久
session_id：sessionStorage，刷新重置（= 新对话）

ended_at 更新策略：懒更新
- 不主动轮询
- 每次 GET /history 时，对超过 2 小时无消息的活跃 session 补齐 ended_at
- 优点：简化后端逻辑，最终一致即可
```

---

## 六、原方案发现的缺陷清单

| # | 缺陷 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | 静态文件挂载未定义，FastAPI 不自动托管 static/ | 🔴 高 | main.py 加 StaticFiles + 根路由返回 index.html |
| 2 | `/chat` 新增必填字段破坏旧客户端（422 报错） | 🔴 高 | user_id/session_id 改为 Optional |
| 3 | JS 文件加载顺序未定义，Claude Code 自行决策 | 🔴 高 | index.html 明确写出 5 个 script 标签及顺序 |
| 4 | STT 音频格式硬编码 webm，Firefox/Safari 不兼容 | 🟡 中 | _getMime() 运行时协商，覆盖 webm/mp4/ogg |
| 5 | /history 全量返回，用户多时慢 | 🟡 中 | 加 ?limit=20&offset=0 分页，响应含 total |
| 6 | CORS 未配置，开发环境跨端口请求全失败 | 🟡 中 | main.py 加 CORSMiddleware（allow_origins=["*"]） |

---

## 七、扩展性设计记录

### 工厂模式扩展点（前端）
```javascript
// 当前 V0.2a
function createSTTProvider() { return new ServerSTTProvider(); }
function createTTSProvider() { return new ServerTTSProvider(); }

// V0.3 只改这两行，调用方零改动
```

### 服务层扩展点（后端）
```
stt_service.py  → 替换 Groq 为 OpenAI/自建，接口签名 transcribe_audio(bytes, filename) 不变
tts_service.py  → 替换 edge_tts 为 CosyVoice HTTP 调用，接口签名 text_to_speech(text, voice_key) 不变
```

### 数据库切换
```
开发：DATABASE_URL=（空，自动用 SQLite）
生产：DATABASE_URL=postgresql+asyncpg://user:pass@host/speakeasy
代码零改动，仅改环境变量
```

### V0.2b / V0.3 准入条件
```
V0.2b（对话复盘/FSRS）：
  - DB 新增 review_cards 表
  - /chat/summary 接口升级
  - 不影响现有表结构

V0.3（Plugin Registry / Level 评估）：
  - 引入 plugin_registry.py
  - 工厂函数升级为 Registry 查找
  - System Prompt 动态注入机制
```

---

## 八、经济性分析

| 阶段 | 月费用估算 | 说明 |
|------|-----------|------|
| V0.2a 早期（<50 用户/天） | ¥0 | Groq 免费 + edge-tts 免费 |
| V0.3（付费 API） | ~¥100-500/月 | 视用量，OpenAI API 按量计费 |
| Scale（自建推理） | ¥1500-3000/月 | GPU 服务器，DAU>500 才合算 |

**结论：** 从零成本起步，规模驱动升级，每次升级都有对应的商业逻辑支撑。

---

*记录时间：2025-03 | 对应执行文档：speakeasy_v02a_spec.md*