<script setup>
/**
 * MobileSentenceList · 手机端句子列表 + 当前句卡（含词拆分 + 选词）
 *
 * 仅 UI 与 emit；副作用在 Practice.vue。
 */
import { computed, nextTick, watch, useTemplateRef } from 'vue'
import { usePracticeStore } from '@/stores/practice'

const props = defineProps({
  selectedWord: { type: Object, default: null }, // { word, display } | null
})
const emit = defineEmits([
  'select-sentence',  // (idx: number)
  'select-word',      // ({ word, display })
  'clear-word',
])

const store = usePracticeStore()
const segments = computed(() => store.segments)
const currentIdx = computed(() => store.currentIdx)
const listRef = useTemplateRef('listRef')

// 拆词正则 · 标点保留为文本节点
const WORD_RE = /([A-Za-z][A-Za-z'-]*)|([^A-Za-z]+)/g

function tokenize(text) {
  const out = []
  let m
  WORD_RE.lastIndex = 0
  while ((m = WORD_RE.exec(text)) !== null) {
    out.push(m[1] ? { type: 'word', text: m[1] } : { type: 'sep', text: m[2] })
  }
  return out
}

function isWordSelected(w) {
  return !!props.selectedWord && props.selectedWord.word === w.toLowerCase()
}

function onWordClick(rawWord) {
  const lower = rawWord.toLowerCase()
  if (props.selectedWord && props.selectedWord.word === lower) {
    emit('clear-word')
  } else {
    emit('select-word', { word: lower, display: rawWord })
  }
}

function onSentenceClick(idx, ev) {
  // 当前句内点词 / 选中条 时，不要触发选句
  if (ev.target.closest('.word') || ev.target.closest('.selected-bar')) return
  if (idx !== currentIdx.value) emit('select-sentence', idx)
}

// 当前句变化时滚到中央
watch(
  () => currentIdx.value,
  async () => {
    await nextTick()
    const el = listRef.value?.querySelector(`[data-idx="${currentIdx.value}"]`)
    if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' })
  },
  { immediate: true }
)
</script>

<template>
  <div ref="listRef" class="m-list">
    <div
      v-for="(seg, i) in segments"
      :key="i"
      :data-idx="i"
      class="m-seg"
      :class="{ current: i === currentIdx }"
      @click="onSentenceClick(i, $event)"
    >
      <div class="idx">{{ i + 1 }}</div>
      <div class="body">
        <div class="txt">
          <template v-if="i === currentIdx">
            <template v-for="(tok, ti) in tokenize(seg.content)" :key="ti">
              <button
                v-if="tok.type === 'word'"
                type="button"
                class="word"
                :aria-pressed="isWordSelected(tok.text)"
                :aria-label="`单词 ${tok.text}${isWordSelected(tok.text) ? '（已选）' : ''}`"
                @click.stop="onWordClick(tok.text)"
              >{{ tok.text }}</button>
              <template v-else>{{ tok.text }}</template>
            </template>
          </template>
          <template v-else>{{ seg.content }}</template>
        </div>

        <div
          v-if="i === currentIdx && selectedWord"
          class="selected-bar"
        >
          <span>⭕ 已选：<b>{{ selectedWord.display }}</b></span>
          <button
            type="button"
            class="clear"
            aria-label="清除选中词"
            @click.stop="emit('clear-word')"
          >×</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.m-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-3) var(--space-4);
  padding-bottom: var(--space-3);
  scroll-behavior: smooth;
}
.m-seg {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3);
  margin-bottom: var(--space-2);
  border-radius: var(--radius);
  cursor: pointer;
  transition: background var(--duration) var(--ease);
}
.m-seg:active { background: var(--bg-elevated); }
.m-seg .idx {
  font-size: 12px;
  color: var(--text-3);
  width: 22px;
  flex-shrink: 0;
  padding-top: 3px;
}
.m-seg .body { flex: 1; min-width: 0; }
.m-seg .txt {
  font-size: 15px;
  line-height: 1.55;
  color: var(--text-2);
  overflow-wrap: anywhere;
  word-break: break-word;
  hyphens: auto;
}
.m-seg.current {
  background: var(--bg-elevated);
  box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.06);
  border-left: 3px solid var(--accent);
  padding-left: calc(var(--space-3) - 3px);
}
.m-seg.current .idx { color: var(--accent); font-weight: 600; }
.m-seg.current .txt {
  font-size: 18px;
  font-weight: 500;
  color: var(--text-1);
}

button.word {
  display: inline-block;
  padding: 1px 2px;
  margin: 0 -1px;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  line-height: inherit;
  border-radius: 3px;
  cursor: pointer;
  transition: background 120ms var(--ease);
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}
button.word:focus { outline: none; }
button.word:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
button.word:active { background: var(--accent-soft); }
button.word[aria-pressed="true"] {
  background: var(--accent-soft);
  color: var(--accent);
  text-decoration: underline;
  text-decoration-thickness: 2px;
  text-decoration-color: var(--accent);
  text-underline-offset: 3px;
}

.selected-bar {
  margin-top: var(--space-3);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px var(--space-3);
  background: var(--accent-soft);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--accent);
}
.selected-bar .clear {
  width: 24px; height: 24px;
  display: grid; place-items: center;
  border: none;
  background: transparent;
  border-radius: 50%;
  color: var(--accent);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
}
.selected-bar .clear:focus { outline: none; }
.selected-bar .clear:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.selected-bar .clear:active { background: var(--bg-elevated); }
</style>
