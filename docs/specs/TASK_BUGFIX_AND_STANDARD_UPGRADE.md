# Claude Code 综合任务清单 — V0.3.1 Bug 修复 + 规范升级

> 任务类型：Bug 修复 + 文档规范升级
> 执行顺序：按模块顺序，每个模块完成后打印确认，再进入下一个
> 前置条件：venv 已激活，处于项目根目录

---

## 模块一：BUG_LOG.md 初始化 + 登记 Bug

### 1.1 检查 BUG_LOG.md 是否有标准格式，若无则初始化

将 BUG_LOG.md 替换为以下内容（保留已有 Bug 记录，补充格式头）：

```markdown
# BUG_LOG.md — Speakeasy Bug 记录

## 格式说明

| 字段 | 说明 |
|---|---|
| BUG-XXX | 编号，三位递增 |
| 发现版本 | 发现时的版本号 |
| 状态 | 🔴 待修复 / 🟡 修复中 / ✅ 已修复 |
| 根因 | 实现错误 / 场景缺失 / 需求变更 |

---
```

### 1.2 新增 BUG-001

```markdown
## BUG-001

- **状态**：🟡 修复中
- **发现版本**：V0.3.1（规划阶段，Step 6 未执行）
- **描述**：Hands free 模式下，Alex TTS 回复播放完毕后，VAD 未自动恢复监听，用户需要刷新页面才能继续对话
- **根因**：场景缺失——SPEC 未定义 TTS 播放结束后的状态转换，缺少对话循环闭环逻辑
- **影响 Step**：Step 6（未开始，当前版本内修复）
- **修复方案**：
  1. TTS 播放完毕回调中自动重启 VAD 监听
  2. TTS 播放期间暂停 VAD，避免 Alex 声音触发自身录音
- **新增 Scenario**：
  - Alex 回复结束后自动恢复监听
  - Alex 说话时暂停 VAD 避免误触
- **修复版本**：V0.3.1 Step 6
```

### 1.3 新增 BUG-002

```markdown
## BUG-002

- **状态**：🟡 修复中
- **发现版本**：V0.3.1（规划阶段，Step 6 未执行）
- **描述**：用户重新进入页面后，若 activation 设置为 hands_free，VAD 自动启动监听，行为不合理——用户未主动发起对话即被监听
- **根因**：场景缺失——SPEC 混淆了"用户偏好持久化"与"会话状态激活"，未定义页面重新进入时的初始状态
- **影响 Step**：Step 5（UI 初始化逻辑）、Step 6（VAD 启动时机）
- **修复方案**：
  1. 页面加载时只渲染 activation 偏好（Voice Settings 选中状态），不自动启动 VAD
  2. 新增"开始对话"触发点，用户主动操作后才启动 VAD
- **新增 Scenario**：
  - 重新进入页面 Hands free 不自动监听
  - 用户主动开始对话后才启动监听
- **修复版本**：V0.3.1 Step 5 + Step 6
```

### 验证

```bash
grep -c "BUG-001" BUG_LOG.md
grep -c "BUG-002" BUG_LOG.md
# 两行均应输出 ≥ 1
```

完成后打印：`✅ 模块一完成`

---

## 模块二：更新 SPEC_V031.md — 补充缺失 Scenarios

### 2.1 在 docs/spec/SPEC_V031.md 的 "Feature: Hands Free 实时对话" 末尾补充以下 Scenarios

```gherkin
Scenario: Alex 回复结束后自动恢复监听
  Given 当前为 Hands free 模式
  And   Alex 正在播放 TTS 回复
  When  TTS 播放完毕
  Then  VAD 自动恢复监听状态
  And   界面恢复显示监听动效（脉冲动画）
  And   用户无需任何操作即可直接说下一句

Scenario: Alex 说话时暂停 VAD 避免误触
  Given 当前为 Hands free 模式
  When  Alex 开始播放 TTS 回复
  Then  VAD 暂停检测
  And   Alex 的声音不触发录音
  When  TTS 播放完毕
  Then  VAD 自动恢复检测

Scenario: 重新进入页面 Hands free 不自动监听
  Given 用户上次设置了 Hands free
  When  用户关闭页面后重新进入
  Then  Voice Settings 中 Hands free 显示为选中状态
  And   VAD 不自动启动
  And   界面无监听动效
  And   需要用户主动点击开始才进入监听状态

Scenario: 用户主动开始对话后才启动监听
  Given 用户进入页面，activation 设置为 Hands free
  When  用户点击"开始对话"按钮
  Then  VAD 启动
  And   界面出现监听动效
```

### 2.2 在 SPEC 第三章"前端 UI 规格"新增状态机图

在 3.3 节之后插入：

```markdown
### 3.4 Hands Free 状态机

以下状态机定义了 Hands Free 模式的完整生命周期，
每条转换箭头对应一个 BDD Scenario。

stateDiagram-v2
    [*] --> 待机 : 页面加载（不论 activation 设置）
    待机 --> 监听中 : 用户点击"开始对话"且 activation=hands_free
    监听中 --> 录音中 : VAD 检测到语音
    录音中 --> 识别中 : 停顿超过 2 秒
    识别中 --> Alex说话中 : ASR 完成，消息发送给 Alex
    Alex说话中 --> 监听中 : TTS 播放完毕（自动恢复）
    Alex说话中 --> 监听中 : TTS 播放出错（降级恢复）
    监听中 --> 待机 : 用户切换为 Push to talk
    监听中 --> 待机 : 用户离开页面
    待机 --> [*] : 用户关闭 App
```

### 验证

```bash
grep -c "Alex 回复结束后自动恢复监听" docs/spec/SPEC_V031.md
grep -c "重新进入页面 Hands free 不自动监听" docs/spec/SPEC_V031.md
grep -c "状态机" docs/spec/SPEC_V031.md
# 三行均应输出 ≥ 1
```

完成后打印：`✅ 模块二完成`

---

## 模块三：修复 Step 5 — 页面加载不自动启动 VAD

### 3.1 修改前端页面初始化逻辑

找到前端 JavaScript 中的 `loadSettings()` 函数，
确保加载设置后只渲染 UI，不触发 VAD 启动：

```javascript
// ❌ 错误：加载设置后自动启动
async function loadSettings() {
  const resp = await fetch(`/settings/${userId}`);
  currentSettings = await resp.json();
  renderSettings();
  if (currentSettings.activation === "hands_free") {
    startHandsFreeMode(); // 不应在这里调用
  }
}

// ✅ 正确：只渲染，不启动
async function loadSettings() {
  const resp = await fetch(`/settings/${userId}`);
  currentSettings = await resp.json();
  renderSettings(); // 只更新 UI 选中状态
  // VAD 不在页面加载时启动
  // 等待用户主动点击"开始对话"
}
```

### 3.2 新增"开始对话"按钮

在对话界面适当位置（输入框上方或 Header 下方）新增：

```html
<!-- 仅 Hands free 模式下显示 -->
<div id="start-conversation-bar" class="hidden">
  <button id="start-btn" onclick="activateHandsFree()">
    🎤 点击开始对话
  </button>
</div>
```

```javascript
function renderSettings() {
  // ... 原有渲染逻辑 ...

  // 根据 activation 显示/隐藏开始按钮
  const bar = document.getElementById("start-conversation-bar");
  if (currentSettings.activation === "hands_free") {
    bar.classList.remove("hidden");
  } else {
    bar.classList.add("hidden");
  }
}

function activateHandsFree() {
  document.getElementById("start-conversation-bar").classList.add("hidden");
  startHandsFreeMode(); // 用户主动触发后才启动
}
```

### 3.3 新增测试：tests/test_step5_v031_bugfix.py

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.db import UserSettings, engine
from sqlalchemy.orm import sessionmaker

TEST_USER = "test_user_v031_step5_bugfix"
client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup():
    yield
    Session = sessionmaker(bind=engine)
    session = Session()
    session.query(UserSettings).filter_by(user_id=TEST_USER).delete()
    session.commit()
    session.close()

def test_hands_free_preference_persists_without_auto_activating():
    """
    设置 hands_free 后，再次读取仍是 hands_free，
    但这只是偏好，不代表 VAD 已启动（VAD 启动是前端行为，
    此处验证 API 层不返回任何"自动启动"指令）
    """
    client.post(f"/settings/{TEST_USER}", json={"activation": "hands_free"})
    resp = client.get(f"/settings/{TEST_USER}")
    data = resp.json()
    assert data["activation"] == "hands_free"
    # API 响应中不包含任何 auto_start 字段
    assert "auto_start" not in data
    assert "vad_active" not in data

def test_page_load_settings_only_returns_preference():
    """页面加载读取设置，返回偏好而非活跃状态"""
    client.post(f"/settings/{TEST_USER}", json={"activation": "hands_free"})
    resp = client.get(f"/settings/{TEST_USER}")
    # 只返回三个偏好字段
    data = resp.json()
    assert set(data.keys()) == {"voice", "speed", "activation"}
```

### 验证

```bash
pytest tests/test_step5_v031_bugfix.py -v
```

全部 PASS 后打印：`✅ 模块三完成`

---

## 模块四：修复 Step 6 — VAD 完整生命周期

### 4.1 修改 app/services/vad_service.py，新增状态管理

```python
from enum import Enum

class VADState(Enum):
    IDLE       = "idle"        # 待机，页面加载初始状态
    LISTENING  = "listening"   # 监听中
    RECORDING  = "recording"   # 录音中（检测到语音）
    PROCESSING = "processing"  # 识别中
    ALEX_SPEAKING = "alex_speaking"  # Alex TTS 播放中

class VADService:
    def __init__(self):
        self.model = load_silero_vad()
        self.misfire_count = 0
        self.state = VADState.IDLE  # 初始为待机

    def set_state(self, state: VADState):
        self.state = state

    def pause(self):
        """Alex 说话时调用，暂停 VAD 检测"""
        self.state = VADState.ALEX_SPEAKING

    def resume(self):
        """Alex 说话结束后调用，恢复监听"""
        self.state = VADState.LISTENING

    def can_detect(self) -> bool:
        """只有 LISTENING 状态才处理音频"""
        return self.state == VADState.LISTENING
```

### 4.2 修改前端 TTS 播放逻辑，播放前暂停 VAD，播放后恢复

```javascript
async function playAlexReply(audioUrl) {
  // Alex 开始说话：通知后端/前端暂停 VAD
  pauseVAD();
  showAlexSpeakingState();

  const audio = new Audio(audioUrl);
  audio.onended = () => {
    // Alex 说完：自动恢复监听
    resumeVAD();
    showListeningState();
  };
  audio.onerror = () => {
    // 播放出错：降级恢复监听，不卡死
    resumeVAD();
    showListeningState();
  };
  audio.play();
}

function pauseVAD() {
  if (wsVAD && wsVAD.readyState === WebSocket.OPEN) {
    wsVAD.send(JSON.stringify({ command: "pause" }));
  }
}

function resumeVAD() {
  if (wsVAD && wsVAD.readyState === WebSocket.OPEN) {
    wsVAD.send(JSON.stringify({ command: "resume" }));
  }
}
```

### 4.3 新增测试：tests/test_step6_v031_bugfix.py

```python
import pytest
from unittest.mock import patch
from app.services.vad_service import VADService, VADState

def test_vad_initial_state_is_idle():
    """页面加载时 VAD 初始状态为 IDLE，不自动监听"""
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        assert vad.state == VADState.IDLE
        assert vad.can_detect() == False  # IDLE 状态不检测

def test_vad_pauses_when_alex_speaks():
    """Alex 开始说话时 VAD 暂停"""
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        vad.set_state(VADState.LISTENING)
        vad.pause()
        assert vad.state == VADState.ALEX_SPEAKING
        assert vad.can_detect() == False

def test_vad_resumes_after_alex_finishes():
    """Alex 说完后 VAD 自动恢复监听"""
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        vad.set_state(VADState.ALEX_SPEAKING)
        vad.resume()
        assert vad.state == VADState.LISTENING
        assert vad.can_detect() == True

def test_vad_does_not_detect_in_alex_speaking_state():
    """Alex 说话期间 VAD 不处理音频，避免 Alex 声音触发录音"""
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        vad.set_state(VADState.ALEX_SPEAKING)
        assert vad.can_detect() == False

def test_vad_resumes_after_tts_error():
    """TTS 播放出错时 VAD 也能恢复，不卡死"""
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        vad.set_state(VADState.ALEX_SPEAKING)
        vad.resume()  # onerror 回调中也调用 resume
        assert vad.state == VADState.LISTENING

def test_vad_listening_state_can_detect():
    """仅 LISTENING 状态下 can_detect 为 True"""
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        for state in VADState:
            vad.set_state(state)
            if state == VADState.LISTENING:
                assert vad.can_detect() == True
            else:
                assert vad.can_detect() == False
```

### 验证

```bash
pytest tests/test_step6_v031_bugfix.py -v
```

全部 PASS 后打印：`✅ 模块四完成`

---

## 模块五：更新 CLAUDE_CODE_DOC_STANDARD.md — 规范升级至 V2.2

### 5.1 在"九、工作规则"末尾（第 12 条之后）新增第 13、14 条

```markdown
13. **每个版本开始时，Claude Code 负责创建文档文件**

    接收到启动指令后，Step 0 的第一件事是在正确路径创建文档文件：

    - SPEC 文件    → `docs/spec/SPEC_Vxxx.md`
    - INSTRUCTIONS → `.claude/INSTRUCTIONS_Vxxx.md`

    文件内容由 Claude（规划者）在对话中与 Human 确认，
    Claude Code 负责将最终内容写入正确路径，不得自行修改内容。

14. **实时功能必须通过状态机自检**

    对含持续运行逻辑的 Feature（VAD、WebSocket、音视频流等），
    生成 Scenarios 后，Claude 必须在提交 Human 确认前完成以下自检：

    □ 列出该功能的所有状态，确认无遗漏
    □ 确认每个状态的"正常退出"路径有 Scenario
    □ 确认每个状态的"异常退出"路径有 Scenario（网络错误、超时、用户切后台）
    □ 确认没有状态是"进得去、出不来"的死胡同
    □ 在 SPEC 对应章节提供 stateDiagram-v2 状态机图

    自检未通过则补充 Scenario 和状态机图后，再提交 Human 确认。
```

### 5.2 在"三、BDD Scenarios 写法"末尾新增 3.4

```markdown
### 3.4 实时功能的额外要求

凡 Feature 涉及持续运行、状态循环、WebSocket、音视频流，
除标准 Scenarios 外，必须在 SPEC 对应 UI 规格章节提供状态机图
（stateDiagram-v2），且每条状态转换箭头必须有对应的 Scenario。

区分"用户偏好"与"会话状态"：
- 用户偏好（voice/speed/activation）→ 持久化到 DB，页面加载时渲染 UI
- 会话状态（VAD 是否运行）→ 不持久化，需用户主动触发，页面加载时归零
```

### 5.3 在"五、Instructions 文档结构"的 Step N 模板之前插入 Step 0 模板

```markdown
## Step 0：文档归档（每个版本固定，位置不可变）

> 覆盖 Story：TECH
> 技术目标：将本版本文档写入正确路径，确保目录结构符合规范

### 实现

**0.1 确认目录存在，不存在则创建**

```bash
mkdir -p docs/spec
mkdir -p .claude
```

**0.2 将 SPEC 内容写入正确路径**

Human 已提供内容，Claude Code 写入：
`docs/spec/SPEC_Vxxx.md`

**0.3 将 INSTRUCTIONS 内容写入正确路径**

Human 已提供内容，Claude Code 写入：
`.claude/INSTRUCTIONS_Vxxx.md`

**0.4 更新 CLAUDE.md 中当前版本状态为"进行中 🔄"**

### 自测

```bash
test -f docs/spec/SPEC_Vxxx.md       && echo "SPEC ✅"         || echo "SPEC ❌ 缺失"
test -f .claude/INSTRUCTIONS_Vxxx.md  && echo "INSTRUCTIONS ✅" || echo "INSTRUCTIONS ❌ 缺失"
```

两行均输出 ✅ 后打印 `✅ Step 0 完成`
```

### 5.4 更新"十三、版本开始标准提示词"中的步骤列表

找到：
```
4. 我确认后，生成完整 SPEC 和 Instructions
```

替换为：
```
4. 我确认后，生成完整 SPEC 和 Instructions
5. 将最终确认的 SPEC 和 Instructions 内容发给 Claude Code
6. Claude Code 执行 Step 0 写入文件，然后从 Step 1 开始执行
```

### 5.5 更新文档版本号

将文档末尾：
```
*CLAUDE_CODE_DOC_STANDARD.md V2.1 — 最后更新 2026-03-10*
```
更新为：
```
*CLAUDE_CODE_DOC_STANDARD.md V2.2 — 最后更新 2026-03-11*
```

### 验证

```bash
grep -c "每个版本开始时，Claude Code 负责创建文档文件" CLAUDE_CODE_DOC_STANDARD.md
grep -c "实时功能必须通过状态机自检" CLAUDE_CODE_DOC_STANDARD.md
grep -c "Step 0：文档归档" CLAUDE_CODE_DOC_STANDARD.md
grep -c "3.4 实时功能的额外要求" CLAUDE_CODE_DOC_STANDARD.md
grep -c "V2.2" CLAUDE_CODE_DOC_STANDARD.md
# 五行均应输出 ≥ 1
```

完成后打印：`✅ 模块五完成`

---

## 模块六：全量回归验证

```bash
echo "=== V0.3.1 全量测试 ==="
pytest tests/test_step1_v031.py \
       tests/test_step2_v031.py \
       tests/test_step3_v031.py \
       tests/test_step4_v031.py \
       tests/test_step5_v031.py \
       tests/test_step5_v031_bugfix.py \
       tests/test_step6_v031.py \
       tests/test_step6_v031_bugfix.py \
       -v
```

### 完成汇报模板

```markdown
## Bug 修复 + 规范升级 完成汇报

### Bug 修复状态
- BUG-001（Alex 回复后未恢复监听）  ✅ 已修复
- BUG-002（重新进入页面自动监听）   ✅ 已修复

### 测试结果
✅ 通过：N 个用例
❌ 失败：0 个用例

### 规范升级状态
- 工作规则第 13 条（Claude Code 创建文档）  ✅
- 工作规则第 14 条（实时功能状态机自检）    ✅
- BDD 3.4（实时功能额外要求）               ✅
- Step 0 模板（文档归档）                   ✅
- 版本开始提示词更新                        ✅
- CLAUDE_CODE_DOC_STANDARD.md → V2.2       ✅

### SPEC 更新状态
- docs/spec/SPEC_V031.md 补充 4 个 Scenario ✅
- 新增 Hands Free 状态机图                  ✅

### BUG_LOG 状态
- BUG-001  🟡 修复中 → ✅ 已修复
- BUG-002  🟡 修复中 → ✅ 已修复

### 待 Human 人工验收
- [ ] Alex 说完后能否自动继续说下一句（无需刷新）
- [ ] 重新进入页面 VAD 是否不自动启动
- [ ] 点击"开始对话"后 VAD 是否正确启动
- [ ] Alex 说话期间用户说话是否不被误录
```

完成后打印：`✅ 模块六完成，等待 Human 人工验收`

---

## 执行顺序总览

```
模块一：BUG_LOG 初始化 + 登记 Bug          （5分钟）
    ↓
模块二：SPEC_V031 补充缺失 Scenarios        （5分钟）
    ↓
模块三：修复 Step 5 — 页面加载不自动启动   （15分钟）
    ↓
模块四：修复 Step 6 — VAD 完整生命周期     （20分钟）
    ↓
模块五：CLAUDE_CODE_DOC_STANDARD → V2.2    （10分钟）
    ↓
模块六：全量回归 + 汇报                    （5分钟）
```

---

*任务清单生成于 2026-03-11*