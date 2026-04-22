# Open Questions

## v04-pronunciation-practice — 2026-04-16

- [ ] B站字幕提取是否需要 Cookie/登录态？— 部分视频的 CC 字幕可能需要登录才能获取 subtitle_url，需要实际测试确认
- [ ] 发音卡是否需要在 memory.html 中展示？— 当前计划只在 practice.html 管理，但用户可能期望在记忆管理页统一查看
- [ ] 单词标记粒度：点击单词时是否自动带上所在句子作为 context？— 计划中假设是，但需确认这是否符合用户期望
- [ ] 手动粘贴的文本分割策略：按换行 vs 按句号 vs 按固定长度？— 影响练习体验，建议按换行 + 句号双重分割
- [ ] SubtitleSource 缓存表是否必要？— 如果用户不会重复提取同一视频，可以省略此表简化实现

## translate-mvp — 2026-04-17
- [ ] 翻译 Prompt 是否需要区分"词/短语"与"句子"两种模式？ — 影响翻译质量和用户体验，MVP 先统一处理，后续可按用户反馈拆分
- [ ] 生词本是否需要导出功能（CSV / Anki）？ — spec 未提及，MVP 不做，但后续用户可能需要
- [ ] translate.html 的 header 导航链接顺序最终确认：🌐翻译 在 🎙️练习 和 🧠记忆 之前是否符合产品优先级排序？ — spec 建议此顺序，待 Human 确认
- [x] memory.html header 是否需要加 🌐 翻译链接？ — **V2 决定：本轮不动**。memory.html 当前为 top-bar 布局，无 header-right，统一改造留作 Follow-up
- [ ] AC5 朗读端点：translate.html 前端调用现有 `POST /tts` 接口（与主聊天页一致），而非 `/practice/tts`（后者为多源 TTS 含 original 音频段） — 已在 Step 4 验证命令中明确为 /tts
