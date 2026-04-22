# Deep Interview Spec: Speakeasy 轻量化部署方案

## Metadata
- Interview ID: lightweight-deploy-2026-04
- Rounds: 6
- Final Ambiguity Score: 14%
- Type: brownfield
- Generated: 2026-04-17
- Threshold: 20%
- Status: PASSED

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.9 | 0.35 | 0.315 |
| Constraint Clarity | 0.8 | 0.25 | 0.200 |
| Success Criteria | 0.85 | 0.25 | 0.213 |
| Context Clarity | 0.85 | 0.15 | 0.128 |
| **Total Clarity** | | | **0.856** |
| **Ambiguity** | | | **14%** |

## Goal
对 Speakeasy 项目进行轻量化改造：移除 PyTorch/Silero VAD 重依赖，精简 Docker 镜像（从 ~1.5GB 降到 <300MB），整理依赖清单，并建立 docker-compose + Caddy HTTPS + CI/CD 的完整自托管部署方案。

## Constraints
- 部署目标：自有 VPS/云服务器，Docker 部署
- 必须保留 Docker（环境隔离、可移植性）
- Edge-TTS（云端 TTS）和 Groq STT（云端 STT）保留不变
- SQLite 作为数据库保留不变
- 前端 Vanilla JS 架构保留不变
- VAD 控制权交给用户（手动按钮控制录音），去掉服务端 VAD

## Non-Goals
- 不更换 TTS/STT 提供商
- 不迁移数据库到 PostgreSQL
- 不重构前端为 SPA 框架
- 不更换后端框架（保留 FastAPI）
- 不实现本地 TTS/STT（更重不更轻）

## Acceptance Criteria
- [ ] 移除 `silero_vad`、`torch`、`torchaudio` 等 PyTorch 相关依赖
- [ ] 移除 `app/services/vad_service.py` 和 `app/routers/vad.py`
- [ ] 前端录音改为纯手动按钮控制（保留简单音量检测作为 UI 反馈）
- [ ] `requirements.txt` 审查：移除所有不必要的依赖
- [ ] Docker 镜像大小 < 300MB
- [ ] 提供 `docker-compose.yml`：一条命令启动完整服务
- [ ] 提供 Caddy 配置：自动 HTTPS（Let's Encrypt）
- [ ] 提供 CI/CD 配置：git push 自动构建部署到 VPS
- [ ] 数据持久化：SQLite 数据库和 TTS 缓存通过 Docker volume 挂载
- [ ] `.env.example` 更新，覆盖所有必需的环境变量
- [ ] 所有现有功能（聊天、复习、记忆、练习）正常工作
- [ ] 冷启动时间 < 10 秒

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| 需要服务端 VAD | 前端 VAD 已能检测静音，服务端是额外精确层 | 去掉服务端 VAD，用户手动控制录音 |
| Edge-TTS 需要替换 | Edge-TTS 已经很轻量（纯 Python，调云端接口） | 保留 Edge-TTS，它不是瓶颈 |
| 必须用 Docker | 直接 pip+systemd 更轻 | 用户确认需要 Docker 的隔离和可移植性 |
| 简单部署就够了 | 部署还需要什么？ | 需要自动 HTTPS + CI/CD |

## Technical Context

### 当前架构
- **Backend**: FastAPI + Uvicorn (Python 3.11)
- **Frontend**: Vanilla HTML/JS (4 pages, no build tools)
- **Database**: SQLite + SQLAlchemy async
- **LLM**: Multi-provider (Anthropic/DeepSeek/VolcEngine/Zhipu)
- **STT**: Groq Whisper-large-v3
- **TTS**: Edge-TTS (primary) + OpenAI TTS (fallback)
- **VAD**: Silero VAD (PyTorch) — **TO BE REMOVED**
- **Deployment**: Fly.io (fly.toml) — **TO BE REPLACED**

### 需要修改的文件
- `app/services/vad_service.py` — 删除
- `app/routers/vad.py` — 删除
- `main.py` — 移除 VAD 路由注册
- `requirements.txt` — 移除 torch/silero_vad，审查其余依赖
- `Dockerfile` — 优化基础镜像、多阶段构建
- `static/js/stt-provider.js` — 确认前端 VAD 独立于服务端
- 新增: `docker-compose.yml`
- 新增: `Caddyfile`
- 新增: `.github/workflows/deploy.yml`（或等效 CI/CD）

### 需要保留的依赖
- fastapi, uvicorn, pydantic — Web 框架
- sqlalchemy, aiosqlite — 数据库
- anthropic, openai, groq — LLM/STT 提供商
- edge-tts — TTS
- python-dotenv, python-multipart — 配置和文件上传
- fsrs — 间隔重复算法
- yt-dlp, youtube-transcript-api — 练习功能

### 可移除的依赖
- torch, torchaudio — PyTorch（Silero VAD 依赖，最大瘦身点）
- silero_vad 相关 — VAD 模型
- asyncpg — PostgreSQL 驱动（不使用 PG）

## Ontology (Key Entities)

| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| Docker Image | core domain | base_image, size, layers | 包含 FastAPI Backend |
| FastAPI Backend | core domain | routes, services, models | 运行在 Docker Image 中 |
| SQLite | supporting | db_path, tables | FastAPI 读写，volume 持久化 |
| Edge-TTS | external system | provider, voices, cache | FastAPI 调用 |
| Groq STT | external system | api_key, model | FastAPI 调用 |
| VPS | infrastructure | provider, region, specs | 运行 Docker |
| Caddy | infrastructure | domains, tls, reverse_proxy | VPS 上反向代理 FastAPI |
| CI/CD Pipeline | infrastructure | trigger, build, deploy | git push → 构建 → 部署到 VPS |

## Ontology Convergence

| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 4 | 4 | - | - | N/A |
| 2 | 5 | 1 | 0 | 4 | 80% |
| 3 | 5 | 1 | 0 | 4 | 80% |
| 4 | 6 | 1 | 0 | 5 | 83% |
| 5 | 6 | 0 | 0 | 6 | 100% |
| 6 | 8 | 2 | 0 | 6 | 75% |

## Interview Transcript
<details>
<summary>Full Q&A (6 rounds)</summary>

### Round 1
**Q:** 你说的「更轻量」，最核心想解决的痛点是什么？
**A:** 镜像瘦身为主
**Ambiguity:** 56% (Goal: 0.75, Constraints: 0.2, Criteria: 0.15, Context: 0.6)

### Round 2
**Q:** 你说未来用 Docker 部署——部署在哪里？
**A:** 自己的 VPS/云服务器
**Ambiguity:** 48% (Goal: 0.75, Constraints: 0.5, Criteria: 0.15, Context: 0.6)

### Round 3
**Q:** 如果去掉服务端 Silero VAD，只保留前端 VAD，可以移除 PyTorch 依赖，你能接受吗？
**A:** 去除 VAD，控制器交给用户（手动按钮）
**Ambiguity:** 41% (Goal: 0.9, Constraints: 0.5, Criteria: 0.2, Context: 0.7)

### Round 4 (Contrarian Mode)
**Q:** 除了镜像瘦身，你还希望这次优化达成什么其他结果？
**A:** 镜像瘦身 + 整理依赖 + 简化部署流程
**Ambiguity:** 26% (Goal: 0.9, Constraints: 0.55, Criteria: 0.7, Context: 0.75)

### Round 5 (Contrarian Challenge)
**Q:** 你真的需要 Docker 吗？直接 pip+systemd+nginx 更轻。
**A:** 确实想用 Docker
**Ambiguity:** 20% (Goal: 0.9, Constraints: 0.75, Criteria: 0.7, Context: 0.8)

### Round 6
**Q:** 切换到 VPS + Docker 后，你期望的部署体验是什么？
**A:** 自动 HTTPS + CI/CD 自动部署
**Ambiguity:** 14% (Goal: 0.9, Constraints: 0.8, Criteria: 0.85, Context: 0.85)

</details>
