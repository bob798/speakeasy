# Google Cloud Text-to-Speech 对接文档

> 引入版本：V0.12 hotfix（PR #28）
> 后端实现：`app/services/tts_service.py:_google_tts`
> 前端入口：Practice 页 ⚙ 设置 sheet · TTS 引擎选项

## 概览

Speakeasy 的 `multi_tts` 多引擎 TTS 体系新增 `provider="google"` 分支：

```text
multi_tts(text, provider, voice, speed, phoneme_map)
   │
   ├─ azure   → _azure_tts (SSML + IPA 纠音支持)
   ├─ edge    → _edge_tts (默认，零配置)
   ├─ google  → _google_tts (本对接)
   └─ openai  → _openai_tts
```

**失败时自动降级 edge-tts**（`tts_service.py:160-167`），不会让前端报 500。

**免费额度：**

| Voice tier | 月免费额度 | 超出后定价 |
|---|---|---|
| Standard | 400 万字符 | $4 / 百万 |
| WaveNet / Neural2 | 100 万字符 | $16 / 百万 |
| Studio / Chirp HD（新） | 100 万字符 | $160 / 百万（注意） |

我们的 `_GOOGLE_VOICE_MAP` 默认走 Neural2 系，音质明显优于 Edge / Azure F0，仍在免费额度内。

---

## 注册 + 拿 API Key

### Step 1 · 创建 GCP 项目

1. 浏览器开 [console.cloud.google.com](https://console.cloud.google.com)（国内通常要科学上网）
2. 顶栏「**选择项目**」→「**新建项目**」
3. 项目名随意，记下 **项目 ID**（后续报错信息里会出现）

### Step 2 · 启用 Text-to-Speech API

[直达启用页](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)，确认右上角是 **「已启用」**。

新项目默认所有 API 都未启用，必须手动开。

### Step 3 · 绑定 Billing（即使只用免费额度也必须）

[Billing 页](https://console.cloud.google.com/billing)

- 没绑卡 → 调 synthesize 时 403 `BILLING_DISABLED`
- 卡可以是 visa / mastercard，可以是新用户的 $300 免费试用券

### Step 4 · 创建 API key

[凭据页](https://console.cloud.google.com/apis/credentials)

1. 「**创建凭据** → **API 密钥**」
2. 复制生成的 39 位字符串 `AIzaSy...`
3. **不要直接关弹窗** → 点「编辑 API 密钥」做限制（下一节）

### Step 5 · 限制 API Key（重要 · 安全 + 避坑）

API key 没限制等于泄漏即灾难。**建议**：

**「应用限制」**：

- 开发期：选「**无**」
- 生产期：选「**IP 地址**」+ 把 VPS 出口 IP 加进去
  - 查 VPS 出口 IP：`ssh <vps>; curl ifconfig.me`

**「API 限制」**：

- 必须选「**限制密钥**」
- 下拉列表勾选 **`Cloud Text-to-Speech API`**
- 别选「不限制」 —— 不限制 = key 泄漏后能滥用所有 Google API

**保存按钮在页面底部**，别忘点。改后**等 2-5 分钟**才生效（边缘节点缓存）。

---

## 配置到 Speakeasy

### 本地开发

`.env`：

```bash
GOOGLE_TTS_API_KEY=AIzaSy....

# 可选：直接把 Google 作为默认引擎
# TTS_DEFAULT_PROVIDER=google
```

重启 uvicorn 即可。

### 线上（VPS Docker compose）

`.env.production`：

```bash
GOOGLE_TTS_API_KEY=AIzaSy....

# 可选：让 multi_tts(provider=None) 默认走 Google
# TTS_DEFAULT_PROVIDER=google
```

让容器读新 env：

```bash
ssh <vps>
cd <app-dir>
docker compose down && docker compose up -d
# 不能只 restart —— restart 不会重新读 .env
```

验证 env 真的注入：

```bash
docker compose exec web env | grep GOOGLE_TTS_API_KEY
```

---

## 切换/默认逻辑

Speakeasy 有两层「provider 选择」：

### A. 单次请求：用户在前端选

Practice 页 → **⚙ 设置 sheet** → **TTS 引擎** → 选 `Google`

- 前端 store `practice.provider = 'google'`
- 调 `/practice/tts` 时 body 带 `"provider": "google"`
- 这个选择**不持久化**（刷新页面回默认）

后端 `multi_tts` 拿到 `provider="google"` → 调 `_google_tts` → 失败时**静默降级 edge**（在 server log 留一行 `WARNING Google TTS 失败，降级 edge-tts: ...`）

### B. 全局默认：用户没指定时走哪

`multi_tts` 在 provider 参数为 None 时读 `settings.TTS_DEFAULT_PROVIDER`，默认 `edge`。

改环境变量：

```bash
TTS_DEFAULT_PROVIDER=google   # 默认 → google
```

**典型场景**：

| 场景 | 配置 |
|---|---|
| 国内服务器 + 想优先用 Edge（不需要科学上网） | `TTS_DEFAULT_PROVIDER=edge`（默认就是） |
| 海外服务器 + 想优先 Google（Neural2 音质） | `TTS_DEFAULT_PROVIDER=google` |
| 默认 edge，让用户自己点 ⚙ 切 Google 试听 | 不配 `TTS_DEFAULT_PROVIDER` |

### C. 我手机端选了 Google 但听到的还是 Edge 声音怎么办？

**这是降级 fallback 触发了** —— Google 调用失败被静默吃掉，后端用 edge 顶上。要恢复用 Google：

1. 找原因：`docker compose logs --tail 200 web | grep -i google`，看降级时的具体错误
2. 按下面【常见错误】排查并修
3. 修好后，**前端不需要做任何操作**：你的 store 还是 `provider="google"`，下次 🔊 自动走 Google
4. 或者刷新页面后重新进 ⚙ 重选 Google

---

## 声音映射

我们用 Edge/Azure 风格的简称作为统一接口，内部映射到 Google 的具体声音：

| Speakeasy alias | Edge/Azure name | Google name | 性别 |
|---|---|---|---|
| `jenny` | `en-US-JennyNeural` | `en-US-Neural2-F` | 女声 |
| `guy` | `en-US-GuyNeural` | `en-US-Neural2-D` | 男声 |
| `sonia` | `en-GB-SoniaNeural` | `en-GB-Neural2-A` | 英国女声 |
| `xiaoxiao` | `zh-CN-XiaoxiaoNeural` | `cmn-CN-Wavenet-A` | 中文女声 |
| `yunxi` | `zh-CN-YunxiNeural` | `cmn-CN-Wavenet-C` | 中文男声 |

映射表在 `app/services/tts_service.py:_GOOGLE_VOICE_MAP`。要换声音改这张表即可，前端无感。

**全部 Google 声音列表：** 调一次 `voices` 端点看：

```bash
KEY="<你的 GOOGLE_TTS_API_KEY>"
curl -s "https://texttospeech.googleapis.com/v1/voices?key=$KEY&languageCode=en-US" \
  | jq '.voices[] | {name, ssmlGender}'
```

---

## 速度转换

前端用 Edge 风格的字符串：`-40% / -20% / +0% / +20%`
Google 用浮点 `speakingRate`（1.0 = 正常，0.25-4.0）

转换函数 `_parse_speed_to_rate`：

```python
"-40%" → 0.6
"-20%" → 0.8
"+0%"  → 1.0
"+20%" → 1.2
```

可注入异常输入（None / 空字符串 / "abc"）默认 1.0，不抛错。

---

## 测试与诊断

### 本地完整诊断脚本

`scripts/test_google_tts_local.py` 分三层验证：

```bash
source venv/bin/activate
python scripts/test_google_tts_local.py
```

输出按顺序：

1. **Step 1：直打 Google REST API**（绕过项目所有代码）
2. **Step 2：经 `_google_tts` 包装层**
3. **Step 3：经 `multi_tts` 统一入口（含缓存）**

哪步挂在哪步定位根因。三步全过 → 写到 `/tmp/google_tts_*.mp3`，`afplay` 听效果。

### 线上验证

```bash
# 1. 进 /practice → ⚙ → 引擎选 Google → 🔊 发音整句
# 2. DevTools Network 看 /practice/tts 是否 200 + audio/mpeg
# 3. 检查 server log
ssh <vps>
docker compose logs --tail 200 web | grep -iE 'google|tts_service'
# 正常情况无输出（成功无日志）
# 失败会看到：Google TTS 失败，降级 edge-tts: HTTP 4XX ...
```

### 单元测试

`tests/test_google_tts.py`，16 个用例：

```bash
source venv/bin/activate
pytest tests/test_google_tts.py -v
```

- `_parse_speed_to_rate` 10 参数化用例（含异常输入与上下界 clamp）
- `_google_tts` 4 个：missing-key / 200-success / HTTP-error / empty-audio
- `multi_tts` 2 个：正常 dispatch / 失败降级 edge

---

## 常见错误

### 403 `API_KEY_SERVICE_BLOCKED`

> Requests to this API texttospeech.googleapis.com method ... are blocked.

**原因**：API 密钥的「API 限制」白名单里**没勾 Text-to-Speech API**。

**修法**：凭据页编辑 key → API 限制 → 勾「Cloud Text-to-Speech API」→ 保存 → 等 2-5 分钟（Google 端边缘节点缓存，前 1-2 分钟可能仍 403）。

### 403 `BILLING_DISABLED`

**原因**：项目没绑结算账号。

**修法**：[Billing 页](https://console.cloud.google.com/billing) → 关联结算账号（即使免费额度也必须绑卡）。

### 403 `IP_ADDRESS_NOT_ALLOWED`

**原因**：「应用限制」勾了「IP 地址」但 VPS 出口 IP 不在白名单。

**修法**：临时切「无」验证；通了再加 VPS 的 `curl ifconfig.me` 出来的 IP。

### 400 `INVALID_ARGUMENT` (voice not available)

**原因**：voice name 不对（GCP 项目区域不支持 / 该 voice 已弃用）。

**修法**：先用 voices 端点列出可用 voices，再改 `_GOOGLE_VOICE_MAP`。

### 429 `RESOURCE_EXHAUSTED`

**原因**：当月免费额度用完。

**修法**：升 paid tier，或当月切回 edge / azure。

### `httpx.ConnectError` / 网络超时

**原因**：服务器无法访问 `texttospeech.googleapis.com`。

**国内 VPS 大概率走不通 Google API**，需要：
- 国际 BGP 线路
- 或前置反代（不推荐，违反 Google ToS）
- 或换 Azure（境内更稳）

---

## 设计决策记录

- **REST + API key 而非 SDK + service-account JSON**
  - 优点：无新依赖；不挂载 secret 文件；env 注入更标准
  - 缺点：API key 限制不如 service account 精细；不能用 OAuth 角色
  - 权衡：服务端单点访问，API key + IP 限制已够安全

- **降级到 edge 而非抛错**
  - 用户不会因为 Google 临时挂掉看到 500
  - 但 `WARNING` log 会留痕方便排查
  - 见 `multi_tts` 中 try/except 块

- **不上 SSML / 不接 IPA 纠音**
  - `_azure_tts` 通过 SSML 支持逐词 IPA 纠音（V0.11 引入），Google 也支持但用法不同
  - 本次先做最小可用，等 IPA 纠音的需求迁到 Google 时再补
