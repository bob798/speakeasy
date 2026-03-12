# ADR-006: VAD 方案选用 Silero VAD

## 状态
草稿（待 Human 确认）

## 背景
V0.3.1 新增 Hands free 模式，需要实时检测用户是否在说话（Voice Activity Detection）。
需求：低延迟、纯 Python、与现有 FastAPI 栈兼容、在英语学习场景中适配说话停顿。

## 决策
使用 Silero VAD（silero-vad 6.x + torch 2.x）。

## 理由
- 模型约 1MB，推理延迟 <30ms，满足实时处理要求
- Python 原生支持，与现有 FastAPI + faster-whisper 技术栈完全兼容
- 业界标准方案（LiveKit、Pipecat 默认集成）
- WebSocket 接口天然支持流式音频处理
- 停顿阈值设为 2 秒（高于常规 1.5 秒），适配英语学习者在组织语言时的思考停顿

## 后果
- 新增 silero-vad + torch 依赖，安装包增大约 200MB
- 需要在服务启动时预加载模型（首次启动略慢约 2~3 秒）
- numpy 版本兼容问题（torch 2.2.2 与 numpy 2.x 存在 API 差异警告，不影响功能）
- VAD WebSocket 仅处理语音检测信号；实际麦克风录音与 ASR 调用仍由前端控制
