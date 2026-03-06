# Changelog

All notable changes to Speakeasy will be documented in this file.

---

## [Unreleased]
> 计划中的功能 / Upcoming features
- Voice input/output (Whisper + TTS)
- Cross-session memory for recurring mistakes
- Workplace / travel / interview scene modes
- Progress visualization

---

## [0.1.0] - 2025-03-06

### Added
- Core chat API (`POST /chat`) with multi-turn conversation support
- Daily tip generation (`POST /chat/summary`) — one gentle takeaway per session
- Multi-model support: Anthropic Claude / DeepSeek / Volcengine / Zhipu GLM
  - Switch providers with a single `.env` config change
- Frontend chat UI (`index.html`) — warm, judgment-free design
- Health check endpoint (`GET /health`)
- Debug status endpoint (`GET /debug/status`)
- Structured logging with request tracing (`request_id`)
- System Prompt: Alex persona — natural modeling, zero explicit correction

### Technical
- FastAPI + Python async backend
- Stateless architecture — conversation history maintained client-side
- Environment-based API key management (never committed to repo)
- OpenAI-compatible client for DeepSeek / Volcengine / Zhipu

---

*Format based on [Keep a Changelog](https://keepachangelog.com)*
