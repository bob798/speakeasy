<script setup>
/**
 * ExplanationModal · V0.9.3 重写
 *
 * 修复:
 *   - Bug 422: 后端 /practice/explain/stream 只收 {text}
 *     word 解读走 /practice/explain (非流，返 {explanation: {...}})
 *   - 字段名对齐后端 NDJSON: meaning / grammar / phrases / liaison /
 *                          current_level_points / next_level_points / narration
 *   - 单词同时拉 /practice/explain/phonetic 立刻展示 IPA
 *
 * @typedef {{ type: 'sentence'|'word', content: string, sentence?: string, context?: any }} ExplainTarget
 */
import { ref, watch, computed, onBeforeUnmount } from 'vue'
import { useSSE } from '@/composables/useSSE'
import { useTTS } from '@/composables/useTTS'
import { useAuthFetch } from '@/composables/useAuthFetch'
import { API } from '@/config'
import AskPanel from './AskPanel.vue'

const open = defineModel('open', { type: Boolean, default: false })
const props = defineProps({
  target: { type: Object, default: null },
})

const { stream: sseStream, streaming, abort: abortStream } = useSSE()
const { enqueue: ttsEnqueue, clear: ttsClear, playing: ttsPlaying } = useTTS()
const { authFetch, authFetchJson } = useAuthFetch()

const data = ref({
  phonetic: '',
  meaning: '',
  grammar: '',
  phrases: [],
  liaison: [],
  current_level_points: [],
  next_level_points: [],
  narration: '',
})
const loading = ref(false)
const error = ref('')
const activeTab = ref('explain')

const hasContent = computed(() => {
  return (
    data.value.phonetic ||
    data.value.meaning ||
    data.value.grammar ||
    data.value.phrases.length ||
    data.value.liaison.length ||
    data.value.current_level_points.length ||
    data.value.next_level_points.length
  )
})

function reset() {
  data.value = {
    phonetic: '',
    meaning: '',
    grammar: '',
    phrases: [],
    liaison: [],
    current_level_points: [],
    next_level_points: [],
    narration: '',
  }
  error.value = ''
  activeTab.value = 'explain'
}

async function fetchWord() {
  // 1. IPA 快拿
  try {
    const p = await authFetchJson(`${API.PRACTICE}/explain/phonetic`, {
      text: props.target.content,
    })
    data.value.phonetic = p.phonetic || ''
  } catch {
    /* IPA 失败不阻塞 */
  }

  // 2. 完整解读
  loading.value = true
  try {
    const resp = await authFetchJson(`${API.PRACTICE}/explain`, {
      text: props.target.content,
      kind: 'word',
      context: props.target.sentence || '',
    })
    const exp = resp.explanation || {}
    Object.assign(data.value, {
      meaning: exp.meaning || exp.summary || '',
      grammar: exp.grammar || '',
      phrases: exp.phrases || [],
      liaison: exp.liaison || [],
      current_level_points: exp.current_level_points || [],
      next_level_points: exp.next_level_points || [],
      narration: exp.narration || '',
    })
  } catch (err) {
    error.value = err.message || '解读失败'
  } finally {
    loading.value = false
  }
}

async function fetchSentence() {
  loading.value = true
  try {
    await sseStream(
      `${API.PRACTICE}/explain/stream`,
      { text: props.target.content }, // ✨ 修 422：只发 text
      {
        mode: 'ndjson',
        onEvent: (evt) => {
          if (evt._cached && evt.explanation) {
            // 缓存命中：整体回填
            const exp = evt.explanation
            Object.assign(data.value, {
              meaning: exp.meaning || '',
              grammar: exp.grammar || '',
              phrases: exp.phrases || [],
              liaison: exp.liaison || [],
              current_level_points: exp.current_level_points || [],
              next_level_points: exp.next_level_points || [],
              narration: exp.narration || '',
            })
            return
          }
          if (evt._done) return
          if (evt._error) {
            error.value = evt._error
            return
          }
          if (evt.field && evt.value != null && evt.field in data.value) {
            data.value[evt.field] = evt.value
          }
        },
        onError: (err) => {
          error.value = err.message || '解读失败'
        },
      }
    )
  } catch (err) {
    error.value = err.message || '解读失败'
  } finally {
    loading.value = false
  }
}

async function fetchExplanation() {
  reset()
  if (!props.target) return
  if (props.target.type === 'word') {
    await fetchWord()
  } else {
    await fetchSentence()
  }
}

watch(
  () => [open.value, props.target?.content],
  ([isOpen]) => {
    if (isOpen && props.target?.content) {
      fetchExplanation()
    } else if (!isOpen) {
      abortStream()
      ttsClear()
    }
  }
)

function playTarget() {
  if (!props.target?.content) return
  ttsEnqueue(props.target.content, { manual: true })
}

function playNarration() {
  if (!data.value.narration) return
  ttsEnqueue(data.value.narration, { manual: true })
}

function close() {
  open.value = false
}

function refId() {
  if (!props.target) return ''
  return `${props.target.type}:${props.target.content.slice(0, 50)}`
}

onBeforeUnmount(() => {
  ttsClear()
  abortStream()
})
</script>

<template>
  <Transition name="drawer">
    <div v-if="open" class="modal-overlay" @click.self="close">
      <aside class="drawer">
        <header class="drawer-head">
          <div class="target">
            <span class="kind">{{ target?.type === 'word' ? '单词' : '句子' }}</span>
            <span class="content">{{ target?.content }}</span>
            <span v-if="data.phonetic" class="ipa">{{ data.phonetic }}</span>
          </div>
          <button
            class="play-btn"
            :class="{ playing: ttsPlaying }"
            @click="playTarget"
            :disabled="!target?.content"
            aria-label="朗读目标"
            title="朗读"
          >
            {{ ttsPlaying ? '⏸' : '🔊' }}
          </button>
          <button class="close" @click="close" aria-label="关闭">×</button>
        </header>

        <nav class="tabs">
          <button
            class="tab"
            :class="{ active: activeTab === 'explain' }"
            @click="activeTab = 'explain'"
          >
            解读
          </button>
          <button
            class="tab"
            :class="{ active: activeTab === 'ask' }"
            @click="activeTab = 'ask'"
            :disabled="!target?.content"
          >
            追问
          </button>
        </nav>

        <div v-show="activeTab === 'explain'" class="explain-box">
          <div v-if="loading && !hasContent" class="loading">
            <span class="dots"><span></span><span></span><span></span></span>
            解读中...
          </div>
          <div v-if="error" class="error">❌ {{ error }}</div>

          <section v-if="data.meaning" class="section">
            <h4>含义</h4>
            <div>{{ data.meaning }}</div>
          </section>
          <section v-if="data.grammar" class="section">
            <h4>语法</h4>
            <div class="pre">{{ data.grammar }}</div>
          </section>
          <section v-if="data.phrases?.length" class="section">
            <h4>搭配 / 词组</h4>
            <ul>
              <li v-for="(p, i) in data.phrases" :key="i">{{ p }}</li>
            </ul>
          </section>
          <section v-if="data.liaison?.length" class="section">
            <h4>连读 / 发音</h4>
            <ul>
              <li v-for="(l, i) in data.liaison" :key="i">{{ l }}</li>
            </ul>
          </section>
          <section v-if="data.current_level_points?.length" class="section">
            <h4>你这个级别要抓的点</h4>
            <ul>
              <li v-for="(p, i) in data.current_level_points" :key="i">{{ p }}</li>
            </ul>
          </section>
          <section v-if="data.next_level_points?.length" class="section">
            <h4>下个级别再扩的点</h4>
            <ul>
              <li v-for="(p, i) in data.next_level_points" :key="i">{{ p }}</li>
            </ul>
          </section>
          <section v-if="data.narration" class="section narration-row">
            <button class="narr-play" @click="playNarration" :disabled="ttsPlaying">
              {{ ttsPlaying ? '⏸ 播解读中' : '🔊 播一遍解读' }}
            </button>
          </section>
        </div>

        <div v-show="activeTab === 'ask'" class="ask-box">
          <AskPanel
            v-if="target?.content"
            scope="practice_explain"
            ref-type="explanation"
            :ref-id="refId()"
            :context-payload="{
              target_type: target?.type,
              target_content: target?.content,
              sentence: target?.sentence,
              meaning: data.meaning,
            }"
            placeholder="还想问点什么..."
            empty-hint="有疑惑就问 Alex"
          />
        </div>
      </aside>
    </div>
  </Transition>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.38);
  z-index: var(--z-modal);
  display: flex;
  justify-content: flex-end;
}
.drawer {
  width: 480px;
  max-width: 92vw;
  height: 100%;
  background: var(--bg-elevated);
  display: flex;
  flex-direction: column;
  padding-top: var(--safe-top);
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.12);
}
.drawer-head {
  padding: var(--space-4);
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-2);
}
.target {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.kind {
  display: inline-block;
  font-size: 11px;
  color: var(--accent);
  background: var(--accent-soft);
  padding: 2px 8px;
  border-radius: 999px;
  align-self: flex-start;
}
.content {
  font-weight: 500;
  word-break: break-word;
  font-size: 15px;
}
.ipa {
  color: var(--accent);
  font-family: Georgia, 'SF Pro Text', serif;
  font-size: 13px;
  margin-top: 2px;
}
.play-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  font-size: 16px;
  color: var(--accent);
  background: var(--accent-soft);
  flex-shrink: 0;
  transition: transform var(--duration) var(--ease);
}
.play-btn:active {
  transform: scale(0.92);
  background: var(--accent);
  color: var(--text-inverse);
}
.play-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.play-btn.playing {
  animation: play-pulse 1.4s ease-in-out infinite;
}
@keyframes play-pulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--accent-soft); }
  50% { box-shadow: 0 0 0 6px transparent; }
}
.close {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 22px;
  color: var(--text-3);
  flex-shrink: 0;
}
.close:active {
  background: var(--bg);
}
.tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}
.tab {
  flex: 1;
  padding: var(--space-3);
  font-size: 14px;
  color: var(--text-2);
  border-bottom: 2px solid transparent;
  transition: color var(--duration) var(--ease), border-color var(--duration) var(--ease);
}
.tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
  font-weight: 500;
}
.tab:disabled {
  opacity: 0.5;
}
.explain-box {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
}
.ask-box {
  flex: 1;
  overflow: hidden;
  display: flex;
}
.ask-box > :deep(.ap-root) {
  width: 100%;
}
.section {
  margin-bottom: var(--space-5);
}
.section h4 {
  margin: 0 0 var(--space-2);
  font-size: 12px;
  color: var(--text-3);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.section div {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-1);
}
.pre {
  white-space: pre-wrap;
}
.section ul {
  margin: 0;
  padding-left: var(--space-4);
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-1);
}
.section li {
  margin-bottom: 4px;
}
.narration-row {
  padding-top: var(--space-4);
  border-top: 1px dashed var(--border);
  margin-top: var(--space-5);
}
.narr-play {
  width: 100%;
  padding: var(--space-3);
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: var(--radius-sm);
  font-weight: 500;
  transition: background var(--duration) var(--ease);
}
.narr-play:active {
  background: var(--accent);
  color: var(--text-inverse);
}
.narr-play:disabled {
  opacity: 0.5;
}
.loading {
  text-align: center;
  color: var(--text-3);
  padding: var(--space-6);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
}
.dots span {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-3);
  margin: 0 2px;
  animation: bounce 1.4s infinite ease-in-out both;
}
.dots span:nth-child(1) { animation-delay: -0.32s; }
.dots span:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); opacity: 0.3; }
  40% { transform: scale(1); opacity: 1; }
}
.error {
  padding: var(--space-3);
  background: rgba(176, 64, 58, 0.1);
  color: #b0403a;
  border-radius: var(--radius);
  font-size: 13px;
}

.drawer-enter-active,
.drawer-leave-active {
  transition: opacity var(--duration) var(--ease);
}
.drawer-enter-active > .drawer,
.drawer-leave-active > .drawer {
  transition: transform var(--duration) var(--ease);
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from > .drawer,
.drawer-leave-to > .drawer {
  transform: translateX(100%);
}
</style>
