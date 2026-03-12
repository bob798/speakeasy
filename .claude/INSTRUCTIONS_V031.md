# Speakeasy V0.3.1 — Claude Code 执行指令

> 前置条件：V0.2b 已验收完成，venv 已激活
> SPEC 文件：SPEC_V031.md
> 执行方式：按 Step 顺序，逐步执行，每步全绿后再进入下一步

---

## 工作规则

1. 按 Step 顺序执行，不跳步
2. 每个 Step = 实现代码 + 自测脚本，测试全部 PASS 才进入下一步
3. 测试未通过则自行修复，直到全绿
4. 所有 pip install 在激活的 venv 中执行
5. 测试数据使用独立 user_id：`test_user_v031_stepN`，每个测试后清理
6. 不修改 V0.2b 已完成的代码和测试
7. mock 策略：只 mock 外部 LLM 调用和 edge-tts 网络请求，不 mock 内部服务
8. 断言必须用具体值，禁止模糊断言（如 `assert result is not None`）
9. 每个 Step 完成后：
   · 终端打印 `✅ Step N 完成`
   · 将 CLAUDE.md 中对应 Step 的 `⬜ 未开始` 更新为 `✅ 完成`
10. 遇到文档未覆盖的情况，停下来向 Human 提问，不自行决策

---

## Step 1：环境准备 + user_settings 数据表

> SPEC 覆盖：SPEC-12
> 覆盖 Story：TECH（纯技术 Step）
> 技术目标：新增 user_settings 表，安装 VAD 依赖，验证环境就绪

### 实现

**1.1 安装依赖**

```bash
pip install silero-vad --break-system-packages
pip install torch --break-system-packages  # silero-vad 依赖
```

**1.2 在 `app/models/db.py` 新增 user_settings 表**

```python
class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id    = Column(String, primary_key=True)
    voice      = Column(String, nullable=False, default="warm")
    speed      = Column(String, nullable=False, default="normal")
    activation = Column(String, nullable=False, default="push_to_talk")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**1.3 执行数据库迁移**

```python
# 在 app/models/db.py 的 create_all 中自动创建新表
Base.metadata.create_all(bind=engine)
```

**1.4 验证 Silero VAD 可导入**

```python
import silero_vad
model = silero_vad.load_silero_vad()
assert model is not None
```

### 自测脚本：tests/test_step1_v031.py

```python
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from app.models.db import Base, UserSettings
from datetime import datetime

TEST_USER = "test_user_v031_step1"
TEST_DB = "sqlite:///test_v031_step1.db"

@pytest.fixture(autouse=True)
def setup_db():
    engine = create_engine(TEST_DB)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.query(UserSettings).filter_by(user_id=TEST_USER).delete()
    session.commit()
    session.close()
    Base.metadata.drop_all(engine)

def test_user_settings_table_exists(setup_db):
    engine = create_engine(TEST_DB)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "user_settings" in tables

def test_user_settings_columns(setup_db):
    engine = create_engine(TEST_DB)
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("user_settings")}
    assert columns == {"user_id", "voice", "speed", "activation", "updated_at"}

def test_user_settings_default_values(setup_db):
    session = setup_db
    settings = UserSettings(user_id=TEST_USER)
    session.add(settings)
    session.commit()
    result = session.query(UserSettings).filter_by(user_id=TEST_USER).first()
    assert result.voice == "warm"
    assert result.speed == "normal"
    assert result.activation == "push_to_talk"

def test_silero_vad_importable():
    import silero_vad
    model = silero_vad.load_silero_vad()
    assert model is not None
```

运行：`pytest tests/test_step1_v031.py -v`
全部 PASS 后打印 `✅ Step 1 完成`

---

## Step 2：用户设置服务 + API 接口

> SPEC 覆盖：SPEC-01 · SPEC-02 · SPEC-03 · SPEC-04
> 覆盖 Story：US-01 · US-02

### 实现

**2.1 新建 `app/services/settings_service.py`**

```python
from sqlalchemy.orm import Session
from app.models.db import UserSettings
from datetime import datetime

VALID_VOICES = {"warm", "steady", "bright"}
VALID_SPEEDS = {"slow", "normal", "fast"}
VALID_ACTIVATIONS = {"hands_free", "push_to_talk"}

VOICE_MAP = {
    "warm":   "en-US-JennyNeural",
    "steady": "en-US-GuyNeural",
    "bright": "en-US-AriaNeural",
}

SPEED_MAP = {
    "slow":   "-25%",
    "normal": "+0%",
    "fast":   "+25%",
}

def get_settings(db: Session, user_id: str) -> UserSettings:
    settings = db.query(UserSettings).filter_by(user_id=user_id).first()
    if not settings:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

def update_settings(db: Session, user_id: str, updates: dict) -> UserSettings:
    if "voice" in updates and updates["voice"] not in VALID_VOICES:
        raise ValueError(f"Invalid voice: {updates['voice']}")
    if "speed" in updates and updates["speed"] not in VALID_SPEEDS:
        raise ValueError(f"Invalid speed: {updates['speed']}")
    if "activation" in updates and updates["activation"] not in VALID_ACTIVATIONS:
        raise ValueError(f"Invalid activation: {updates['activation']}")

    settings = get_settings(db, user_id)
    for key, value in updates.items():
        setattr(settings, key, value)
    settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings)
    return settings

def get_tts_params(db: Session, user_id: str) -> dict:
    """返回 edge-tts 所需的 voice 和 rate 参数"""
    settings = get_settings(db, user_id)
    return {
        "voice": VOICE_MAP.get(settings.voice, "en-US-JennyNeural"),
        "rate":  SPEED_MAP.get(settings.speed, "+0%"),
    }
```

**2.2 新建 `app/routers/settings.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.models.db import get_db
from app.services.settings_service import get_settings, update_settings

router = APIRouter()

@router.get("/settings/{user_id}")
def read_settings(user_id: str, db: Session = Depends(get_db)):
    settings = get_settings(db, user_id)
    return {
        "voice": settings.voice,
        "speed": settings.speed,
        "activation": settings.activation,
    }

@router.post("/settings/{user_id}")
def write_settings(user_id: str, payload: dict, db: Session = Depends(get_db)):
    settings = update_settings(db, user_id, payload)
    return {
        "success": True,
        "settings": {
            "voice": settings.voice,
            "speed": settings.speed,
            "activation": settings.activation,
        }
    }
```

**2.3 在 `app/main.py` 注册路由**

```python
from app.routers.settings import router as settings_router
app.include_router(settings_router)
```

### 自测脚本：tests/test_step2_v031.py

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.db import Base, UserSettings, engine
from sqlalchemy.orm import sessionmaker

TEST_USER = "test_user_v031_step2"
client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup():
    yield
    Session = sessionmaker(bind=engine)
    session = Session()
    session.query(UserSettings).filter_by(user_id=TEST_USER).delete()
    session.commit()
    session.close()

def test_get_settings_returns_defaults_for_new_user():
    resp = client.get(f"/settings/{TEST_USER}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["voice"] == "warm"
    assert data["speed"] == "normal"
    assert data["activation"] == "push_to_talk"

def test_post_settings_updates_voice():
    resp = client.post(f"/settings/{TEST_USER}", json={"voice": "steady"})
    assert resp.status_code == 200
    assert resp.json()["settings"]["voice"] == "steady"

def test_post_settings_updates_speed():
    resp = client.post(f"/settings/{TEST_USER}", json={"speed": "slow"})
    assert resp.status_code == 200
    assert resp.json()["settings"]["speed"] == "slow"

def test_post_settings_updates_activation():
    resp = client.post(f"/settings/{TEST_USER}", json={"activation": "hands_free"})
    assert resp.status_code == 200
    assert resp.json()["settings"]["activation"] == "hands_free"

def test_post_settings_partial_update_preserves_other_fields():
    # 先设置完整状态
    client.post(f"/settings/{TEST_USER}", json={
        "voice": "bright", "speed": "fast", "activation": "hands_free"
    })
    # 只更新 speed
    resp = client.post(f"/settings/{TEST_USER}", json={"speed": "slow"})
    data = resp.json()["settings"]
    assert data["voice"] == "bright"       # 保持不变
    assert data["speed"] == "slow"         # 已更新
    assert data["activation"] == "hands_free"  # 保持不变

def test_post_settings_rejects_invalid_voice():
    resp = client.post(f"/settings/{TEST_USER}", json={"voice": "invalid_voice"})
    assert resp.status_code == 422

def test_settings_persist_across_requests():
    client.post(f"/settings/{TEST_USER}", json={"voice": "bright", "speed": "fast"})
    resp = client.get(f"/settings/{TEST_USER}")
    data = resp.json()
    assert data["voice"] == "bright"
    assert data["speed"] == "fast"
```

运行：`pytest tests/test_step2_v031.py -v`
全部 PASS 后打印 `✅ Step 2 完成`

---

## Step 3：TTS 层集成语速与音色

> SPEC 覆盖：SPEC-01 · SPEC-02 · SPEC-03 · SPEC-04
> 覆盖 Story：US-01 · US-02
> 覆盖 Scenarios：用户切换语速后 Alex 下一句按新语速播放 · 用户切换音色后 Alex 声音立刻改变

### 实现

**3.1 修改 `app/routers/chat.py`，在 TTS 调用处读取用户设置**

在现有 `/chat` 路由中，调用 TTS 之前注入 voice 和 rate：

```python
from app.services.settings_service import get_tts_params

# 在生成 TTS 时：
tts_params = get_tts_params(db, user_id)
communicate = edge_tts.Communicate(
    text    = alex_reply,
    voice   = tts_params["voice"],   # 原来硬编码，现在从设置读取
    rate    = tts_params["rate"],    # 原来硬编码，现在从设置读取
)
```

**3.2 降级处理**

```python
# 如果指定音色不可用，降级到 Jenny
try:
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await communicate.save(output_path)
except Exception:
    communicate = edge_tts.Communicate(
        text=text, voice="en-US-JennyNeural", rate="+0%"
    )
    await communicate.save(output_path)
```

### 自测脚本：tests/test_step3_v031.py

```python
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.models.db import UserSettings, engine
from sqlalchemy.orm import sessionmaker

TEST_USER = "test_user_v031_step3"
client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup():
    yield
    Session = sessionmaker(bind=engine)
    session = Session()
    session.query(UserSettings).filter_by(user_id=TEST_USER).delete()
    session.commit()
    session.close()

def test_tts_uses_warm_voice_by_default():
    """默认设置下 TTS 使用 JennyNeural"""
    captured = {}
    original_communicate = __import__("edge_tts").Communicate

    def mock_communicate(text, voice, rate, **kwargs):
        captured["voice"] = voice
        captured["rate"] = rate
        return AsyncMock()

    with patch("edge_tts.Communicate", side_effect=mock_communicate):
        with patch("app.services.chat_service.get_llm_reply", return_value="Hello!"):
            client.post("/chat", json={"user_id": TEST_USER, "message": "Hi"})

    assert captured.get("voice") == "en-US-JennyNeural"
    assert captured.get("rate") == "+0%"

def test_tts_uses_steady_voice_after_setting_change():
    """切换到 Steady 后 TTS 使用 GuyNeural"""
    client.post(f"/settings/{TEST_USER}", json={"voice": "steady"})
    captured = {}

    def mock_communicate(text, voice, rate, **kwargs):
        captured["voice"] = voice
        captured["rate"] = rate
        return AsyncMock()

    with patch("edge_tts.Communicate", side_effect=mock_communicate):
        with patch("app.services.chat_service.get_llm_reply", return_value="Hello!"):
            client.post("/chat", json={"user_id": TEST_USER, "message": "Hi"})

    assert captured.get("voice") == "en-US-GuyNeural"

def test_tts_uses_slow_rate_after_setting_change():
    """切换到 Slow 后 TTS rate 为 -25%"""
    client.post(f"/settings/{TEST_USER}", json={"speed": "slow"})
    captured = {}

    def mock_communicate(text, voice, rate, **kwargs):
        captured["rate"] = rate
        return AsyncMock()

    with patch("edge_tts.Communicate", side_effect=mock_communicate):
        with patch("app.services.chat_service.get_llm_reply", return_value="Hello!"):
            client.post("/chat", json={"user_id": TEST_USER, "message": "Hi"})

    assert captured.get("rate") == "-25%"

def test_tts_fast_rate():
    client.post(f"/settings/{TEST_USER}", json={"speed": "fast"})
    captured = {}

    def mock_communicate(text, voice, rate, **kwargs):
        captured["rate"] = rate
        return AsyncMock()

    with patch("edge_tts.Communicate", side_effect=mock_communicate):
        with patch("app.services.chat_service.get_llm_reply", return_value="Hello!"):
            client.post("/chat", json={"user_id": TEST_USER, "message": "Hi"})

    assert captured.get("rate") == "+25%"
```

运行：`pytest tests/test_step3_v031.py -v`
全部 PASS 后打印 `✅ Step 3 完成`

---

## Step 4：VAD 服务（Hands Free 核心）

> SPEC 覆盖：SPEC-07 · SPEC-08 · SPEC-09
> 覆盖 Story：US-03
> 覆盖 Scenarios：VAD 检测说完后自动发送 · 误触提示

### 实现

**4.1 新建 `app/services/vad_service.py`**

```python
import torch
import numpy as np
from silero_vad import load_silero_vad

SAMPLE_RATE = 16000
SILENCE_THRESHOLD_SECONDS = 2.0
MISFIRE_MAX_COUNT = 3
MIN_TRANSCRIPT_LENGTH = 2  # 少于2字符视为误触

class VADService:
    def __init__(self):
        self.model = load_silero_vad()
        self.misfire_count = 0

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """判断音频块是否包含语音"""
        tensor = torch.FloatTensor(audio_chunk)
        confidence = self.model(tensor, SAMPLE_RATE).item()
        return confidence > 0.5

    def is_misfire(self, transcript: str) -> bool:
        """判断识别结果是否为误触"""
        return len(transcript.strip()) < MIN_TRANSCRIPT_LENGTH

    def record_misfire(self) -> bool:
        """记录一次误触，返回是否达到提示阈值"""
        self.misfire_count += 1
        return self.misfire_count >= MISFIRE_MAX_COUNT

    def reset_misfire_count(self):
        self.misfire_count = 0

    def get_silence_threshold(self) -> float:
        return SILENCE_THRESHOLD_SECONDS
```

**4.2 新建 `app/routers/vad.py`（WebSocket 接口）**

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.vad_service import VADService
from app.services.settings_service import get_settings
from app.models.db import get_db
import numpy as np
import json

router = APIRouter()

@router.websocket("/ws/vad/{user_id}")
async def vad_endpoint(websocket: WebSocket, user_id: str):
    await websocket.accept()
    vad = VADService()
    audio_buffer = []
    silence_frames = 0
    is_recording = False
    FRAMES_PER_SECOND = 25  # 40ms per chunk
    SILENCE_FRAMES = int(vad.get_silence_threshold() * FRAMES_PER_SECOND)

    try:
        while True:
            data = await websocket.receive_bytes()
            audio_chunk = np.frombuffer(data, dtype=np.float32)

            speech_detected = vad.is_speech(audio_chunk)

            if speech_detected:
                is_recording = True
                silence_frames = 0
                audio_buffer.append(audio_chunk)
                await websocket.send_json({"event": "speech_start"})

            elif is_recording:
                silence_frames += 1
                audio_buffer.append(audio_chunk)

                if silence_frames >= SILENCE_FRAMES:
                    # 说完了，发送给 ASR
                    full_audio = np.concatenate(audio_buffer)
                    await websocket.send_json({
                        "event": "speech_end",
                        "audio_length": len(full_audio)
                    })
                    audio_buffer.clear()
                    is_recording = False
                    silence_frames = 0

    except WebSocketDisconnect:
        pass
```

**4.3 在 `app/main.py` 注册**

```python
from app.routers.vad import router as vad_router
app.include_router(vad_router)
```

### 自测脚本：tests/test_step4_v031.py

```python
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from app.services.vad_service import VADService

def make_audio_chunk(has_speech: bool) -> np.ndarray:
    """生成模拟音频块"""
    return np.random.randn(512).astype(np.float32)

def test_vad_service_initializes():
    with patch("app.services.vad_service.load_silero_vad") as mock_load:
        mock_load.return_value = MagicMock()
        vad = VADService()
        assert vad.model is not None
        assert vad.misfire_count == 0

def test_is_misfire_empty_transcript():
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        assert vad.is_misfire("") == True
        assert vad.is_misfire(" ") == True

def test_is_misfire_single_char():
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        assert vad.is_misfire("a") == True

def test_is_not_misfire_valid_transcript():
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        assert vad.is_misfire("ok") == False
        assert vad.is_misfire("这个 deadline") == False

def test_misfire_count_accumulates():
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        assert vad.record_misfire() == False  # 1次，未达阈值
        assert vad.record_misfire() == False  # 2次，未达阈值
        assert vad.record_misfire() == True   # 3次，达到阈值

def test_misfire_count_resets():
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        vad.record_misfire()
        vad.record_misfire()
        vad.reset_misfire_count()
        assert vad.misfire_count == 0

def test_silence_threshold_is_2_seconds():
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        assert vad.get_silence_threshold() == 2.0
```

运行：`pytest tests/test_step4_v031.py -v`
全部 PASS 后打印 `✅ Step 4 完成`

---

## Step 5：前端 Voice Settings UI

> SPEC 覆盖：SPEC-05 · SPEC-06
> 覆盖 Story：US-01 · US-02 · US-03
> 覆盖 Scenarios：Voice Settings bottom sheet · ⚙️ Header 入口 · 设置自动保存

### 实现

**5.1 修改对话页面 HTML，在 Header 添加 ⚙️**

```html
<!-- Header -->
<div id="chat-header">
  <button id="back-btn">←</button>
  <div id="header-title">
    <span id="alex-name">Alex</span>
    <span id="hands-free-badge" class="hidden">· Hands free 🟢</span>
  </div>
  <div id="header-actions">
    <button id="voice-toggle-btn">🔊</button>
    <button id="settings-btn" onclick="openVoiceSettings()">⚙️</button>
  </div>
</div>
```

**5.2 Voice Settings Bottom Sheet HTML**

```html
<div id="voice-settings-sheet" class="bottom-sheet hidden">
  <div class="sheet-handle"></div>
  <div class="sheet-header">
    <span>Voice Settings</span>
    <button onclick="closeVoiceSettings()">✕</button>
  </div>

  <!-- Voice -->
  <div class="settings-section">
    <label>Voice</label>
    <div class="option-group" id="voice-options">
      <button class="option-btn" data-value="warm" onclick="selectVoice('warm')">
        <div>Warm</div><div class="sub">Jenny</div>
      </button>
      <button class="option-btn" data-value="steady" onclick="selectVoice('steady')">
        <div>Steady</div><div class="sub">Guy</div>
      </button>
      <button class="option-btn" data-value="bright" onclick="selectVoice('bright')">
        <div>Bright</div><div class="sub">Aria</div>
      </button>
    </div>
  </div>

  <!-- Speed -->
  <div class="settings-section">
    <label>Speed</label>
    <div class="option-group" id="speed-options">
      <button class="option-btn" data-value="slow" onclick="selectSpeed('slow')">Slow</button>
      <button class="option-btn" data-value="normal" onclick="selectSpeed('normal')">Normal</button>
      <button class="option-btn" data-value="fast" onclick="selectSpeed('fast')">Fast</button>
    </div>
  </div>

  <!-- Activation -->
  <div class="settings-section">
    <label>Activation</label>
    <div id="activation-options">
      <div class="activation-item" onclick="selectActivation('hands_free')">
        <div>
          <div>Hands free</div>
          <div class="sub">Best for quiet environments</div>
        </div>
        <span id="check-hands-free"></span>
      </div>
      <div class="activation-item" onclick="selectActivation('push_to_talk')">
        <div>
          <div>Push to talk</div>
          <div class="sub">Hold to speak, release to send</div>
        </div>
        <span id="check-push-to-talk"></span>
      </div>
    </div>
  </div>
</div>
```

**5.3 JavaScript 设置逻辑**

```javascript
let currentSettings = { voice: "warm", speed: "normal", activation: "push_to_talk" };

async function loadSettings() {
  const resp = await fetch(`/settings/${userId}`);
  currentSettings = await resp.json();
  renderSettings();
}

function renderSettings() {
  // 高亮当前选中项
  document.querySelectorAll("#voice-options .option-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.value === currentSettings.voice);
  });
  document.querySelectorAll("#speed-options .option-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.value === currentSettings.speed);
  });
  // Activation 勾选
  document.getElementById("check-hands-free").textContent =
    currentSettings.activation === "hands_free" ? "✓" : "";
  document.getElementById("check-push-to-talk").textContent =
    currentSettings.activation === "push_to_talk" ? "✓" : "";
  // Header badge
  const badge = document.getElementById("hands-free-badge");
  badge.classList.toggle("hidden", currentSettings.activation !== "hands_free");
}

async function saveSetting(updates) {
  await fetch(`/settings/${userId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  Object.assign(currentSettings, updates);
  renderSettings();
}

function selectVoice(value) { saveSetting({ voice: value }); }
function selectSpeed(value) { saveSetting({ speed: value }); }
function selectActivation(value) {
  saveSetting({ activation: value });
  if (value === "hands_free") startHandsFreeMode();
  else stopHandsFreeMode();
}

function openVoiceSettings() {
  document.getElementById("voice-settings-sheet").classList.remove("hidden");
}
function closeVoiceSettings() {
  document.getElementById("voice-settings-sheet").classList.add("hidden");
}
```

**5.4 CSS 核心样式（Bottom Sheet）**

```css
.bottom-sheet {
  position: fixed;
  bottom: 0; left: 0; right: 0;
  background: #1a1a1a;
  border-radius: 16px 16px 0 0;
  padding: 16px;
  transition: transform 0.3s ease;
  z-index: 100;
}
.option-btn.active {
  background: #1a5cff;
  color: white;
}
.option-btn {
  padding: 12px 20px;
  border-radius: 10px;
  border: 1px solid #333;
  background: transparent;
  color: #fff;
  cursor: pointer;
}
```

### 自测脚本：tests/test_step5_v031.py

```python
"""
前端 UI 测试：验证 Voice Settings API 交互逻辑正确
（UI 渲染验证需人工打开浏览器确认，此处测试 API 层的配合）
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.db import UserSettings, engine
from sqlalchemy.orm import sessionmaker

TEST_USER = "test_user_v031_step5"
client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup():
    yield
    Session = sessionmaker(bind=engine)
    session = Session()
    session.query(UserSettings).filter_by(user_id=TEST_USER).delete()
    session.commit()
    session.close()

def test_settings_page_returns_200():
    """前端页面可访问"""
    resp = client.get("/")
    assert resp.status_code == 200

def test_settings_api_roundtrip_voice():
    """前端保存音色后，再次读取值一致"""
    client.post(f"/settings/{TEST_USER}", json={"voice": "bright"})
    resp = client.get(f"/settings/{TEST_USER}")
    assert resp.json()["voice"] == "bright"

def test_settings_api_roundtrip_speed():
    """前端保存语速后，再次读取值一致"""
    client.post(f"/settings/{TEST_USER}", json={"speed": "fast"})
    resp = client.get(f"/settings/{TEST_USER}")
    assert resp.json()["speed"] == "fast"

def test_settings_api_roundtrip_activation():
    """前端保存激活方式后，再次读取值一致"""
    client.post(f"/settings/{TEST_USER}", json={"activation": "hands_free"})
    resp = client.get(f"/settings/{TEST_USER}")
    assert resp.json()["activation"] == "hands_free"

def test_all_three_settings_saved_together():
    """三项同时保存"""
    client.post(f"/settings/{TEST_USER}", json={
        "voice": "steady",
        "speed": "slow",
        "activation": "hands_free"
    })
    resp = client.get(f"/settings/{TEST_USER}")
    data = resp.json()
    assert data["voice"] == "steady"
    assert data["speed"] == "slow"
    assert data["activation"] == "hands_free"
```

运行：`pytest tests/test_step5_v031.py -v`
全部 PASS 后打印 `✅ Step 5 完成`

---

## Step 6：Hands Free 前端集成

> SPEC 覆盖：SPEC-07 · SPEC-08 · SPEC-09 · SPEC-10 · SPEC-11
> 覆盖 Story：US-03
> 覆盖 Scenarios：切换 Hands free 后出现监听动效 · VAD 说完自动发送 · 误触提示 · Push to talk 保持不变

### 实现

**6.1 前端 Hands Free 控制器（JavaScript）**

```javascript
let wsVAD = null;
let misfireCount = 0;
const MISFIRE_MAX = 3;

function startHandsFreeMode() {
  // 显示监听状态动效
  document.getElementById("listening-indicator").classList.remove("hidden");

  // 建立 VAD WebSocket 连接
  wsVAD = new WebSocket(`ws://localhost:8000/ws/vad/${userId}`);

  wsVAD.onmessage = async (event) => {
    const msg = JSON.parse(event.data);

    if (msg.event === "speech_start") {
      showRecordingAnimation();
    }

    if (msg.event === "speech_end") {
      // 停止录音，发送给 ASR
      const audioBlob = stopRecording();
      const transcript = await sendToASR(audioBlob);

      if (!transcript || transcript.trim().length < 2) {
        // 误触处理
        misfireCount++;
        if (misfireCount >= MISFIRE_MAX) {
          showMisfireToast();
        }
      } else {
        misfireCount = 0;
        await sendMessage(transcript);
      }
      resetRecordingAnimation();
    }
  };

  startMicrophoneStream(wsVAD);
}

function stopHandsFreeMode() {
  if (wsVAD) { wsVAD.close(); wsVAD = null; }
  document.getElementById("listening-indicator").classList.add("hidden");
  misfireCount = 0;
}

function showMisfireToast() {
  const toast = document.getElementById("misfire-toast");
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 3000);
}
```

**6.2 误触提示 HTML**

```html
<div id="misfire-toast" class="toast hidden">
  环境较嘈杂，建议切换为 Push to talk
  <button onclick="this.parentElement.classList.add('hidden')">✕</button>
</div>

<div id="listening-indicator" class="hidden">
  <div class="pulse-animation">🎤</div>
</div>
```

**6.3 Push to talk 保持不变**

Hands free 关闭时（`stopHandsFreeMode()`），原有录音按钮的 `mousedown/mouseup` 事件逻辑完全不受影响，无需修改。

### 自测脚本：tests/test_step6_v031.py

```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.vad_service import VADService
from app.services.settings_service import get_settings, update_settings
from app.models.db import UserSettings, engine, get_db
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.main import app

TEST_USER = "test_user_v031_step6"
client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup():
    yield
    Session = sessionmaker(bind=engine)
    session = Session()
    session.query(UserSettings).filter_by(user_id=TEST_USER).delete()
    session.commit()
    session.close()

def test_activation_switches_to_hands_free():
    resp = client.post(f"/settings/{TEST_USER}", json={"activation": "hands_free"})
    assert resp.status_code == 200
    assert resp.json()["settings"]["activation"] == "hands_free"

def test_activation_switches_back_to_push_to_talk():
    client.post(f"/settings/{TEST_USER}", json={"activation": "hands_free"})
    resp = client.post(f"/settings/{TEST_USER}", json={"activation": "push_to_talk"})
    assert resp.json()["settings"]["activation"] == "push_to_talk"

def test_misfire_threshold_triggers_at_3():
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        assert vad.record_misfire() == False
        assert vad.record_misfire() == False
        result = vad.record_misfire()
        assert result == True  # 第3次触发提示

def test_misfire_does_not_auto_switch_mode():
    """误触达到阈值后，activation 设置不自动改变"""
    client.post(f"/settings/{TEST_USER}", json={"activation": "hands_free"})
    # 模拟3次误触
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        for _ in range(3):
            vad.record_misfire()
    # 验证 activation 仍为 hands_free
    resp = client.get(f"/settings/{TEST_USER}")
    assert resp.json()["activation"] == "hands_free"

def test_chinese_english_mixed_input_passes_through():
    """中英混合输入不被过滤"""
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        mixed_text = "这个 deadline 能不能 push 一下"
        assert vad.is_misfire(mixed_text) == False
```

运行：`pytest tests/test_step6_v031.py -v`
全部 PASS 后打印 `✅ Step 6 完成`

---

## Step 7：文档同步

> 覆盖 Story：TECH
> 技术目标：同步架构文档，确保文档与实现一致

### 检查清单

| 情况 | 动作 |
|---|---|
| 新增 settings_service（跨模块调用链） | 新建 `docs/architecture/flows/settings-flow.md` |
| 新增 vad_service（跨模块调用链） | 新建 `docs/architecture/flows/vad-flow.md` |
| 新增 user_settings 表 | 更新 `docs/architecture/c4-container.md` |
| VAD 技术选型决策 | 新建 `docs/adr/ADR-005-silero-vad.md` |

### Flow 文档要求

**settings-flow.md** 需包含：
- 用户打开 Voice Settings → 点击选项 → POST /settings → DB 写入 → TTS 调用读取的完整 sequenceDiagram
- user_settings 表的 stateDiagram（默认值 → 用户修改 → 持久化）

**vad-flow.md** 需包含：
- 麦克风 → VAD → 有声音判断 → ASR → 发送 Alex 的 flowchart TD
- 误触计数状态机 stateDiagram-v2

### ADR-005 模板

```markdown
# ADR-005: VAD 方案选用 Silero VAD

## 状态
草稿（待 Human 确认）

## 背景
V0.3.1 新增 Hands free 模式，需要实时检测用户是否在说话。

## 决策
使用 Silero VAD。

## 理由
- 模型 ~1MB，延迟 <30ms，满足实时要求
- Python 原生支持，与现有 FastAPI + faster-whisper 栈完全兼容
- 业界标准方案（LiveKit/Pipecat 默认集成）
- 停顿阈值设为 2 秒（高于常规 1.5 秒），适配英语学习者思考停顿

## 后果
- 新增 silero-vad + torch 依赖，安装包增大约 200MB
- 需要在服务启动时预加载模型（首次启动略慢）
```

### 完成标志

```bash
ls docs/architecture/flows/settings-flow.md
ls docs/architecture/flows/vad-flow.md
grep "user_settings" docs/architecture/c4-container.md
ls docs/adr/ADR-005-silero-vad.md
```

全部确认后打印 `✅ Step 7 完成`

---

## Step 8：全链路回归 + 汇报

> 覆盖 Story：TECH
> 技术目标：所有测试全绿，向 Human 输出验收报告

### 执行

```bash
# 全量回归
pytest tests/ -v

# 仅 V0.3.1 新增测试
pytest tests/test_step1_v031.py tests/test_step2_v031.py \
       tests/test_step3_v031.py tests/test_step4_v031.py \
       tests/test_step5_v031.py tests/test_step6_v031.py -v
```

### 人工验收清单（Human 需要做的）

```
□ 打开 App，确认 Header 右侧有 ⚙️ 图标
□ 点击 ⚙️，确认 Voice Settings bottom sheet 从底部滑出
□ 切换 Voice 三个选项，确认 Alex 下一句声音不同
□ 切换 Speed 三个选项，确认 Alex 语速有明显变化
□ 切换到 Hands free，确认出现监听动效，说话自动识别
□ 切换到 Push to talk，确认原有按住录音功能正常
□ 关闭 App 重新进入，确认设置持久化
□ 说中英混合句子，确认识别正确
```

### 汇报模板

```markdown
## Speakeasy V0.3.1 完成汇报

### 测试结果
✅ 通过：N 个用例
❌ 失败：0 个用例

### 各 Step 状态
- Step 1 环境 + 数据表        ✅
- Step 2 设置服务 + API       ✅
- Step 3 TTS 集成语速音色     ✅
- Step 4 VAD 服务             ✅
- Step 5 Voice Settings UI    ✅
- Step 6 Hands Free 集成      ✅
- Step 7 文档同步             ✅
- Step 8 全链路回归           ✅

### 验收标准覆盖
- [已覆盖] 语速 3 档控制
- [已覆盖] 语速持久化
- [已覆盖] 音色 3 档选择
- [已覆盖] 音色持久化
- [已覆盖] Voice Settings bottom sheet
- [已覆盖] ⚙️ Header 入口
- [已覆盖] Hands free VAD 自动检测
- [已覆盖] 停顿 2 秒自动发送
- [已覆盖] 误触提示（不自动切换模式）
- [已覆盖] Push to talk 保持不变
- [已覆盖] 中英混合识别透传
- [已覆盖] user_settings 数据表

### 遗留问题
（如有则列出，无则填"无"）

### 待 Human 人工验收
- 音色三种声音主观体验确认
- Hands free 真实环境下误触率评估
- 语速三档主观体验确认

### 文档同步状态
- CLAUDE.md               ✅ 已更新至 V0.3.1
- C4 架构图               ✅ 新增 user_settings 表
- ADR-005（Silero VAD）   ⏳ 草稿，待 Human 确认
- BUG_LOG                 ✅ 本版本无 Bug / 见记录
- ROADMAP                 ⏳ 待 Human 将 V0.3.1 移入"已发布"
```

打印 `✅ Step 8 完成`

---

## SPEC 覆盖检查汇总

| SPEC ID | 描述 | 覆盖 Step |
|---|---|---|
| SPEC-01 | 语速 3 档控制 | Step 2 · Step 3 |
| SPEC-02 | 语速持久化 | Step 2 · Step 5 |
| SPEC-03 | 音色 3 档选择 | Step 2 · Step 3 |
| SPEC-04 | 音色持久化 | Step 2 · Step 5 |
| SPEC-05 | Voice Settings bottom sheet | Step 5 |
| SPEC-06 | ⚙️ Header 入口 | Step 5 |
| SPEC-07 | Hands free VAD 自动检测 | Step 4 · Step 6 |
| SPEC-08 | 停顿 2 秒自动发送 | Step 4 · Step 6 |
| SPEC-09 | 误触提示 | Step 4 · Step 6 |
| SPEC-10 | Push to talk 保持不变 | Step 6 |
| SPEC-11 | 中英混合识别 | Step 6 |
| SPEC-12 | user_settings 数据表 | Step 1 · Step 2 |

✅ 所有 SPEC ID 均已覆盖，无遗漏

---

*INSTRUCTIONS_V031.md — Speakeasy V0.3.1 — 生成于 2026-03-11*