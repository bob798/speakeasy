# Practice 手机端重设计 · 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Practice 页手机端（<768px）从「难找按钮的长滚动列表」改造为「单手大拇指可达 + 教练状态条引导」的练习页。桌面端不变。

**Architecture:** Practice.vue 容器按 `isMobile` 切两套子组件树。手机端：`MobileSentenceList`（列表 + 当前句卡 + 选词）+ `MobileActionDock`（coach bar + 4 按钮）+ ⚙ 底部 sheet。`selectedWord` 等瞬时 UI 状态留在 `Practice.vue` 本地 ref（不入 Pinia），避免跨布局污染。Coach bar 文案由纯派生 composable `useCoachBar` 推导。

**Tech Stack:** Vue 3 (`<script setup>`) · Pinia (复用现有 `usePracticeStore`) · vitest + @vue/test-utils (仅给纯派生 composable 写单测) · 设计 tokens (`frontend/src/styles/tokens.css`)

**Spec:** `docs/superpowers/specs/2026-05-12-practice-mobile-redesign.md`
**Prototype:** `mockups/practice-mobile-v2.html`
**Branch:** `feat/practice-mobile-redesign`（已存在）

---

## File Structure

```
frontend/src/
├── composables/
│   ├── useBreakpoint.js                    [NEW] 通用 isMobile reactive (matchMedia)
│   ├── useCoachBar.js                      [NEW] 纯派生：state → coach copy
│   └── __tests__/
│       └── useCoachBar.spec.js             [NEW] vitest 单测
├── components/practice/
│   ├── MobileSentenceList.vue              [NEW] 列表 + 当前句卡（含词拆分 + 选词 + 选中条）
│   ├── MobileActionDock.vue                [NEW] coach bar + 4 按钮 + 主/副标签状态机
│   ├── PracticePlayer.vue                  [UNCHANGED] 桌面端用
│   ├── SentenceList.vue                    [UNCHANGED] 桌面端用
│   └── SubtitleImport.vue                  [UNCHANGED]
└── views/
    └── Practice.vue                        [MODIFY] 按 isMobile 切换子树 + ⚙ sheet + 首次 FSRS toast + 状态机
```

**职责边界：**
- `MobileSentenceList`：纯 UI，从 store 拿 `segments / currentIdx`，从 props 拿 `selectedWord`。emit `select-sentence` / `select-word` / `clear-word`。
- `MobileActionDock`：纯 UI，从 props 拿状态（`selectedWord, recording, isPlayingTTS, hasRecording, hasPlayedBack, currentIdx, totalSegments, practicedCount`）。emit `explain` / `speak` / `toggle-record` / `playback` / `open-settings`。
- `Practice.vue`：所有副作用（TTS、录音、API、storage、状态机原语）集中在这里。

---

## Phase 1 · Foundation 组件依赖

### Task 1: `useBreakpoint` composable

**Files:**
- Create: `frontend/src/composables/useBreakpoint.js`

- [ ] **Step 1: 创建 composable**

```js
// frontend/src/composables/useBreakpoint.js
import { ref, onMounted, onUnmounted } from 'vue'

/**
 * 响应式 isMobile · 基于 matchMedia('(max-width: 767px)')
 * 与 spec 的 < 768px 断点对齐
 */
export function useBreakpoint() {
  const isMobile = ref(false)
  let mq = null
  const onChange = (e) => { isMobile.value = e.matches }

  onMounted(() => {
    mq = window.matchMedia('(max-width: 767px)')
    isMobile.value = mq.matches
    mq.addEventListener('change', onChange)
  })
  onUnmounted(() => {
    if (mq) mq.removeEventListener('change', onChange)
  })

  return { isMobile }
}
```

- [ ] **Step 2: 手动 sanity check**

跑 `npm run dev`（在 `frontend/` 目录），打开 Practice 页（这步还没接入，但确保 import 不报 lint 错）。

Run: `cd frontend && npm run lint -- src/composables/useBreakpoint.js`
Expected: 无 error

- [ ] **Step 3: Commit**

```bash
git add frontend/src/composables/useBreakpoint.js
git commit -m "feat(practice): add useBreakpoint composable"
```

---

### Task 2: `useCoachBar` composable + 单测

**Files:**
- Create: `frontend/src/composables/useCoachBar.js`
- Create: `frontend/src/composables/__tests__/useCoachBar.spec.js`

- [ ] **Step 1: 先写测试（TDD）**

```js
// frontend/src/composables/__tests__/useCoachBar.spec.js
import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { useCoachBar } from '../useCoachBar'

function setup(overrides = {}) {
  const state = {
    selectedWord:  ref(null),
    recording:     ref(false),
    isPlayingTTS:  ref(false),
    hasRecording:  ref(false),
    hasPlayedBack: ref(false),
    currentIdx:    ref(0),
    totalSegments: ref(9),
    practicedCount: ref(0),
    ...overrides,
  }
  return { state, ...useCoachBar(state) }
}

describe('useCoachBar', () => {
  it('空闲：先听我读一次', () => {
    const { coachCopy, coachProgress } = setup()
    expect(coachCopy.value).toBe('先听我读一次')
    expect(coachProgress.value).toBe('第 1/9 句')
  })

  it('选词后：解读 "<word>"', () => {
    const { coachCopy } = setup({ selectedWord: ref({ word: 'schedule', display: 'schedule' }) })
    expect(coachCopy.value).toBe('解读 "schedule"')
  })

  it('TTS 播放中：听着…', () => {
    const { coachCopy } = setup({ isPlayingTTS: ref(true) })
    expect(coachCopy.value).toBe('听着…')
  })

  it('录音中：录音中 · 念完点停止', () => {
    const { coachCopy, coachClass } = setup({ recording: ref(true) })
    expect(coachCopy.value).toBe('录音中 · 念完点停止')
    expect(coachClass.value).toBe('recording')
  })

  it('录完未回放：收到了 · 回放听听自己', () => {
    const { coachCopy } = setup({ hasRecording: ref(true) })
    expect(coachCopy.value).toBe('收到了 · 回放听听自己')
  })

  it('录完已回放：比一比，节奏对齐了吗', () => {
    const { coachCopy } = setup({
      hasRecording: ref(true),
      hasPlayedBack: ref(true),
    })
    expect(coachCopy.value).toBe('比一比，节奏对齐了吗')
  })

  it('已完成 N 句时进度带 · 已完成 N', () => {
    const { coachProgress } = setup({
      currentIdx: ref(2),
      practicedCount: ref(3),
    })
    expect(coachProgress.value).toBe('第 3/9 句 · 已完成 3')
  })

  it('状态优先级：录音 > TTS > 选词 > 录完 > 空闲', () => {
    // 录音中即使有 selectedWord 和 hasRecording 也走录音文案
    const { coachCopy } = setup({
      selectedWord: ref({ word: 'x', display: 'x' }),
      hasRecording: ref(true),
      recording: ref(true),
    })
    expect(coachCopy.value).toBe('录音中 · 念完点停止')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npm test -- useCoachBar`
Expected: FAIL — `Cannot find module '../useCoachBar'`

- [ ] **Step 3: 实现 composable**

```js
// frontend/src/composables/useCoachBar.js
import { computed } from 'vue'

/**
 * Coach bar 状态机 · 纯派生 · 不持有 state
 *
 * 状态优先级：recording > isPlayingTTS > selectedWord > hasPlayedBack > hasRecording > idle
 *
 * @param {{
 *   selectedWord:   import('vue').Ref<{word:string, display:string}|null>,
 *   recording:      import('vue').Ref<boolean>,
 *   isPlayingTTS:   import('vue').Ref<boolean>,
 *   hasRecording:   import('vue').Ref<boolean>,
 *   hasPlayedBack:  import('vue').Ref<boolean>,
 *   currentIdx:     import('vue').Ref<number>,
 *   totalSegments:  import('vue').Ref<number>,
 *   practicedCount: import('vue').Ref<number>,
 * }} state
 */
export function useCoachBar(state) {
  const coachCopy = computed(() => {
    if (state.recording.value) return '录音中 · 念完点停止'
    if (state.isPlayingTTS.value) return '听着…'
    if (state.selectedWord.value) return `解读 "${state.selectedWord.value.display}"`
    if (state.hasRecording.value && state.hasPlayedBack.value) return '比一比，节奏对齐了吗'
    if (state.hasRecording.value) return '收到了 · 回放听听自己'
    return '先听我读一次'
  })

  const coachClass = computed(() => (state.recording.value ? 'recording' : ''))

  const coachProgress = computed(() => {
    const base = `第 ${state.currentIdx.value + 1}/${state.totalSegments.value} 句`
    return state.practicedCount.value > 0
      ? `${base} · 已完成 ${state.practicedCount.value}`
      : base
  })

  return { coachCopy, coachClass, coachProgress }
}
```

- [ ] **Step 4: 跑测试确认全过**

Run: `cd frontend && npm test -- useCoachBar`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useCoachBar.js \
        frontend/src/composables/__tests__/useCoachBar.spec.js
git commit -m "feat(practice): add useCoachBar composable + tests"
```

---

## Phase 2 · MobileActionDock 组件

### Task 3: 创建 `MobileActionDock.vue` 骨架

**Files:**
- Create: `frontend/src/components/practice/MobileActionDock.vue`

- [ ] **Step 1: 创建组件文件**

```vue
<!-- frontend/src/components/practice/MobileActionDock.vue -->
<script setup>
/**
 * MobileActionDock · 手机端底部 action dock
 *
 * 仅 UI 与 props/emit；所有副作用在 Practice.vue。
 * 设计文档：docs/superpowers/specs/2026-05-12-practice-mobile-redesign.md
 *
 * 该 dock 是可复用容器模式：未来 Translate / Polish 出现高频底部动作可沿用。
 */
import { computed } from 'vue'
import { useCoachBar } from '@/composables/useCoachBar'

const props = defineProps({
  selectedWord:   { type: Object, default: null },
  recording:      { type: Boolean, default: false },
  isPlayingTTS:   { type: Boolean, default: false },
  hasRecording:   { type: Boolean, default: false },
  hasPlayedBack:  { type: Boolean, default: false },
  currentIdx:     { type: Number, default: 0 },
  totalSegments:  { type: Number, default: 0 },
  practicedCount: { type: Number, default: 0 },
})

const emit = defineEmits(['explain', 'speak', 'toggle-record', 'playback'])

// 把 props 转 refs 喂 useCoachBar
const state = {
  selectedWord:   computed(() => props.selectedWord),
  recording:      computed(() => props.recording),
  isPlayingTTS:   computed(() => props.isPlayingTTS),
  hasRecording:   computed(() => props.hasRecording),
  hasPlayedBack:  computed(() => props.hasPlayedBack),
  currentIdx:     computed(() => props.currentIdx),
  totalSegments:  computed(() => props.totalSegments),
  practicedCount: computed(() => props.practicedCount),
}
const { coachCopy, coachClass, coachProgress } = useCoachBar(state)

// 主标签：句模式 vs 词模式
const explainLabel = computed(() => (props.selectedWord ? '解释单词' : '解释整句'))
const speakLabel   = computed(() => (props.selectedWord ? '发音单词' : '发音整句'))
const subWord      = computed(() => props.selectedWord?.display || '')

const explainAria = computed(() =>
  props.selectedWord
    ? `解释 · 当前作用对象 ${props.selectedWord.display}`
    : '解释 · 整句'
)
const speakAria = computed(() =>
  props.selectedWord
    ? `发音 · 当前作用对象 ${props.selectedWord.display}`
    : '发音 · 整句'
)

const playbackDisabled = computed(() => !props.hasRecording)
</script>

<template>
  <div class="dock">
    <!-- coach bar -->
    <div class="coach-bar" :class="coachClass" role="status" aria-live="polite">
      <span class="ico" aria-hidden="true">🎯</span>
      <span class="progress">{{ coachProgress }}</span>
      <span class="copy">{{ coachCopy }}</span>
    </div>

    <div class="dock-row">
      <button
        class="dock-btn primary"
        :aria-label="explainAria"
        @click="emit('explain')"
      >
        <span class="ico" aria-hidden="true">💡</span>
        <span class="label">{{ explainLabel }}</span>
        <span v-if="subWord" class="sub">{{ subWord }}</span>
      </button>
      <button
        class="dock-btn primary"
        :aria-label="speakAria"
        @click="emit('speak')"
      >
        <span class="ico" aria-hidden="true">🔊</span>
        <span class="label">{{ speakLabel }}</span>
        <span v-if="subWord" class="sub">{{ subWord }}</span>
      </button>
    </div>
    <div class="dock-row">
      <button
        class="dock-btn record"
        :class="{ recording }"
        :aria-pressed="recording"
        :aria-label="recording ? '停止录音' : '开始录音'"
        @click="emit('toggle-record')"
      >
        <span class="ico" aria-hidden="true">{{ recording ? '⏹' : '🎤' }}</span>
        <span class="label">{{ recording ? '停止' : '录音' }}</span>
        <span class="sub">
          {{ recording ? '录音中…' : (hasRecording ? '重录' : '开始录') }}
        </span>
      </button>
      <button
        class="dock-btn"
        :aria-disabled="playbackDisabled"
        :aria-label="playbackDisabled ? '回放，先录一段' : '回放录音'"
        @click="emit('playback')"
      >
        <span class="ico" aria-hidden="true">▶</span>
        <span class="label">回放</span>
        <span class="sub">{{ playbackDisabled ? '无录音' : '听自己' }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.dock {
  position: sticky;
  bottom: 0;
  background: var(--bg-overlay);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-top: 1px solid var(--border);
  padding: var(--space-2) var(--space-3);
  padding-bottom: calc(var(--space-2) + var(--safe-bottom));
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  z-index: 5;
}
.coach-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px var(--space-3);
  background: var(--bg-elevated);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-2);
  line-height: 1.35;
}
.coach-bar .ico { font-size: 14px; flex-shrink: 0; }
.coach-bar .progress { color: var(--text-3); margin-right: 2px; flex-shrink: 0; }
.coach-bar .copy { flex: 1; min-width: 0; }
.coach-bar.recording { color: #c6463a; }

.dock-row { display: flex; gap: var(--space-2); }
.dock-btn {
  flex: 1;
  min-height: 56px;
  border-radius: var(--radius);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  font-family: inherit;
  color: var(--text-1);
  cursor: pointer;
  transition: all 120ms var(--ease);
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}
.dock-btn:active { transform: scale(0.96); background: var(--bg); }
.dock-btn:focus { outline: none; }
.dock-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.dock-btn .ico { font-size: 20px; line-height: 1; }
.dock-btn .label { font-size: 13px; font-weight: 500; }
.dock-btn .sub { font-size: 10px; color: var(--text-3); }
.dock-btn.primary { background: var(--accent); border-color: var(--accent); color: var(--text-inverse); }
.dock-btn.primary .sub { color: rgba(255,255,255,0.75); }
.dock-btn.record.recording {
  background: #c6463a; border-color: #c6463a; color: #fff;
  animation: rec-pulse 1s infinite;
}
.dock-btn[aria-disabled="true"] { opacity: 0.45; }
@keyframes rec-pulse {
  0%,100% { box-shadow: 0 0 0 0 rgba(198,70,58,0.4); }
  50%    { box-shadow: 0 0 0 8px rgba(198,70,58,0); }
}

@media (orientation: landscape) and (max-height: 500px) {
  .dock { padding-bottom: var(--space-2); }
  .dock-row { gap: var(--space-1); }
  .dock-btn { min-height: 44px; }
  .coach-bar { display: none; }
}
</style>
```

- [ ] **Step 2: Lint check**

Run: `cd frontend && npm run lint -- src/components/practice/MobileActionDock.vue`
Expected: 无 error

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/practice/MobileActionDock.vue
git commit -m "feat(practice): add MobileActionDock component"
```

---

## Phase 3 · MobileSentenceList 组件

### Task 4: 创建 `MobileSentenceList.vue`

**Files:**
- Create: `frontend/src/components/practice/MobileSentenceList.vue`

- [ ] **Step 1: 创建组件**

```vue
<!-- frontend/src/components/practice/MobileSentenceList.vue -->
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
```

- [ ] **Step 2: Lint check**

Run: `cd frontend && npm run lint -- src/components/practice/MobileSentenceList.vue`
Expected: 无 error

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/practice/MobileSentenceList.vue
git commit -m "feat(practice): add MobileSentenceList component"
```

---

## Phase 4 · Practice.vue 整合 + 状态机

### Task 5: 改 `Practice.vue` 接入 mobile 子树

**Files:**
- Modify: `frontend/src/views/Practice.vue`

这步改动较大，把 Phase 1-3 的组件全部接进 Practice.vue 并加状态机。

- [ ] **Step 1: 改 `<script setup>` 顶部 imports + 状态**

定位 `Practice.vue` 现有 imports 区（约第 11-21 行），把整个 script setup 替换为：

```vue
<script setup>
/**
 * Practice · V0.12 手机端重设计
 *
 * 桌面端 (>= 768px) 仍走 SentenceList + PracticePlayer（不动）。
 * 手机端 (< 768px) 走 MobileSentenceList + MobileActionDock，
 * 所有副作用（TTS / 录音 / API / 状态机）集中在本文件。
 */
import { ref, computed, watch, onActivated, onDeactivated, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { usePracticeStore } from '@/stores/practice'
import { usePractice } from '@/composables/usePractice'
import { useRecorder } from '@/composables/useRecorder'
import { useAuthFetch, getErrorMessage } from '@/composables/useAuthFetch'
import { useScrollLock } from '@/composables/useScrollLock'
import { useBreakpoint } from '@/composables/useBreakpoint'

import SubtitleImport from '@/components/practice/SubtitleImport.vue'
import SentenceList from '@/components/practice/SentenceList.vue'
import PracticePlayer from '@/components/practice/PracticePlayer.vue'
import MobileSentenceList from '@/components/practice/MobileSentenceList.vue'
import MobileActionDock from '@/components/practice/MobileActionDock.vue'
import ExplanationModal from '@/components/ExplanationModal.vue'

defineOptions({ name: 'Practice' })

const router = useRouter()
const store = usePracticeStore()
const { createCards, ttsBlob } = usePractice()
const { authFetch } = useAuthFetch()
const recorder = useRecorder()
const { isMobile } = useBreakpoint()

// ---- 通用 / 桌面端原有逻辑 ----
const explainOpen = ref(false)
const explainTarget = ref(null)
const toast = ref({ show: false, text: '', type: 'info' })
const listDrawerOpen = ref(false)  // 桌面端不用，但保留兼容
useScrollLock(listDrawerOpen)

const hasSource = computed(
  () => !!store.currentSource && (store.segments?.length || 0) > 0
)
const isBbcSource = computed(() => {
  const s = store.currentSource
  return !!s && (s.source_type === 'bbc_eaw' || s.type === 'bbc_eaw')
})

function showToast(text, type = 'info', duration = 2500) {
  toast.value = { show: true, text, type }
  setTimeout(() => (toast.value.show = false), duration)
}

// ---- 手机端本地状态（不入 Pinia） ----
const selectedWord = ref(null)         // { word, display } | null
const sheetOpen = ref(false)
const recordingSegIdx = ref(null)
const hasPlayedBack = ref(false)
const isPlayingTTS = ref(false)
const practicedCount = ref(0)
let _ttsAudio = null
let _ttsUrl = null
let _lastRequestKey = null

useScrollLock(sheetOpen)

const FSRS_NOTICE_KEY = 'v2:practice.fsrs_notice_seen'

// 跨断点（resize 跨 768px）时清状态防泄漏
watch(isMobile, () => {
  selectedWord.value = null
  sheetOpen.value = false
  _releaseTTS()
  if (recorder.recording.value) recorder.stop()
  recordingSegIdx.value = null
})

// 首次进入弹一次 FSRS toast（仅手机端弹）
watch(
  [isMobile, hasSource],
  ([m, has]) => {
    if (!m || !has) return
    try {
      if (!localStorage.getItem(FSRS_NOTICE_KEY)) {
        setTimeout(() => {
          showToast('ℹ︎ 手机端暂不记录复习评分，仍可正常练习', 'info', 4000)
          localStorage.setItem(FSRS_NOTICE_KEY, '1')
        }, 400)
      }
    } catch { /* ignore */ }
  },
  { immediate: true }
)

// ---- 复用桌面端 onImported / onSelect / onExplain / onRated / onNewImport ----
// (保持原 Practice.vue 现有实现；下面只列差异点)

function gotoBbcReview() {
  const slug = store.currentSource?.slug || store.currentSource?.id
  if (!slug) return
  router.push({ name: 'bbc-review', params: { slug } })
}

async function onImported(data) {
  if (!data.id && data.source_id) data.id = data.source_id
  store.loadSource(data)
  const segs = (data.segments || []).map((seg, i) => ({
    text: seg.content,
    context: JSON.stringify({ segIdx: i, from: seg.from, to: seg.to }),
    segIdx: i,
  }))
  try {
    const existingResp = await fetch('/practice/cards?limit=200', {
      headers: getAuthHeaders(),
    })
    const existingCards = existingResp.ok
      ? ((await existingResp.json()).cards || [])
      : []
    const cardBySegIdx = {}
    for (const c of existingCards) {
      let segIdx = null
      try {
        const ctx = c.context ? JSON.parse(c.context) : {}
        if (typeof ctx.segIdx === 'number') segIdx = ctx.segIdx
      } catch { /* ignore */ }
      if (segIdx == null) {
        segIdx = segs.findIndex((s) => s.text === c.text)
      }
      if (segIdx >= 0 && segIdx < segs.length) {
        cardBySegIdx[segIdx] = { ...c, segIdx }
      }
    }
    const missing = segs.filter((_, i) => !cardBySegIdx[i])
    if (missing.length) {
      await createCards({ items: missing })
      const refetchResp = await fetch('/practice/cards?limit=200', {
        headers: getAuthHeaders(),
      })
      const refetched = refetchResp.ok
        ? ((await refetchResp.json()).cards || [])
        : []
      for (const c of refetched) {
        let segIdx = null
        try {
          const ctx = c.context ? JSON.parse(c.context) : {}
          if (typeof ctx.segIdx === 'number') segIdx = ctx.segIdx
        } catch { /* ignore */ }
        if (segIdx == null) segIdx = segs.findIndex((s) => s.text === c.text)
        if (segIdx >= 0 && segIdx < segs.length) {
          cardBySegIdx[segIdx] = { ...c, segIdx }
        }
      }
    }
    store.cards = Object.values(cardBySegIdx)
    showToast(`已导入 ${segs.length} 段`, 'info')
  } catch (err) {
    const msg = getErrorMessage(err, '卡片初始化失败')
    if (msg) showToast(msg, 'error')
  }
}

function getAuthHeaders() {
  try {
    const t = localStorage.getItem('v2:auth.token') || localStorage.getItem('token')
    return t ? { Authorization: 'Bearer ' + t } : {}
  } catch { return {} }
}

function onSelect(idx) {
  store.setCurrentIdx(idx)
  listDrawerOpen.value = false
}

function onExplain(payload) {
  let target
  if (typeof payload === 'string') {
    target = { type: 'sentence', content: payload }
  } else {
    target = { type: payload.type, content: payload.content }
    if (payload.sentence) target.sentence = payload.sentence
  }
  const src = store.currentSource || {}
  const isBbc = src.source_type === 'bbc_eaw' || src.type === 'bbc_eaw'
  const vocabRef = isBbc
    ? { vocab_source_type: 'bbc_eaw', vocab_source_ref: src.slug || src.id || null }
    : { vocab_source_type: 'practice', vocab_source_ref: src.id || src.source_id || null }
  target.context = {
    source: 'practice',
    source_id: src.id,
    ...vocabRef,
    ...(target.sentence ? { sentence: target.sentence } : {}),
  }
  explainTarget.value = target
  explainOpen.value = true
}

function onRated({ level }) {
  showToast(`已评 ${level}`, 'info', 1200)
}

function onNewImport() {
  store.reset()
  sheetOpen.value = false
}

// ---- 手机端：选词 / 切句 / dock 动作 ----
function _releaseTTS() {
  if (_ttsAudio) { _ttsAudio.pause(); _ttsAudio = null }
  if (_ttsUrl)   { URL.revokeObjectURL(_ttsUrl); _ttsUrl = null }
  isPlayingTTS.value = false
}

function onMobileSelectSentence(idx) {
  if (idx === store.currentIdx) return
  // 状态机：录音中切句要 confirm
  if (recorder.recording.value) {
    const ok = window.confirm('正在录音，停止并切换到这一句？')
    if (!ok) return
    recorder.stop()
    recorder.reset()
    recordingSegIdx.value = null
  }
  _releaseTTS()
  // 离开旧句视作"完成一句"（v1 用切句作信号；issue #26 评分恢复后改为按 Good/Easy 计）
  if (store.currentIdx !== idx) practicedCount.value += 1
  store.setCurrentIdx(idx)
  selectedWord.value = null
  hasPlayedBack.value = false
}

function onMobileSelectWord({ word, display }) {
  selectedWord.value = { word, display }
}
function onMobileClearWord() {
  selectedWord.value = null
}

async function onMobileExplain() {
  const key = `explain:${store.currentIdx}:${selectedWord.value?.word || '__'}:${Date.now()}`
  _lastRequestKey = key
  if (selectedWord.value) {
    onExplain({
      type: 'word',
      content: selectedWord.value.display,
      sentence: store.currentSegment?.content || '',
    })
  } else {
    onExplain(store.currentSegment?.content || '')
  }
  // stale 防御对 modal 打开本身意义不大（用户已切句也无影响），保留 key 写入便于一致语义
  void key
}

async function onMobileSpeak() {
  const key = `tts:${store.currentIdx}:${selectedWord.value?.word || '__'}:${Date.now()}`
  _lastRequestKey = key
  _releaseTTS()
  isPlayingTTS.value = true
  try {
    const text = selectedWord.value ? selectedWord.value.display : (store.currentSegment?.content || '')
    if (!text) return
    const blob = await ttsBlob({
      text,
      provider: store.provider,
      speed: store.speed,
    })
    if (_lastRequestKey !== key) return // stale 丢弃
    _ttsUrl = URL.createObjectURL(blob)
    _ttsAudio = new Audio(_ttsUrl)
    _ttsAudio.onended = () => { if (_lastRequestKey === key) isPlayingTTS.value = false }
    await _ttsAudio.play()
  } catch (err) {
    const msg = getErrorMessage(err, 'TTS 失败')
    if (msg) showToast(msg, 'error')
    isPlayingTTS.value = false
  }
}

async function onMobileToggleRecord() {
  if (recorder.recording.value) {
    recorder.stop()
    recordingSegIdx.value = null
    hasPlayedBack.value = false
  } else {
    recorder.reset()
    await recorder.start()
    if (recorder.error.value) {
      showToast(recorder.error.value, 'error')
      return
    }
    recordingSegIdx.value = store.currentIdx
  }
}

function onMobilePlayback() {
  if (!recorder.url.value) {
    showToast('先录一段', 'info', 1200)
    return
  }
  const a = new Audio(recorder.url.value)
  a.play()
  hasPlayedBack.value = true
}

function onOpenSettings() { sheetOpen.value = true }
function onCloseSettings() { sheetOpen.value = false }

// 切句时清 TTS / 录音绑定校验
watch(
  () => store.currentIdx,
  (n, o) => {
    if (n === o) return
    _releaseTTS()
  }
)

onActivated(() => {})
onDeactivated(() => {})
onBeforeUnmount(() => {
  _releaseTTS()
  recorder.reset()
})
</script>
```

- [ ] **Step 2: 改 `<template>` —— 按 isMobile 切两套子树**

把 `<template>` 整段替换为：

```vue
<template>
  <div class="practice-page" :class="{ mobile: isMobile }">
    <header class="topbar">
      <RouterLink class="back" to="/">← 返回</RouterLink>
      <div class="title">发音练习</div>
      <div class="topbar-right">
        <!-- 桌面端原有列表/重新导入按钮（mobile 不显示，移进 ⚙ sheet） -->
        <template v-if="!isMobile">
          <button
            v-if="hasSource && isBbcSource"
            class="bbc-btn"
            @click="gotoBbcReview"
            title="开始/继续这篇 BBC 文章的 SRS 复习"
          >📖 复习</button>
          <button
            v-if="hasSource"
            class="new-btn"
            @click="onNewImport"
            title="重新导入字幕"
          >🔄</button>
        </template>
        <!-- 手机端：单一 ⚙ 设置入口 -->
        <button
          v-if="isMobile && hasSource"
          class="settings-btn"
          @click="onOpenSettings"
          aria-label="打开设置"
        >
          <span aria-hidden="true">⚙</span>
          <span>设置</span>
        </button>
      </div>
    </header>

    <div v-if="!hasSource" class="import-wrap">
      <SubtitleImport @imported="onImported" />
    </div>

    <!-- 桌面端布局 -->
    <div v-else-if="!isMobile" class="layout">
      <aside class="left">
        <div class="progress">
          <div class="progress-bar" :style="{ width: `${store.progressPct}%` }"></div>
        </div>
        <div class="stats">
          {{ store.totalPracticed }}/{{ store.segments.length }} 已练
          · Again: {{ store.ratingResults.again }}
          · Good: {{ store.ratingResults.good }}
        </div>
        <SentenceList @select="onSelect" @explain="onExplain" />
      </aside>
      <main class="right">
        <PracticePlayer
          @rated="onRated"
          @explain="onExplain"
          @toast="({ text, type, duration }) => showToast(text, type || 'info', duration || 2000)"
        />
      </main>
    </div>

    <!-- 手机端布局 -->
    <template v-else>
      <MobileSentenceList
        :selected-word="selectedWord"
        @select-sentence="onMobileSelectSentence"
        @select-word="onMobileSelectWord"
        @clear-word="onMobileClearWord"
      />
      <MobileActionDock
        :selected-word="selectedWord"
        :recording="recorder.recording.value"
        :is-playing-t-t-s="isPlayingTTS"
        :has-recording="!!recorder.url.value"
        :has-played-back="hasPlayedBack"
        :current-idx="store.currentIdx"
        :total-segments="store.segments.length"
        :practiced-count="practicedCount"
        @explain="onMobileExplain"
        @speak="onMobileSpeak"
        @toggle-record="onMobileToggleRecord"
        @playback="onMobilePlayback"
      />
    </template>

    <!-- ⚙ 手机端 sheet -->
    <Teleport to="body">
      <Transition name="sheet">
        <div
          v-if="sheetOpen"
          class="sheet-mask"
          @click.self="onCloseSettings"
          @keydown.esc="onCloseSettings"
        >
          <aside class="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title">
            <h4 id="sheet-title">设置</h4>
            <div class="sheet-row">
              <label>语速</label>
              <div class="seg-pick">
                <button
                  v-for="opt in [
                    { v: '-40%', label: '慢' },
                    { v: '-20%', label: '偏慢' },
                    { v: '+0%',  label: '正常' },
                    { v: '+20%', label: '偏快' },
                  ]"
                  :key="opt.v"
                  type="button"
                  :class="{ active: store.speed === opt.v }"
                  @click="store.speed = opt.v"
                >{{ opt.label }}</button>
              </div>
            </div>
            <div class="sheet-row">
              <label>TTS 引擎</label>
              <div class="seg-pick">
                <button
                  v-for="opt in [
                    { v: 'edge',   label: 'Edge' },
                    { v: 'doubao', label: '豆包' },
                  ]"
                  :key="opt.v"
                  type="button"
                  :class="{ active: store.provider === opt.v }"
                  @click="store.provider = opt.v"
                >{{ opt.label }}</button>
              </div>
            </div>

            <div class="sheet-divider"></div>

            <button
              v-if="isBbcSource"
              class="sheet-action"
              type="button"
              @click="gotoBbcReview(); onCloseSettings()"
            >
              <span class="sa-ico">📖</span>
              <span class="sa-body">
                <span class="sa-title">BBC 复习</span>
                <span class="sa-desc">基于 SRS 的文章复习</span>
              </span>
              <span class="sa-chev">›</span>
            </button>
            <button
              class="sheet-action"
              type="button"
              @click="onNewImport()"
            >
              <span class="sa-ico">🔄</span>
              <span class="sa-body">
                <span class="sa-title">重新导入字幕</span>
                <span class="sa-desc">换一集、换一篇</span>
              </span>
              <span class="sa-chev">›</span>
            </button>

            <div class="sheet-footer-note">
              ℹ︎ 关于复习评分 · 手机端暂不评分，本次练习不会进入 FSRS 复习计划；
              如需评分请到桌面端，或关注
              <a href="https://github.com/bob798/speakeasy/issues/26" target="_blank" rel="noopener">issue #26</a>。
            </div>
          </aside>
        </div>
      </Transition>
    </Teleport>

    <ExplanationModal v-model:open="explainOpen" :target="explainTarget" />

    <Transition name="toast">
      <div v-if="toast.show" class="toast" :class="toast.type">{{ toast.text }}</div>
    </Transition>
  </div>
</template>
```

- [ ] **Step 3: 改 `<style scoped>` —— 加 mobile 容器 + sheet 样式**

把 `.practice-page` 改为 `100dvh`（替代 `100vh` 防键盘抖动），并追加 sheet / settings-btn 样式：

```css
.practice-page {
  display: flex;
  flex-direction: column;
  height: 100dvh;            /* 改 100vh → 100dvh */
  background: var(--bg);
}
.practice-page.mobile {
  /* 手机端：MobileActionDock 是 sticky，列表能滚到底部 */
}

/* settings-btn（替代 mobile 的 📜 等） */
.settings-btn {
  min-width: 44px;
  height: 36px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  gap: 4px;
  border-radius: 18px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 14px;
  font-weight: 500;
  font-family: inherit;
  border: none;
  cursor: pointer;
}
.settings-btn:focus { outline: none; }
.settings-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.settings-btn:active { background: var(--accent); color: var(--text-inverse); transform: scale(0.96); }

/* sheet · 底部 */
.sheet-mask {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  z-index: var(--z-modal);
  display: flex;
  align-items: flex-end;
}
.sheet {
  width: 100%;
  background: var(--bg-elevated);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  padding: var(--space-4);
  padding-bottom: calc(var(--space-4) + var(--safe-bottom));
  max-height: 80dvh;
  overflow-y: auto;
}
.sheet h4 { margin: 0 0 var(--space-3); font-size: 14px; color: var(--text-2); }
.sheet-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
}
.sheet-row label { font-size: 14px; color: var(--text-1); }
.seg-pick { display: flex; gap: 4px; }
.seg-pick button {
  padding: 6px 10px;
  font-size: 12px;
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--text-2);
  border: 1px solid var(--border);
  font-family: inherit;
  cursor: pointer;
}
.seg-pick button.active {
  background: var(--accent); color: #fff; border-color: var(--accent);
}
.sheet-divider {
  height: 1px;
  background: var(--border);
  margin: 12px 0;
}
.sheet-action {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 10px 8px;
  border: none;
  background: transparent;
  border-radius: var(--radius);
  cursor: pointer;
  font-family: inherit;
  text-align: left;
  transition: background 120ms var(--ease);
}
.sheet-action:active { background: var(--bg); }
.sheet-action .sa-ico {
  width: 36px; height: 36px;
  display: grid; place-items: center;
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: var(--radius-sm);
  font-size: 18px;
}
.sheet-action .sa-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}
.sheet-action .sa-title { font-size: 14px; color: var(--text-1); font-weight: 500; }
.sheet-action .sa-desc { font-size: 11px; color: var(--text-3); }
.sheet-action .sa-chev { color: var(--text-3); font-size: 18px; }
.sheet-footer-note {
  margin-top: 12px;
  padding: 10px 12px;
  background: var(--bg);
  border-radius: var(--radius-sm);
  font-size: 11px;
  color: var(--text-3);
  line-height: 1.5;
}
.sheet-footer-note a { color: var(--accent); text-decoration: underline; }

.sheet-enter-active, .sheet-leave-active { transition: opacity 200ms var(--ease); }
.sheet-enter-active .sheet, .sheet-leave-active .sheet {
  transition: transform 220ms var(--ease);
}
.sheet-enter-from, .sheet-leave-to { opacity: 0; }
.sheet-enter-from .sheet, .sheet-leave-to .sheet { transform: translateY(100%); }
```

**注意：** 保留 `.topbar / .layout / .left / .right / .progress / .toast` 等桌面端样式块（原 `Practice.vue` 已有）。只**追加**上述 mobile 相关样式，**删除**以下不再用的旧块：
- `.mobile-only`、`.desktop-only` 媒体查询切换（现在通过 v-if 切换）
- `.list-btn`、`.list-drawer*`、`.ld-*`（句子列表抽屉已弃用）
- 原 `@media (min-width: 768px) { ... }` 块改为：桌面端样式作为默认，手机端用 `.practice-page.mobile` 选择器覆盖

- [ ] **Step 4: Lint check**

Run: `cd frontend && npm run lint -- src/views/Practice.vue`
Expected: 无 error

- [ ] **Step 5: 启动 dev server 手动验证**

Run: `cd frontend && npm run dev`

打开浏览器 → Practice 页 → Chrome DevTools mobile mode（iPhone 14, 390×844）→ 走核心路径：
1. 进页面（已导入 BBC 字幕）→ 应弹一次 FSRS toast，再 reload 不再弹
2. 当前句居中、其它句紧凑
3. 点当前句某词 → 下划线高亮 + 「已选: xxx」条 + dock 主标签变「解释单词」/「发音单词」+ coach bar 显示「解读 "xxx"」
4. ✕ 清除选词 → 主标签回「解释整句」
5. 切到 DevTools 桌面尺寸（1280px）→ 回原桌面端布局 → 切回 mobile 不报错

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/Practice.vue
git commit -m "feat(practice): wire mobile redesign into Practice.vue"
```

---

## Phase 5 · sheet a11y 收尾

### Task 6: sheet 焦点管理 + 背景 inert

**Files:**
- Modify: `frontend/src/views/Practice.vue`

- [ ] **Step 1: 加 sheet 打开/关闭的焦点管理**

在 `<script setup>` 适当位置（接近 `onOpenSettings`/`onCloseSettings`）替换为：

```js
const sheetTriggerRef = ref(null) // 记录打开 sheet 时的触发元素
const sheetRef = ref(null)        // <aside class="sheet"> dom ref

function onOpenSettings() {
  sheetTriggerRef.value = document.activeElement
  sheetOpen.value = true
  // 等下一帧 DOM 出现再 focus
  setTimeout(() => {
    const first = sheetRef.value?.querySelector('button')
    if (first) first.focus()
  }, 60)
  // 屏蔽背景 a11y
  document.querySelectorAll('.topbar, .m-list, .dock, .layout').forEach((el) => el.setAttribute('inert', ''))
}
function onCloseSettings() {
  sheetOpen.value = false
  document.querySelectorAll('.topbar, .m-list, .dock, .layout').forEach((el) => el.removeAttribute('inert'))
  if (sheetTriggerRef.value?.focus) sheetTriggerRef.value.focus()
}
```

并在模板的 `<aside class="sheet" ...>` 上加 `ref="sheetRef"`。

- [ ] **Step 2: 加全局 Esc 监听（仅 sheet 打开时生效）**

在 script 末尾加：

```js
function _onEscape(e) {
  if (e.key === 'Escape' && sheetOpen.value) onCloseSettings()
}
window.addEventListener('keydown', _onEscape)
onBeforeUnmount(() => window.removeEventListener('keydown', _onEscape))
```

- [ ] **Step 3: 手动验证**

Run: `cd frontend && npm run dev`，在 mobile mode 测：
- Tab 进 ⚙ 按钮 → Enter → sheet 打开，焦点落到第一个按钮（语速「慢」）
- 按 Esc → sheet 关，焦点回到 ⚙ 按钮
- Voice Over 或 Chrome a11y inspector 看背景区是否被 `inert` 屏蔽（语速 sheet 外的 list / dock 应不可达）

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/Practice.vue
git commit -m "feat(practice): sheet focus management + Esc + inert background"
```

---

## Phase 6 · 视觉 / 边界 / 回归

### Task 7: 长句 / 横屏 / 跨断点回归

**Files:**
- Verify only

- [ ] **Step 1: 长句压力测试**

在 Practice 页 import 一段含超长 token 的字幕（手动改 subtitle text 加 `pneumonoultramicroscopicsilicovolcanoconiosis` 之类）。
验证：当前句卡不撑炸，按词渲染正常断词，dock 不被推出屏外。

- [ ] **Step 2: 横屏测试**

DevTools 切 iPhone 14 横屏（844×390）→ 验证：
- coach bar 隐藏
- dock 两行按钮压成 44px 高
- 句子列表正常滚动

- [ ] **Step 3: 跨断点测试**

打开 Practice 页 mobile mode（390 宽）→ 点开 ⚙ sheet → 在 DevTools 把宽度拖到 1280 → 验证：
- sheet 自动关
- selectedWord 自动清
- 没有 ResizeObserver / matchMedia 报错
- 反向（1280 → 390）也无报错

- [ ] **Step 4: 录音中切句 confirm**

mobile mode → 点 🎤 录音 → 在录音过程中点列表里另一句 → 应弹 `window.confirm` 提示「正在录音，停止并切换到这一句？」
- 取消 → 留在当前句、继续录
- 确定 → 录音停止 + 切到新句 + 录音 blob discard

- [ ] **Step 5: 异步 stale 响应**

在 DevTools Network 面板设 Slow 3G → 选词 → 快速切到别句 → 切回 → 验证：旧请求回来不会触发任何 UI 变化（用 console.log 在 `_lastRequestKey !== key` 分支临时加日志验证一次后撤）。

- [ ] **Step 6: 提交（如有 fix）**

如果上述任何一步发现 bug 修了，按 fix 类型 commit：

```bash
git add -p
git commit -m "fix(practice): <具体描述>"
```

否则跳过此步。

---

### Task 8: Bundle size 校验

**Files:**
- Verify only

- [ ] **Step 1: 构建生产包**

Run: `cd frontend && npm run build`
Expected: 构建成功，无 error

- [ ] **Step 2: 检查 size budget**

Run: `cd frontend && npm run size`
Expected: 各项均在 budget 内（200KB JS gzip / 100KB CSS gzip 见 package.json size-limit 配置）

如超：检查是否引入了不必要的新依赖；本次只新增 composable + 2 个 Vue 组件，理论上增量 < 5KB gzip。

- [ ] **Step 3: 跑全套 unit tests**

Run: `cd frontend && npm test`
Expected: 全过（含新增 useCoachBar.spec.js）

- [ ] **Step 4: 后端 pytest 回归（防意外动到 API）**

```bash
source venv/bin/activate
pytest tests/ -v
```
Expected: 全过（本次不动后端，应该零变化）

- [ ] **Step 5: Commit（如有调整）**

如 budget 不达调整后 commit，否则跳过。

---

## Phase 7 · PR

### Task 9: 推分支 + 开 PR

**Files:**
- N/A

- [ ] **Step 1: 检查分支状态**

Run: `git log --oneline main..feat/practice-mobile-redesign`
Expected: 看到 spec commit + 7-8 个实现 commit

- [ ] **Step 2: 推到远程**

Run: `git push -u origin feat/practice-mobile-redesign`

- [ ] **Step 3: 开 PR**

```bash
gh pr create --title "feat(practice): 手机端重设计 · 单作用对象 + coach bar + 底部 dock" --body "$(cat <<'EOF'
## Summary

把 Practice 发音练习页手机端 (`<768px`) 改造为「单手大拇指可达 + 教练状态条引导」的练习页。桌面端不变。

设计文档：`docs/superpowers/specs/2026-05-12-practice-mobile-redesign.md`
原型：`mockups/practice-mobile-v2.html`

主要变化：
- 删除 📜 句子列表抽屉，列表直接在主页面滚
- dock 两行四按钮：💡 解释 / 🔊 发音 / 🎤 录音 / ▶ 回放
- dock 主标签随选词模式切换：默认 `解释整句`，选词后变 `解释单词`
- 新增 coach bar：引导 + 进度 + 反馈一行（v1 静态规则推导，v2 接 LLM）
- 顶栏只留 ⚙ 设置（语速 / 引擎 / 📖 BBC / 🔄 重新导入 / ℹ︎ FSRS 说明）
- 手机端暂无评分入口（issue #26 跟进）；首次进 Practice 弹一次 FSRS 披露 toast

## Test plan

- [ ] iPhone 14 模拟器：💡/🔊/🎤/▶/⚙ 单手可达
- [ ] 选词后 dock 主标签 + coach bar 同步变化
- [ ] 切句清选词，录音中切句弹 confirm
- [ ] 首次 toast + ⚙ 内 ℹ︎ 行都在
- [ ] 横屏 dock 压成单行，coach bar 隐藏
- [ ] 长句不撑炸卡片
- [ ] 跨断点（767 ↔ 768）resize 不残留 / 不报错
- [ ] 桌面端 ≥ 768px 布局不变
- [ ] `npm test` 全过（含新 useCoachBar.spec.js）
- [ ] `npm run size` 在 budget 内
- [ ] `npm run build` 成功

Closes 暂无（issue #26 后续处理评分）
EOF
)"