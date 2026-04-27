<script setup>
/**
 * SentenceList · V0.9.3 修
 *   - 移除单词级点击（与选中行点击冲突）
 *   - 单击整句 = select
 *   - 💡 按钮 = sentence explain
 *   - 单词解读入口搬到 PracticePlayer
 */
import { computed, watch, nextTick, useTemplateRef } from 'vue'
import { usePracticeStore } from '@/stores/practice'

const emit = defineEmits(['select', 'explain'])
const store = usePracticeStore()

const items = computed(() => store.segments)
const listRef = useTemplateRef('listRef')

// 当前句变化时滚到可见位置（抽屉打开 / 跳句 / 进入页面）
watch(
  () => store.currentIdx,
  async () => {
    await nextTick()
    const el = listRef.value?.querySelector('.item.active')
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
  },
  { immediate: true }
)
</script>

<template>
  <ul ref="listRef" class="sentences">
    <li
      v-for="(seg, i) in items"
      :key="i"
      class="item"
      :class="{
        active: store.currentIdx === i,
        practiced: store.practicedIndices.has(i),
      }"
      @click="emit('select', i)"
    >
      <span class="idx">{{ i + 1 }}.</span>
      <span class="txt">{{ seg.content }}</span>
      <button
        class="explain-btn"
        @click.stop="emit('explain', { type: 'sentence', content: seg.content })"
        aria-label="解读整句"
        title="解读整句"
      >
        💡
      </button>
    </li>
    <li v-if="!items.length" class="empty">先导入字幕</li>
  </ul>
</template>

<style scoped>
.sentences {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  height: 100%;
  background: var(--bg-elevated);
}
.item {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  transition: background var(--duration) var(--ease);
  user-select: none;
}
.item:active {
  background: var(--bg);
}
.item.active {
  background: var(--accent-soft);
  border-left: 3px solid var(--accent);
  padding-left: calc(var(--space-4) - 3px);
}
.item.practiced {
  opacity: 0.6;
  position: relative;
}
.item.practiced::after {
  content: '✓';
  position: absolute;
  top: var(--space-2);
  right: var(--space-3);
  color: var(--accent);
  font-size: 12px;
}
.idx {
  color: var(--text-3);
  font-size: 12px;
  flex-shrink: 0;
  padding-top: 2px;
}
.txt {
  flex: 1;
  font-size: 14px;
  line-height: 1.55;
  color: var(--text-1);
  word-break: break-word;
}
.explain-btn {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 16px;
  background: transparent;
  transition: background var(--duration) var(--ease), transform var(--duration) var(--ease);
}
.explain-btn:active {
  background: var(--accent);
  transform: scale(0.9);
}
.item.active .explain-btn {
  background: var(--bg-elevated);
}
@media (hover: hover) {
  .explain-btn:hover {
    background: var(--accent-soft);
  }
}
.empty {
  padding: var(--space-6);
  text-align: center;
  color: var(--text-3);
  font-size: 13px;
}
</style>
