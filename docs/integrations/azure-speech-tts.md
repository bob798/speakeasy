# Azure Speech Services（Text-to-Speech）对接文档

> 引入版本：V0.11（PR #16 升级 TTS 引擎 edge-tts → Azure TTS · 支持 SSML IPA 纠音）
> 后端实现：`app/services/tts_service.py:_azure_tts`
> 前端入口：Practice 页 ⚙ 设置 sheet · TTS 引擎选项

## 为什么选 Azure

Speakeasy 的 `multi_tts` 多引擎 TTS 体系里 `provider="azure"` 是 **国内 VPS 部署的首选**：

| 引擎 | 国内 VPS 可用性 | 音质 | 免费额度 |
|---|---|---|---|
| **Azure** | ✅ 走香港 endpoint，国内访问稳 | Neural 一流 | F0：50 万字符/月 |
| Google | ❌ 国内 VPS 99% 不通（除非反代） | Neural2 一流 | 100 万字符/月 |
| Edge | ✅（默认） | 还行，免费 | 无限 |
| OpenAI | 视域名而定 | 较好 | 按量收费 |

**独有功能：** SSML + IPA 纠音 — `_azure_tts` 支持传 `phoneme_map={"crisis": "ˈkraɪsɪs"}` 给某个词指定国际音标，TTS 朗读时按你给的音标读。这是 edge / openai 都没有的特性，对发音教学场景特别有用。

**失败时自动降级 edge-tts**（`tts_service.py:160`），不会让前端报 500。

---

## ⚠️ Azure Global vs Azure 中国 —— 千万别注册错

| | Azure Global | Azure 中国（21Vianet 运营） |
|---|---|---|
| 入口 | [portal.azure.com](https://portal.azure.com) | [portal.azure.cn](https://portal.azure.cn) |
| 计费 | USD | RMB |
| 注册要求 | 邮箱 + 信用卡 | 中国企业资质 + ICP 备案 |
| Speech 声音库 | 全套 Neural / Multilingual / Studio | 只有部分中文声音 |
| 注册难度 | ⭐ 一张 visa 几分钟 | ⭐⭐⭐⭐⭐ 个人基本开不了 |
| **Speakeasy 用** | **✅** | ❌ |

**走 Azure Global。** 入口必须是 **`signup.azure.com`** 不是 `.cn`。

---

## 注册 + 拿 API Key

### Step 1 · 注册 Azure Global 账户

1. 打开 [signup.azure.com](https://signup.azure.com/)
2. **国家/地区选「United States」**（账户国家，注册后不可改）
   - 不选「中国」—— 那会自动跳到 Azure 中国
   - 美国通过率最高、$200 试用额度给得最干脆
3. 用 outlook.com 或 gmail 注册
4. 手机验证（国内号可收码）
5. 绑 visa/mastercard 卡（**只扣 $1 验证然后退**，永不自动收费除非主动超免费层）

注册完会拿到：

- **$200 美元试用额度**（12 个月内用完）
- **F0 免费层**（永久免费，包含 Speech 50 万字符/月）

### Step 2 · 创建 Speech Services 资源

1. 进 [portal.azure.com](https://portal.azure.com)
2. 左上「**创建资源**」→ 搜 `Speech` → 选 **Speech Services**
3. 创建参数：

| 字段 | 值 | 备注 |
|---|---|---|
| 订阅 | 默认（免费试用） | |
| 资源组 | 新建 `speakeasy-rg` | 任意名 |
| **区域** | **East Asia** | ⭐ 国内 VPS 用必选香港，延迟 30-50ms |
| 名称 | `speakeasy-speech` | 任意名，全球唯一 |
| **定价层** | **Free F0** | 50 万字符/月免费；超额才升 S0 |

「区域」和注册时的「国家」是**两回事**：
- 国家 = 账单国家（已锁死美国）
- 区域 = 服务部署位置（按延迟选 East Asia）

### Step 3 · 进资源页

⚠️ 创建完别从「资源组」点进去 —— 那是个文件夹，左侧菜单**只有「访问控制 (IAM)」**之类，没你要的东西。

**正确路径：**

- portal 顶栏搜「**所有资源**」（All resources）
- 找类型为 **`语音服务` / `Speech` / `Cognitive Services`** 的条目
- 点资源名（比如 `speakeasy-speech`）进去
- 顶部面包屑应该是：`主页 > 所有资源 > speakeasy-speech`（**而不是 `… > speakeasy-rg`**）

进对的页面后左侧菜单**至少**有：

```
📋 概述
📜 活动日志
🔐 访问控制 (IAM)
🏷️ 标记
🩺 诊断并解决问题
─── 资源管理 ───
🔑 密钥和终结点      ← ⭐ 你要的
🌐 网络
🆔 标识
…
```

如果**只看到「访问控制」+ 几项**，三种可能：

1. **看的是资源组** —— 退一层，点进具体资源
2. **资源还没部署完** —— 顶部铃铛🔔等「部署成功」
3. **创建错资源类型** —— 必须是 `kind: SpeechServices` 的语音服务，不是 Speech Translation / multi-service AI services。在「概述」页验证类型 = `Speech` / `Cognitive Services`，定价层 = `F0 Free`

### Step 4 · 拿 Key + Region

进资源后 → 左侧 **「密钥和终结点」**（Keys and Endpoint）→ 这页有 3 个字段：

| 字段 | 用途 | 拷哪个值 |
|---|---|---|
| **密钥 1 / 密钥 2** | 鉴权 | 复制 **密钥 1** → `AZURE_TTS_KEY`（32 位 hex） |
| **位置/区域** | 服务区域 | 显示 `East Asia` → 转 region code `eastasia` |
| **终结点 (Endpoint)** | Cognitive Services 通用入口 | **⚠️ 不用** |

> ⚠️ 「终结点」一栏显示的 `https://eastasia.api.cognitive.microsoft.com/` 是 Cognitive Services **通用域名**，给 SDK 用的。
>
> **我们代码 `_azure_tts` 不读这个 endpoint** —— TTS 走专属子域 `https://<region>.tts.speech.microsoft.com/cognitiveservices/v1`，由代码根据 region 自己拼。所以你**只需要 KEY + REGION CODE 两个值**。

**Region code 对照**（`位置/区域` 显示名 → `.env` 里写的 code）：

| 显示名 | Region code |
|---|---|
| East Asia | `eastasia` |
| Southeast Asia | `southeastasia` |
| Japan East | `japaneast` |
| Korea Central | `koreacentral` |
| East US | `eastus` |
| West US | `westus` |
| West Europe | `westeurope` |

**code 必须全小写连写**，不要写 `East Asia`、`east-asia` 或 `EastAsia` —— 是最常见的 401 原因。

---

## 配置到 Speakeasy

### 本地开发

`.env`：

```bash
AZURE_TTS_KEY=<KEY 1 32 位 hex>
AZURE_TTS_REGION=eastasia

# 可选：直接把 Azure 作为默认引擎
# TTS_DEFAULT_PROVIDER=azure
```

重启 uvicorn 即可。

### 线上（VPS Docker compose）

`.env.production`：

```bash
AZURE_TTS_KEY=<KEY 1>
AZURE_TTS_REGION=eastasia

# 推荐：国内 VPS 把 Azure 设为默认（Google 走不通）
TTS_DEFAULT_PROVIDER=azure
```

让容器读新 env：

```bash
ssh <vps>
cd <app-dir>
docker compose down && docker compose up -d
# 注意：docker compose restart 不会重新读 .env，必须 down + up
```

验证 env 已注入：

```bash
docker compose exec web env | grep AZURE_TTS
```

---

## 切换 / 默认逻辑

跟 [Google TTS 文档](google-cloud-tts.md#切换默认逻辑) 完全平行：

### A. 单次请求（前端）

Practice 页 → ⚙ → TTS 引擎 → 选 `Azure`
- 不持久化，刷新页面回默认

### B. 全局默认（环境变量）

```bash
TTS_DEFAULT_PROVIDER=azure
```

国内 VPS 推荐这个配置。

### C. 选了 Azure 但听到 edge 声音怎么办

这是 `multi_tts` 的**降级 fallback** —— Azure 调用失败被吃掉用 edge 顶。

```bash
ssh <vps>
docker compose logs --tail 200 web | grep -iE 'azure|tts_service'
# 找：Azure TTS 失败，降级 edge-tts: ...
```

按下面【常见错误】对应修。

---

## 声音映射

`VOICES` dict（`app/services/tts_service.py:17-24`）已为 Edge / Azure 共用 voice 名设计：

| Speakeasy alias | Azure voice name | 性别 |
|---|---|---|
| `jenny` | `en-US-JennyNeural` | 女声 |
| `guy` | `en-US-GuyNeural` | 男声 |
| `sonia` | `en-GB-SoniaNeural` | 英国女声 |
| `xiaoxiao` | `zh-CN-XiaoxiaoNeural` | 中文女声 |
| `yunxi` | `zh-CN-YunxiNeural` | 中文男声 |

要换声音改这张表即可，前端无感。Azure 全部声音见：
[Azure Neural voices 列表](https://learn.microsoft.com/azure/ai-services/speech-service/language-support?tabs=tts)

---

## SSML 与 IPA 纠音（Azure 独有）

`_azure_tts(text, voice, rate, phoneme_map=None)` 接受可选的 IPA 映射。

```python
audio, _ = await _azure_tts(
    "The crisis worries her.",
    voice="en-US-JennyNeural",
    rate="+0%",
    phoneme_map={"crisis": "ˈkraɪsɪs", "worries": "ˈwʌriz"},
)
```

内部生成 SSML：

```xml
<speak version="1.0" xml:lang="en-US">
  <voice name="en-US-JennyNeural">
    <prosody rate="+0%">
      The <phoneme alphabet="ipa" ph="ˈkraɪsɪs">crisis</phoneme>
      <phoneme alphabet="ipa" ph="ˈwʌriz">worries</phoneme> her.
    </prosody>
  </voice>
</speak>
```

应用场景：用户某个词反复读错，系统标出正确 IPA 让 Azure 「示范」一遍。Speakeasy V0.11 已用于发音练习的 IPA 纠音。

详细见 `tests/test_azure_tts.py:test_build_ssml_with_phoneme_map*`。

---

## 速度格式

Azure 直接用 Edge 风格的字符串：`-40% / -20% / +0% / +20%`，**不需要转换**。

`_azure_tts` 把 rate 原样塞进 SSML `<prosody rate="...">`：

```python
rate="+20%"  →  <prosody rate="+20%">...</prosody>
```

跟 Google TTS 不同（Google 用 0.6 ~ 1.2 浮点 speakingRate）。

---

## 测试与诊断

### 单元测试

```bash
source venv/bin/activate
pytest tests/test_azure_tts.py -v
```

`tests/test_azure_tts.py`（V0.11 引入，20 个用例）：

- `_build_ssml`：含 / 不含 phoneme_map / 大小写不敏感 / 只换匹配词
- `_azure_tts`：无 KEY 抛错 / HTTP 200 / HTTP 4XX 抛错 / 空 body 抛错
- `multi_tts`：provider=azure dispatch / 失败降级 edge / 缓存命中

### 命令行手验

```bash
# 1. voices 端点（GET、最便宜）
curl -s "https://eastasia.tts.speech.microsoft.com/cognitiveservices/voices/list" \
  -H "Ocp-Apim-Subscription-Key: $AZURE_TTS_KEY" | jq '.[0:3]'
# 应返回 JSON 数组（前 3 个声音）

# 2. synthesize 端点（POST + SSML）
SSML='<speak version="1.0" xml:lang="en-US"><voice name="en-US-JennyNeural">Hello from Speakeasy.</voice></speak>'
curl -X POST "https://eastasia.tts.speech.microsoft.com/cognitiveservices/v1" \
  -H "Ocp-Apim-Subscription-Key: $AZURE_TTS_KEY" \
  -H "Content-Type: application/ssml+xml" \
  -H "X-Microsoft-OutputFormat: audio-24khz-96kbitrate-mono-mp3" \
  -d "$SSML" \
  --output /tmp/azure.mp3 && file /tmp/azure.mp3
# 期望：MPEG ADTS, layer III
# afplay /tmp/azure.mp3 听效果
```

### 应用层端到端

进 `/practice` → ⚙ → 引擎选 `Azure` → 🔊 发音整句 → 听 JennyNeural 声音。

DevTools Network 看 `/practice/tts` 返回 200 + audio/mpeg。

---

## 常见错误

### 401 `Access denied due to invalid subscription key or wrong API region`

**70% 的踩坑都是这个。** 五种细分原因，按命中率排序：

| 原因 | 表现 | 修法 |
|---|---|---|
| Region code 写成显示名 | `.env` 里 `AZURE_TTS_REGION=East Asia` | 改 `eastasia` 全小写连写 |
| Region 和 key 不配对 | 你创建资源时选了 East Asia，env 写 eastus | portal 资源页「概述」核对真实区域 |
| key 复制时多了空格 | key 前后混进空格或换行 | `.env` 里 key 值无空格，引号也不要 |
| 用了「终结点」当 key | 把 `https://...api.cognitive...` 塞进 KEY 字段 | KEY 是 32 位 hex，不是 URL |
| 资源是 Azure 中国的 | portal 是 `.cn` 子域注册的 | 必须 Azure Global（signup.azure.com） |

### 403 `Quota Exceeded`

F0 免费层 50 万字符/月用完了。

- 月初自动重置
- 急用：portal 把定价层升 S0（按量付费，每月前 50 万字符仍免费）
- 或临时切回 edge：`TTS_DEFAULT_PROVIDER=edge`

### 400 `Bad Request - Invalid SSML`

SSML 格式错。常见：
- voice 名拼错（例 `en-US-jennyNeural` 大小写错）
- phoneme alphabet 错（必须是 `ipa`）
- 文本含未转义的 `<`, `>`, `&` — `_build_ssml` 会自动 `xml.sax.saxutils.escape`，应该不会触发

### 429 `Too Many Requests`

并发太高（F0 ≤ 20 并发请求；S0 ≤ 200）。

- 应用层加 retry/throttle
- 或升 S0

### 网络超时（国内 VPS 罕见）

`East Asia` 部署在香港，从国内 VPS 通常 30-50ms。如果超时：

```bash
# VPS 上测连通性
curl -v --max-time 5 https://eastasia.tts.speech.microsoft.com 2>&1 | head -20
```

如果 connect 都超时 → 该 VPS 出口被防火墙限制（少见但可能）。换 VPS 或换 region (Japan East / Korea Central) 试试。

---

## 设计决策记录

- **REST + subscription key 而非 SDK**
  - Azure 有 `azure-cognitiveservices-speech` Python SDK，但要额外装 native binary（mac/linux 编译）
  - REST + `Ocp-Apim-Subscription-Key` 头一行搞定
  - SSML 自己构（带 `xml.sax.saxutils.escape`，防注入）

- **SSML + IPA 纠音作为可选参数**
  - 默认调用不传 `phoneme_map`，跟 edge / openai 调用形态一致
  - 教学场景需要 IPA 时按需传，向下兼容

- **降级到 edge 而非抛错**
  - 同 Google：fallback 让前端永远不会 500
  - `WARNING` log 留痕方便排查

- **region 选 East Asia 默认**
  - 国内 VPS 用户为主
  - 海外用户改 `AZURE_TTS_REGION=eastus` 即可，无需改代码

---

## 跟 Google TTS 对比一览

| 对比维度 | Azure | Google |
|---|---|---|
| **国内 VPS 可用** | ✅ East Asia | ❌ 不通 |
| **免费额度** | 50 万字符/月 | 100 万字符/月 |
| **超额定价** | $16/百万（Neural） | $16/百万（Neural2） |
| **音质** | Neural 一流 | Neural2 一流，伯仲 |
| **IPA 纠音** | ✅ SSML phoneme | ❌（SSML 支持但用法不同） |
| **认证** | subscription key | API key |
| **速度格式** | `+20%` 字符串 | `1.2` 浮点 |
| **配置复杂度** | 需 key + region | 仅 key |
| **国内注册难度** | 中（要 visa） | 中（要 visa + 科学上网） |
| **Speakeasy 推荐** | **生产首选** | 海外部署备选 |
