<script setup>
/**
 * TranslateSidebar · 右侧生词本侧边栏
 * PR1 placeholder — 生词本 FSRS 功能在 PR3 中实现
 */

defineProps({
  open: {
    type: Boolean,
    default: true,
  },
})
</script>

<template>
  <aside v-if="open" class="sidebar">
    <div class="sidebar-header">
      <span class="sidebar-title">📖 生词本</span>
    </div>
    <div class="sidebar-body">
      <p class="placeholder-text">生词本功能将在后续版本中升级</p>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
  min-height: 320px;
}

.sidebar-header {
  display: flex;
  align-items: center;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}

.sidebar-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-1);
}

.sidebar-body {
  flex: 1;
  padding: var(--space-4);
  display: flex;
  align-items: center;
  justify-content: center;
}

.placeholder-text {
  font-size: 13px;
  color: var(--text-3);
  text-align: center;
  line-height: 1.6;
}
</style>
