<script setup>
/**
 * SentenceList · 左侧字幕句列表
 * 每行可点击选中 · 已练习标记 · 播放中高亮
 * 迁移自 practice.html renderSubtitles + selectLine
 */
import { computed } from 'vue'
import { usePracticeStore } from '@/stores/practice'

const emit = defineEmits(['select', 'explain'])
const store = usePracticeStore()

const items = computed(() => store.segments)
</script>

<template>
  <ul class="sentences">
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
        @click.stop="emit('explain', seg.content)"
        aria-label="解读"
        title="解读"
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
}
.item:active,
.item.active {
  background: var(--accent-soft);
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
  line-height: 1.5;
  color: var(--text-1);
  word-break: break-word;
}
.explain-btn {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-size: 14px;
  opacity: 0;
  transition: opacity var(--duration) var(--ease);
}
.item.active .explain-btn,
.item:active .explain-btn {
  opacity: 1;
}
@media (hover: hover) {
  .item:hover .explain-btn {
    opacity: 1;
  }
}
.empty {
  padding: var(--space-6);
  text-align: center;
  color: var(--text-3);
  font-size: 13px;
}
</style>
