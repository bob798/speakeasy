# Settings Flow — 用户设置完整调用链

> 引入版本：V0.3.1
> 覆盖 SPEC：SPEC-01 ~ SPEC-06

---

## 1. 设置保存与 TTS 集成调用链

```mermaid
sequenceDiagram
    participant U as 用户（浏览器）
    participant FE as Voice Settings UI
    participant API as /settings/{user_id}
    participant SS as settings_service
    participant DB as SQLite (user_settings)
    participant TTS as /tts
    participant TS as tts_service
    participant EDGE as edge-tts

    U->>FE: 点击 ⚙️ 打开 Voice Settings
    FE->>API: GET /settings/{user_id}
    API->>SS: get_settings(db, user_id)
    SS->>DB: SELECT user_settings WHERE user_id=?
    DB-->>SS: 返回设置（若无则创建默认值）
    SS-->>API: UserSettings 对象
    API-->>FE: {voice, speed, activation}
    FE->>FE: renderSettings()（高亮当前选项）

    U->>FE: 点击选项（如 Speed: Slow）
    FE->>API: POST /settings/{user_id} {speed: "slow"}
    API->>SS: update_settings(db, user_id, {speed: "slow"})
    SS->>DB: UPDATE user_settings SET speed="slow"
    DB-->>SS: 写入成功
    SS-->>API: 更新后的 UserSettings
    API-->>FE: {success: true, settings: {...}}
    FE->>FE: renderSettings()（更新 UI 选中态）

    Note over U,EDGE: 下一次 Alex 发话时
    U->>TTS: POST /tts {text, user_id}
    TTS->>SS: get_tts_params(db, user_id)
    SS->>DB: SELECT user_settings
    DB-->>SS: {voice: "warm", speed: "slow"}
    SS-->>TTS: {voice: "en-US-JennyNeural", rate: "-25%"}
    TTS->>TS: text_to_speech_with_params(text, voice, rate)
    TS->>EDGE: Communicate(text, "en-US-JennyNeural", rate="-25%")
    EDGE-->>TS: 音频数据
    TS-->>TTS: bytes
    TTS-->>U: audio/mpeg（按用户设置的语速播放）
```

---

## 2. user_settings 状态图

```mermaid
stateDiagram-v2
    [*] --> DefaultValues: 用户首次访问（自动创建）

    DefaultValues: 默认值\nvoice=warm\nspeed=normal\nactivation=push_to_talk

    DefaultValues --> VoiceChanged: 用户选择音色
    DefaultValues --> SpeedChanged: 用户选择语速
    DefaultValues --> ActivationChanged: 用户切换激活方式

    VoiceChanged --> Persisted: DB 写入
    SpeedChanged --> Persisted: DB 写入
    ActivationChanged --> Persisted: DB 写入

    Persisted --> DefaultValues: 用户重置（未实现）
    Persisted --> VoiceChanged: 再次修改音色
    Persisted --> SpeedChanged: 再次修改语速
    Persisted --> ActivationChanged: 再次切换方式

    note right of Persisted
        关闭 App 重开后读取持久化值
        所有设置跨 session 生效
    end note
```

---

## 3. 映射关系

| 用户选项 | voice_key | edge-tts voice | rate |
|---|---|---|---|
| Warm | warm | en-US-JennyNeural | — |
| Steady | steady | en-US-GuyNeural | — |
| Bright | bright | en-US-AriaNeural | — |
| Slow | — | — | -25% |
| Normal | — | — | +0% |
| Fast | — | — | +25% |
