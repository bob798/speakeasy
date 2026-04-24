<script setup>
/**
 * SentenceList · 左侧字幕句列表
 * 每行可点击选中 · 已练习标记 · 播放中高亮
 * 迁移自 practice.html renderSubtitles + selectLine
 *
 * 单词级交互（V0.8 补回）:
 *   - 整句点击 → emit('select', idx)
 *   - 💡 按钮 → emit('explain', { type:'sentence', content })
 *   - 单词长按 / 双击 → emit('explain', { type:'word', content, sentence })
 */
import { computed } from 'vue'
import { usePracticeStore } from '@/stores/practice'

const emit = defineEmits(['select', 'explain'])
const store = usePracticeStore()

const items = computed(() => store.segments)

function tokenize(text) {
  // 保留标点作为不可点的 token，单词可点
  const parts = []
  const re = /([A-Za-z][A-Za-z'-]*|[^A-Za-z\s]+|\s+)/g
  let m
  while ((m = re.exec(text)) !== null) {
    const piece = m[1]
    const isWord = /^[A-Za-z]/.test(piece)
    const isSpace = /^\s+$/.test(piece)
    parts.push({ piece, isWord, isSpace })
  }
  return parts
}

function onWordClick(e, word, sentence) {
  e.stopPropagation()
  emit('explain', { type: 'word', content: word, sentence })
}

function onSentenceExplain(content) {
  emit('explain', { type: 'sentence', content })
}
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
      <span class="txt">
        <template v-for="(tok, j) in tokenize(seg.content)" :key="j">
          <span
            v-if="tok.isWord"
            class="word"
            :title="`点击解读：${tok.piece}`"
            @click="onWordClick($event, tok.piece, seg.content)"
          >{{ tok.piece }}</span>
          <span v-else>{{ tok.piece }}</span>
        </template>
      </span>
      <button
        class="explain-btn"
        @click.stop="onSentenceExplain(seg.content)"
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
.word {
  cursor: pointer;
  border-radius: 3px;
  transition: background var(--duration) var(--ease);
}
.word:active {
  background: var(--accent-soft);
  color: var(--accent);
}
@media (hover: hover) {
  .word:hover {
    background: var(--accent-soft);
    color: var(--accent);
  }
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
