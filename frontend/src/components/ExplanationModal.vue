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
import { ref, watch, computed, nextTick, onBeforeUnmount, useTemplateRef } from 'vue'
import { useSSE } from '@/composables/useSSE'
import { useTTS } from '@/composables/useTTS'
import { useAuthFetch, getErrorMessage } from '@/composables/useAuthFetch'
import { API } from '@/config'
import AskPanel from './AskPanel.vue'

const open = defineModel('open', { type: Boolean, default: false })
const props = defineProps({
  target: { type: Object, default: null },
})

const { stream: sseStream, streaming, abort: abortStream } = useSSE()
const { enqueue: ttsEnqueue, clear: ttsClear, playing: ttsPlaying } = useTTS()
const { authFetch, authFetchJson } = useAuthFetch()

const askPanelRef = useTemplateRef('askPanelRef')
const ttsLoading = ref(false)

// ── 收藏到生词本（V0.10）─────────────────────────────────────
const starState = ref('idle')   // idle | saving | saved | error
const starError = ref('')

function deriveVocabSource() {
  // 来源由父组件透传到 target.context；下面的 fallback 兼容老调用
  const ctx = props.target?.context || {}
  // 父组件优先：显式传入 vocab_source_type / vocab_source_ref
  if (ctx.vocab_source_type) {
    return {
      source_type: ctx.vocab_source_type,
      source_ref: ctx.vocab_source_ref || null,
    }
  }
  // 老路径推断
  if (ctx.source === 'chat') {
    return { source_type: 'chat', source_ref: ctx.session_id || null }
  }
  if (ctx.source === 'practice') {
    return { source_type: 'practice', source_ref: ctx.source_id || null }
  }
  // 解读页 / 其它
  return { source_type: 'translate', source_ref: null }
}

const data = ref({
  // Sentence fields
  meaning: '',
  grammar: '',
  phrases: [],
  liaison: [],
  current_level_points: [],
  next_level_points: [],
  // Word fields
  phonetic: '',
  pos: '',
  definitions: [],
  examples: [],
  synonyms: [],
  antonyms: [],
  current_level_usage: '',
  next_level_usage: '',
  // Shared
  narration: '',
})
const loading = ref(false)
const error = ref('')
const activeTab = ref('explain')

const hasContent = computed(() => {
  const d = data.value
  return (
    d.phonetic || d.meaning || d.grammar || d.pos ||
    d.definitions.length || d.examples.length ||
    d.phrases.length || d.liaison.length ||
    d.synonyms.length || d.antonyms.length ||
    d.current_level_points.length || d.next_level_points.length ||
    d.current_level_usage || d.next_level_usage
  )
})

function reset() {
  data.value = {
    meaning: '', grammar: '', phrases: [], liaison: [],
    current_level_points: [], next_level_points: [],
    phonetic: '', pos: '', definitions: [], examples: [],
    synonyms: [], antonyms: [],
    current_level_usage: '', next_level_usage: '',
    narration: '',
  }
  error.value = ''
  activeTab.value = 'explain'
  starState.value = 'idle'
  starError.value = ''
}

async function saveToVocab() {
  if (!props.target?.content || starState.value === 'saving') return
  starState.value = 'saving'
  starError.value = ''
  const { source_type, source_ref } = deriveVocabSource()
  // 拼一份解释 JSON（按 type 取相关字段）
  const exp = data.value
  const explanationPayload = props.target.type === 'word'
    ? {
        phonetic: exp.phonetic,
        pos: exp.pos,
        definitions: exp.definitions,
        examples: exp.examples,
        synonyms: exp.synonyms,
        antonyms: exp.antonyms,
      }
    : {
        meaning: exp.meaning,
        grammar: exp.grammar,
        phrases: exp.phrases,
        liaison: exp.liaison,
      }
  // 句子用 sentence；word 单 token；多 token 视作 phrase
  let item_type = 'sentence'
  if (props.target.type === 'word') {
    const tokens = props.target.content.trim().split(/\s+/)
    item_type = tokens.length === 1 ? 'word' : 'phrase'
  }
  const translated = props.target.type === 'word'
    ? (exp.definitions?.[0] || '')
    : (exp.meaning || '')

  try {
    await authFetchJson(API.VOCAB, {
      source_text: props.target.content,
      translated_text: translated,
      direction: 'en2zh',
      context: props.target.sentence || '',
      item_type,
      source_type,
      source_ref,
      explanation_json: JSON.stringify(explanationPayload),
    })
    starState.value = 'saved'
  } catch (err) {
    starError.value = getErrorMessage(err, '收藏失败')
    starState.value = 'error'
  }
}

async function fetchWord() {
  // 1. IPA 快拿（本地秒出 · 不阻塞主请求）
  try {
    const p = await authFetchJson(`${API.PRACTICE}/explain/phonetic`, {
      text: props.target.content,
    })
    data.value.phonetic = p.phonetic || ''
  } catch {
    /* IPA 失败不阻塞 */
  }

  // 2. 完整解读 · Word prompt 9 字段
  loading.value = true
  try {
    const resp = await authFetchJson(`${API.PRACTICE}/explain`, {
      text: props.target.content,
      kind: 'word',
      context: props.target.sentence || '',
    })
    const exp = resp.explanation || {}
    Object.assign(data.value, {
      phonetic: exp.phonetic || data.value.phonetic,  // LLM 版盖掉 local 版
      pos: exp.pos || '',
      definitions: exp.definitions || [],
      examples: exp.examples || [],
      synonyms: exp.synonyms || [],
      antonyms: exp.antonyms || [],
      current_level_usage: exp.current_level_usage || '',
      next_level_usage: exp.next_level_usage || '',
      narration: exp.narration || '',
    })
  } catch (err) {
    error.value = getErrorMessage(err, '解读失败')
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
          error.value = getErrorMessage(err, '解读失败')
        },
      }
    )
  } catch (err) {
    error.value = getErrorMessage(err, '解读失败')
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

async function playTarget() {
  if (!props.target?.content) return
  ttsLoading.value = true
  // 监听 playing → 变 true 后关掉 loading；或 1.5s 超时兜底
  const t = setTimeout(() => (ttsLoading.value = false), 2000)
  const stop = watch(ttsPlaying, (v) => {
    if (v) {
      ttsLoading.value = false
      clearTimeout(t)
      stop()
    }
  })
  ttsEnqueue(props.target.content, { manual: true })
}

async function playNarration() {
  if (!data.value.narration) return
  ttsLoading.value = true
  const t = setTimeout(() => (ttsLoading.value = false), 2000)
  const stop = watch(ttsPlaying, (v) => {
    if (v) {
      ttsLoading.value = false
      clearTimeout(t)
      stop()
    }
  })
  ttsEnqueue(data.value.narration, { manual: true })
}

watch(activeTab, async (tab) => {
  if (tab === 'ask') {
    await nextTick()
    setTimeout(() => askPanelRef.value?.focus(), 100)
  }
})

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
            class="star-btn"
            :class="{ saved: starState === 'saved', saving: starState === 'saving', error: starState === 'error' }"
            @click="saveToVocab"
            :disabled="!target?.content || starState === 'saving' || starState === 'saved'"
            :aria-label="starState === 'saved' ? '已收藏' : '收藏到生词本'"
            :title="starState === 'error' ? (starError || '收藏失败') : (starState === 'saved' ? '已加入生词本' : '收藏到生词本')"
          >
            <span v-if="starState === 'saving'" class="spin">⏳</span>
            <span v-else>{{ starState === 'saved' ? '★' : '☆' }}</span>
          </button>
          <button
            class="play-btn"
            :class="{ playing: ttsPlaying, loading: ttsLoading }"
            @click="playTarget"
            :disabled="!target?.content || ttsLoading"
            aria-label="朗读目标"
            title="朗读"
          >
            <span v-if="ttsLoading" class="spin">⏳</span>
            <span v-else>{{ ttsPlaying ? '⏸' : '🔊' }}</span>
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

          <!-- ═══ Word 字段 ═══ -->
          <template v-if="target?.type === 'word'">
            <section v-if="data.pos || data.definitions?.length" class="section">
              <h4>📖 释义</h4>
              <div v-if="data.pos" class="pos-tag">{{ data.pos }}</div>
              <ul v-if="data.definitions?.length">
                <li v-for="(d, i) in data.definitions" :key="i">{{ d }}</li>
              </ul>
            </section>
            <section v-if="data.examples?.length" class="section">
              <h4>📝 例句</h4>
              <ul class="examples">
                <li v-for="(ex, i) in data.examples" :key="i">
                  <div class="en">{{ ex.en }}</div>
                  <div class="zh">{{ ex.zh }}</div>
                </li>
              </ul>
            </section>
            <section v-if="data.synonyms?.length || data.antonyms?.length" class="section">
              <h4>🔗 近反义词</h4>
              <div v-if="data.synonyms?.length" class="tagline">
                <span class="label">近:</span>
                <span v-for="(w, i) in data.synonyms" :key="i" class="tag syn">{{ w }}</span>
              </div>
              <div v-if="data.antonyms?.length" class="tagline">
                <span class="label">反:</span>
                <span v-for="(w, i) in data.antonyms" :key="i" class="tag ant">{{ w }}</span>
              </div>
            </section>
            <section v-if="data.current_level_usage" class="section">
              <h4>🎯 你这级怎么用</h4>
              <div>{{ data.current_level_usage }}</div>
            </section>
            <section v-if="data.next_level_usage" class="section">
              <h4>⬆ 下级进阶用法</h4>
              <div>{{ data.next_level_usage }}</div>
            </section>
          </template>

          <!-- ═══ Sentence 字段 ═══ -->
          <template v-else>
            <section v-if="data.meaning" class="section">
              <h4>💡 意思</h4>
              <div>{{ data.meaning }}</div>
            </section>
            <section v-if="data.grammar" class="section">
              <h4>🔨 语法结构</h4>
              <div class="pre">{{ data.grammar }}</div>
            </section>
            <section v-if="data.phrases?.length" class="section">
              <h4>🔗 搭配 / 词组</h4>
              <ul class="phrases">
                <li v-for="(p, i) in data.phrases" :key="i">
                  <span class="phrase">{{ p.phrase || p }}</span>
                  <span v-if="p.note" class="note">{{ p.note }}</span>
                </li>
              </ul>
            </section>
            <section v-if="data.liaison?.length" class="section">
              <h4>🔊 连读 · 发音</h4>
              <ul class="liaison">
                <li v-for="(l, i) in data.liaison" :key="i">
                  <span class="chunk">{{ l.chunk || l }}</span>
                  <span v-if="l.ipa" class="ipa-inline">{{ l.ipa }}</span>
                  <span v-if="l.tip" class="tip">{{ l.tip }}</span>
                </li>
              </ul>
            </section>
            <section v-if="data.current_level_points?.length" class="section">
              <h4>🎯 你这级要抓的点</h4>
              <ul>
                <li v-for="(p, i) in data.current_level_points" :key="i">{{ p }}</li>
              </ul>
            </section>
            <section v-if="data.next_level_points?.length" class="section">
              <h4>⬆ 下级再扩的点</h4>
              <ul>
                <li v-for="(p, i) in data.next_level_points" :key="i">{{ p }}</li>
              </ul>
            </section>
          </template>

          <!-- ═══ 通用 · 播解读 ═══ -->
          <section v-if="data.narration" class="section narration-row">
            <button class="narr-play" @click="playNarration" :disabled="ttsPlaying">
              {{ ttsPlaying ? '⏸ 播解读中' : '🔊 播一遍解读' }}
            </button>
          </section>
        </div>

        <div v-show="activeTab === 'ask'" class="ask-box">
          <AskPanel
            v-if="target?.content"
            ref="askPanelRef"
            scope="practice_explain"
            ref-type="explanation"
            :ref-id="refId()"
            :context-payload="{
              kind: target?.type,
              text: target?.content,
              context: target?.sentence || '',
              explanation: {
                meaning: data.meaning,
                grammar: data.grammar,
                phrases: data.phrases,
              },
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
.star-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  font-size: 18px;
  color: var(--accent);
  background: var(--accent-soft);
  flex-shrink: 0;
  transition: transform var(--duration) var(--ease), background var(--duration) var(--ease);
}
.star-btn:active {
  transform: scale(0.92);
}
.star-btn.saved {
  color: #c89b3c;
  background: rgba(200, 155, 60, 0.16);
  cursor: default;
}
.star-btn.error {
  color: #b0403a;
  background: rgba(176, 64, 58, 0.12);
}
.star-btn:disabled {
  opacity: 0.6;
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
.play-btn.loading {
  opacity: 0.75;
}
.spin {
  display: inline-block;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
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
.pos-tag {
  display: inline-block;
  padding: 2px 10px;
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: 999px;
  font-size: 12px;
  margin-bottom: var(--space-2);
}
.examples {
  list-style: none;
  padding: 0;
}
.examples li {
  margin-bottom: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--bg);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--accent);
}
.examples .en {
  font-size: 14px;
  color: var(--text-1);
  margin-bottom: 2px;
}
.examples .zh {
  font-size: 12px;
  color: var(--text-2);
}
.tagline {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-bottom: var(--space-2);
}
.tagline .label {
  font-size: 12px;
  color: var(--text-3);
  font-weight: 500;
}
.tag {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
}
.tag.syn {
  background: rgba(61, 107, 79, 0.1);
  color: var(--accent);
}
.tag.ant {
  background: rgba(198, 70, 58, 0.1);
  color: #c6463a;
}
.phrases {
  list-style: none;
  padding: 0;
}
.phrases li {
  margin-bottom: var(--space-2);
}
.phrase {
  font-weight: 500;
  color: var(--text-1);
}
.note {
  color: var(--text-2);
  font-size: 12px;
  margin-left: var(--space-2);
}
.liaison {
  list-style: none;
  padding: 0;
}
.liaison li {
  padding: var(--space-2) 0;
  border-bottom: 1px dashed var(--border);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: baseline;
}
.liaison li:last-child {
  border-bottom: none;
}
.chunk {
  font-weight: 500;
}
.ipa-inline {
  color: var(--accent);
  font-family: Georgia, 'SF Pro Text', serif;
  font-size: 13px;
}
.tip {
  color: var(--text-2);
  font-size: 12px;
  width: 100%;
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
