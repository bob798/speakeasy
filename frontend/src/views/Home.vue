<script setup>
// Home · 入口页
// Phase 4 次战场壳化时完整迁移旧首页入口卡片
import { RouterLink } from 'vue-router'
</script>

<template>
  <main class="home">
    <h1>Speakeasy</h1>
    <p class="tagline">AI 陪伴式私教 · 越聊越懂你</p>
    <nav class="entry">
      <RouterLink to="/chat" class="card">聊天</RouterLink>
      <RouterLink to="/practice" class="card">发音练习</RouterLink>
      <RouterLink to="/translate" class="card">翻译 · 生词本</RouterLink>
      <RouterLink to="/memory" class="card">记忆管理</RouterLink>
    </nav>
    <p class="phase-note">Phase 0 占位 · Phase 4 迁移旧入口</p>
  </main>
</template>

<style scoped>
.home {
  padding: var(--space-6) var(--space-5);
  max-width: 640px;
  margin: 0 auto;
  padding-top: calc(var(--safe-top) + var(--space-6));
  padding-bottom: calc(var(--safe-bottom) + var(--space-5));
}
h1 {
  margin: 0 0 var(--space-2);
  font-size: 32px;
  color: var(--accent);
}
.tagline {
  margin: 0 0 var(--space-6);
  color: var(--text-2);
}
.entry {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3);
}
.card {
  display: block;
  padding: var(--space-5);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-1);
  font-weight: 500;
  transition: transform var(--duration) var(--ease);
}
.card:active {
  transform: scale(0.97);
}
.phase-note {
  margin-top: var(--space-6);
  color: var(--text-3);
  font-size: 12px;
  text-align: center;
}
</style>
