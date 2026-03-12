# TODO.md — Speakeasy 待办事项

---

## 待办列表

### TODO-001：下架 VAD 实时检测功能

- **优先级**：待定
- **背景**：VAD 检测效果不稳定，阈值调整后仍无法保证可靠性，用户体验差
- **方案**：
  - Hands Free 模式从 Voice Settings 中移除
  - activation 选项仅保留 Push to talk
  - 相关代码（`app/routers/vad.py`、`app/services/vad_service.py`、前端 Hands Free 逻辑）标记废弃或删除
- **影响范围**：V0.3.1 Step 4~6、`static/js/stt-provider.js` 中 VAD 相关逻辑
- **状态**：⬜ 待排期

---

*TODO.md — 最后更新 2026-03-12*
