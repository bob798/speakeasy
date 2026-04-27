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

## V0.8 候选（已迁移到 GitHub Issues）

> 详细方案与讨论以 GitHub Issue 为准，本文件仅留索引。

- [#6](https://github.com/bob798/speakeasy/issues/6) — 连读解释通俗化 + 模式知识库
- [#7](https://github.com/bob798/speakeasy/issues/7) — 追问入口下沉到解读弹窗底部
- [#8](https://github.com/bob798/speakeasy/issues/8) — 历史缓存解读的刷新机制

---

### TODO 杂项（未排期）

1. 导出聊天内容，比如导出我的测试内容，让 ai 修正
2. 定义聊天标题

*TODO.md — 最后更新 2026-04-26*
