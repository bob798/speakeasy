<script setup>
/**
 * TopBar · 翻译页顶部栏
 * - 返回链接 + 标题 + 方向切换标签 + swap 按钮 + sidebar 折叠按钮
 */

const props = defineProps({
  direction: {
    type: String,
    required: true,
  },
  sidebarOpen: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits(['swap', 'toggle-sidebar'])
</script>

<template>
  <header class="topbar">
    <RouterLink class="back" to="/">← 返回</RouterLink>

    <div class="center">
      <span class="title">翻译</span>
      <div class="direction-label">
        <span :class="{ active: direction === 'zh2en' }">中文</span>
        <button class="swap-btn" @click="emit('swap')" aria-label="切换翻译方向">⇄</button>
        <span :class="{ active: direction === 'en2zh' }">English</span>
      </div>
    </div>

    <button
      class="sidebar-toggle"
      :class="{ open: sidebarOpen }"
      @click="emit('toggle-sidebar')"
      :aria-label="sidebarOpen ? '折叠生词本' : '展开生词本'"
      :title="sidebarOpen ? '折叠生词本' : '展开生词本'"
    >
      📖
    </button>
  </header>
</template>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  padding-top: calc(var(--safe-top) + var(--space-3));
  background: var(--bg-overlay);
  backdrop-filter: saturate(180%) blur(16px);
  border-bottom: 1px solid var(--border);
  gap: var(--space-3);
}

.back {
  color: var(--text-2);
  font-size: 14px;
  white-space: nowrap;
  flex-shrink: 0;
}

.center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex: 1;
}

.title {
  font-weight: 600;
  color: var(--accent);
  font-size: 15px;
}

.direction-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 13px;
  color: var(--text-3);
}

.direction-label span {
  transition: color var(--duration) var(--ease);
}

.direction-label span.active {
  color: var(--text-1);
  font-weight: 500;
}

.swap-btn {
  padding: 2px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--text-2);
  background: var(--bg-elevated);
  transition: all var(--duration) var(--ease);
  cursor: pointer;
}

.swap-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.swap-btn:active {
  background: var(--accent-soft);
  transform: scale(0.95);
}

.sidebar-toggle {
  font-size: 18px;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  color: var(--text-2);
  background: transparent;
  transition: all var(--duration) var(--ease);
  flex-shrink: 0;
  opacity: 0.6;
}

.sidebar-toggle.open {
  opacity: 1;
  background: var(--accent-soft);
}

.sidebar-toggle:hover {
  opacity: 1;
  background: var(--accent-soft);
}

@media (max-width: 1024px) {
  .sidebar-toggle {
    display: none;
  }
}
</style>
