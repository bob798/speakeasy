# VAD Flow — 实时语音检测流程

> 引入版本：V0.3.1
> 覆盖 SPEC：SPEC-07 ~ SPEC-11

---

## 1. Hands Free 完整流程

```mermaid
flowchart TD
    A[用户切换到 Hands Free] --> B[前端建立 WebSocket /ws/vad/user_id]
    B --> C[VADService 初始化 Silero VAD 模型]
    C --> D{麦克风持续监听}

    D --> E[接收 40ms 音频块]
    E --> F{VAD 判断\nconfidence > 0.5?}

    F -- 是: 检测到语音 --> G[is_recording = True\n发送 speech_start 事件]
    G --> H[前端显示录音动效]
    H --> D

    F -- 否且未录音 --> D

    F -- 否且录音中 --> I[silence_frames ++]
    I --> J{silence_frames >= 50?\n即 2 秒静音}

    J -- 否 --> D

    J -- 是: 说完了 --> K[发送 speech_end 事件\naudio_length 信息]
    K --> L[前端停止录音\n将音频发给 ASR]
    L --> M{ASR 识别结果\n长度 >= 2 字符?}

    M -- 是: 有效输入 --> N[misfireCount = 0\n调用 sendMessage]
    N --> O[Alex 回复]
    O --> D

    M -- 否: 误触 --> P[misfireCount ++]
    P --> Q{misfireCount >= 3?}

    Q -- 否 --> D

    Q -- 是: 达到阈值 --> R[显示 Toast 提示\n建议切换 Push to talk]
    R --> D
```

---

## 2. 误触计数状态机

```mermaid
stateDiagram-v2
    [*] --> Idle: 初始化

    Idle: misfire_count = 0

    Idle --> Counting1: 第1次误触
    Counting1: misfire_count = 1

    Counting1 --> Counting2: 第2次误触
    Counting2: misfire_count = 2

    Counting2 --> ThresholdReached: 第3次误触
    ThresholdReached: misfire_count = 3\n→ 触发 Toast 提示

    ThresholdReached --> ThresholdReached: 继续误触\n（仍显示 Toast）

    Counting1 --> Idle: 有效输入\n(reset)
    Counting2 --> Idle: 有效输入\n(reset)
    ThresholdReached --> Idle: 有效输入\n(reset)

    note right of ThresholdReached
        误触提示：仅 Toast 弹出
        不自动切换 activation 模式
        用户自行决定是否切换
    end note
```

---

## 3. 关键参数

| 参数 | 值 | 说明 |
|---|---|---|
| SAMPLE_RATE | 16000 Hz | Silero VAD 要求 |
| SILENCE_THRESHOLD | 2.0 秒 | 高于常规 1.5 秒，适配英语学习者思考停顿 |
| FRAMES_PER_SECOND | 25 | 每帧 40ms |
| SILENCE_FRAMES | 50 | 2s × 25fps |
| VAD confidence 阈值 | 0.5 | 默认值，平衡误触与漏检 |
| MIN_TRANSCRIPT_LENGTH | 2 字符 | 少于此长度视为误触 |
| MISFIRE_MAX_COUNT | 3 次 | 达到后显示切换提示 |
