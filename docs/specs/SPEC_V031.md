# Speakeasy V0.3.1 — 版本规格说明

> 状态：待 Claude Code 执行
> 前置条件：V0.2b 已验收完成
> 本版本目标：语音体验全面升级——音色选择、语速控制、实时免提对话

---

## 一、User Stories

### US-01 语速控制

```
作为职场英语学习者，
我希望能调整 Alex 说话的语速，
以便在听力吃力时放慢速度理解，熟悉后加快速度提升真实对话感。

验收标准：
- [ ] 3 档语速：Slow / Normal / Fast
- [ ] 对应 edge-tts rate 参数：-25% / 0% / +25%
- [ ] 设置持久化，重新进入 App 仍然生效
- [ ] 切换后下一句 Alex 回复立刻生效
- [ ] 对 Push to talk 和 Hands free 两种模式均生效
```

### US-02 音色选择

```
作为职场英语学习者，
我希望选择 Alex 的英文声音风格，
以便找到最适合自己的倾听体验，增强沉浸感。

验收标准：
- [ ] 3 个英文音色：Warm (Jenny) / Steady (Guy) / Bright (Aria)
- [ ] 对应 edge-tts voice：
      Warm   → en-US-JennyNeural
      Steady → en-US-GuyNeural
      Bright → en-US-AriaNeural
- [ ] 默认音色：Warm（首次安装）
- [ ] 切换后下一句 Alex 回复立刻生效
- [ ] 设置持久化
```

### US-03 实时语音对话

```
作为职场英语学习者，
我希望选择对话激活方式，
以便在安静环境用免提自然交流，嘈杂环境用按住说话精准控制。

验收标准：
- [ ] Header 右侧 ⚙️ 入口，点击弹出 Voice Settings bottom sheet
- [ ] Voice Settings 包含 Voice / Speed / Activation 三组设置
- [ ] 设置修改后自动保存，无需确认按钮
- [ ] Hands free 模式：VAD 自动检测，说完停顿 2 秒后自动发送
- [ ] Push to talk 模式：按住说话，松开发送（现有功能保留）
- [ ] Hands free 下连续误触超过 3 次，提示切换 Push to talk
- [ ] 支持中英混合语音输入识别
- [ ] 端到端延迟 <1 秒（VAD 检测结束 → Alex 开始回复）
- [ ] 所有设置持久化
```

---

## 二、BDD Scenarios

### Feature: 语速控制
> 覆盖 Story：US-01

```gherkin
Scenario: 用户切换语速后 Alex 下一句按新语速播放
  Given 用户在对话界面
  When  用户点击 Header ⚙️ 打开 Voice Settings
  And   在 Speed 区域选择 Slow
  Then  Slow 高亮显示
  And   Alex 下一条回复以 edge-tts rate="-25%" 播放

Scenario: 语速设置在 App 重启后仍然生效
  Given 用户上次将语速设置为 Fast
  When  用户关闭 App 重新进入对话界面
  Then  Voice Settings 中 Fast 仍为选中状态
  And   Alex 回复以 edge-tts rate="+25%" 播放

Scenario: 新用户语速默认值为 Normal
  Given 新用户首次进入 App
  When  用户打开 Voice Settings
  Then  Speed 区域 Normal 默认高亮
  And   Alex 以 edge-tts rate="0%" 播放
```

### Feature: 音色选择
> 覆盖 Story：US-02

```gherkin
Scenario: 用户切换音色后 Alex 声音立刻改变
  Given 用户在对话界面，当前音色为 Warm
  When  用户打开 Voice Settings
  And   在 Voice 区域选择 Steady
  Then  Steady 高亮
  And   Alex 下一条回复使用 en-US-GuyNeural 播放

Scenario: 新用户音色默认值为 Warm
  Given 新用户首次进入 App
  When  用户打开 Voice Settings
  Then  Voice 区域 Warm (Jenny) 默认高亮

Scenario: 音色设置持久化
  Given 用户将音色设置为 Bright
  When  用户重新进入 App
  Then  Bright 仍为选中状态
  And   Alex 使用 en-US-AriaNeural 播放
```

### Feature: Voice Settings 入口与交互
> 覆盖 Story：US-03

```gherkin
Scenario: 用户在对话界面快速打开 Voice Settings
  Given 用户在对话界面
  When  用户点击 Header 右侧 ⚙️
  Then  Voice Settings bottom sheet 从底部滑出
  And   包含 Voice / Speed / Activation 三组设置项

Scenario: 关闭 Voice Settings 回到对话
  Given Voice Settings bottom sheet 已打开
  When  用户点击 ✕ 或下滑面板
  Then  bottom sheet 收起
  And   对话内容和滚动位置保持不变

Scenario: 设置修改后自动保存无需确认
  Given Voice Settings 已打开
  When  用户切换任意设置项
  Then  设置立刻写入持久化存储
  And   界面无"保存"或"确认"按钮
```

### Feature: Hands Free 实时对话
> 覆盖 Story：US-03

```gherkin
Scenario: 切换到 Hands free 后界面出现监听状态指示
  Given 用户打开 Voice Settings
  When  在 Activation 区域选择 Hands free
  And   关闭 Voice Settings
  Then  对话界面出现持续监听状态动效（麦克风脉冲动画）
  And   无需按任何按钮即可开始说话

Scenario: VAD 检测到用户说完后自动发送
  Given 当前为 Hands free 模式
  When  用户说完一句话后停顿超过 2 秒
  Then  录音自动结束
  And   音频送入 ASR（faster-whisper）识别
  And   识别结果作为用户消息发送给 Alex

Scenario: 嘈杂环境误触超过阈值后给出提示
  Given 当前为 Hands free 模式
  When  连续 3 次检测到背景噪音触发录音（识别结果为空或少于 2 字符）
  Then  界面显示提示："环境较嘈杂，建议切换为 Push to talk"
  And   提示可手动关闭
  And   Hands free 模式继续运行不自动切换

Scenario: Push to talk 模式保持现有交互不变
  Given 用户在 Activation 中选择 Push to talk
  When  用户按住录音按钮说话并松开
  Then  行为与 V0.2b 版本完全一致
  And   VAD 服务不启动

Scenario: 中英混合语音正确识别
  Given 当前为 Hands free 模式
  When  用户说"这个 deadline 能不能 push 一下"
  Then  ASR 正确输出中英混合文本
  And   发送给 Alex 的内容完整、无乱码

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

---

## 三、前端 UI 规格

### 3.1 对话界面 Header

```
┌─────────────────────────────────────────┐
│  ←    Alex · Hands free 🟢      🔊  ⚙️  │
└─────────────────────────────────────────┘
```

- `⚙️` 始终显示在 Header 右侧
- 当前为 Hands free 时，Header 副标题显示 "Hands free 🟢"
- 当前为 Push to talk 时，副标题不显示

### 3.2 Voice Settings Bottom Sheet

```
┌─────────────────────────────────────────┐
│  ━━━━━━  (拖拽条)                        │
│                                         │
│  Voice Settings                    ✕    │
│                                         │
│  Voice                                  │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │  Warm    │ │  Steady  │ │ Bright  │ │
│  │  Jenny   │ │   Guy    │ │  Aria   │ │
│  └──────────┘ └──────────┘ └─────────┘ │
│                                         │
│  Speed                                  │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │   Slow   │ │  Normal  │ │  Fast   │ │
│  └──────────┘ └──────────┘ └─────────┘ │
│                                         │
│  Activation                             │
│  ┌─────────────────────────────────┐    │
│  │ ✅  Hands free                  │    │
│  │     Best for quiet environments │    │
│  ├─────────────────────────────────┤    │
│  │ ○   Push to talk                │    │
│  │     Hold to speak, release send │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

- 选中项：蓝色高亮背景（对标 Claude 设计语言）
- 点击任意选项立刻生效并持久化
- 支持下滑手势关闭

### 3.3 Hands Free 监听状态动效

- 对话界面麦克风区域显示低调脉冲动画
- 检测到用户说话时，切换为波形录音动效
- 识别处理中显示 loading 状态
- 噪音提示为顶部 toast，3秒后自动消失，可手动关闭

### 3.4 Hands Free 状态机

以下状态机定义了 Hands Free 模式的完整生命周期，
每条转换箭头对应一个 BDD Scenario。

```
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

---

## 四、后端接口规格

### 4.1 用户设置接口

**GET /settings/{user_id}**
```json
响应：
{
  "voice": "warm",
  "speed": "normal",
  "activation": "push_to_talk"
}
```

**POST /settings/{user_id}**
```json
请求（支持部分更新）：
{
  "voice": "steady",
  "speed": "slow",
  "activation": "hands_free"
}
响应：
{
  "success": true,
  "settings": {
    "voice": "steady",
    "speed": "slow",
    "activation": "hands_free"
  }
}
```

### 4.2 TTS 参数映射

| Speed 设置 | edge-tts rate |
|---|---|
| slow | -25% |
| normal | 0% |
| fast | +25% |

| Voice 设置 | edge-tts voice |
|---|---|
| warm | en-US-JennyNeural |
| steady | en-US-GuyNeural |
| bright | en-US-AriaNeural |

### 4.3 VAD 配置（Hands Free 专用）

- 方案：Silero VAD（pip install silero-vad）
- 停顿阈值：**2 秒**
- 误触判定：识别结果为空字符串或字符数 < 2，计为一次误触
- 连续误触上限：3 次，触发前端提示
- VAD 在 Push to talk 模式下不启动

---

## 五、数据模型规格

### 5.1 新增：user_settings 表

```sql
CREATE TABLE user_settings (
    user_id     TEXT PRIMARY KEY,
    voice       TEXT NOT NULL DEFAULT 'warm',
    speed       TEXT NOT NULL DEFAULT 'normal',
    activation  TEXT NOT NULL DEFAULT 'push_to_talk',
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

> ⚠️ 新增数据表，Claude Code 执行前需 Human 确认表结构

---

## 六、降级策略

| 场景 | 降级方案 |
|---|---|
| edge-tts 指定音色不可用 | 降级到 en-US-JennyNeural，不报错 |
| VAD 初始化失败 | Hands free 自动切换为 Push to talk，前端提示 |
| user_settings 读取失败 | 使用默认值（warm / normal / push_to_talk）|
| ASR 识别结果为空 | 不发送消息，重置录音状态，继续监听 |
| 连续误触 3 次 | 显示提示，不自动切换模式，用户自行决策 |

---

## 七、技术决策说明

### VAD 方案：Silero VAD
- 模型 ~1MB，延迟 <30ms，Python 原生，与现有栈完全兼容
- 停顿阈值设为 2 秒（高于常规 1.5 秒）——英语学习者说话有思考停顿

### ASR：本版本保留 faster-whisper，不换引擎
- 降低 V0.3.1 风险，优先交付语音体验升级
- 同步准备 FunASR SenseVoice A/B 测试数据收集，V0.3.2 决策换引擎

### 音色：edge-tts 英文音色
- 零成本接入（改一个参数），强化"和英语母语者对话"沉浸感
- 不使用中文音色，与产品核心定位一致

---

## 八、SPEC 覆盖检查

| SPEC ID | 描述 | 覆盖 Step（待 Instructions 补充）|
|---|---|---|
| SPEC-01 | 语速 3 档控制 | TBD |
| SPEC-02 | 语速持久化 | TBD |
| SPEC-03 | 音色 3 档选择 | TBD |
| SPEC-04 | 音色持久化 | TBD |
| SPEC-05 | Voice Settings bottom sheet | TBD |
| SPEC-06 | ⚙️ Header 入口 | TBD |
| SPEC-07 | Hands free VAD 自动检测 | TBD |
| SPEC-08 | 停顿 2 秒自动发送 | TBD |
| SPEC-09 | 误触提示 | TBD |
| SPEC-10 | Push to talk 保持不变 | TBD |
| SPEC-11 | 中英混合识别 | TBD |
| SPEC-12 | user_settings 数据表 | TBD |

---

*SPEC_V031.md — Speakeasy V0.3.1 — 生成于 2026-03-11*