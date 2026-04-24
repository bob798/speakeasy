<script setup>
// Review · 次战场 (Phase 4 壳化)
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <main class="placeholder">
    <h2>Review · 占位</h2>
    <p>Session ID: {{ route.params.sessionId || '(无)' }}</p>
    <p class="note">Phase 4 壳化 · 读 /review/:sessionId API</p>
  </main>
</template>

<style scoped>
.placeholder {
  padding: var(--space-6);
  max-width: 640px;
  margin: 0 auto;
}
.note {
  color: var(--text-3);
  font-size: 13px;
}
</style>
