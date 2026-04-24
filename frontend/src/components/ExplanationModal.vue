<script setup>
/**
 * ExplanationModal · V0.7 句子/单词解读抽屉
 * 共用组件 · Chat 点击 AI 气泡触发 · Practice 点击字幕句触发
 *
 * 调 /practice/explain/stream (NDJSON 流式) 逐字段渐进渲染；内嵌 AskPanel 做追问。
 *
 * props:
 *   open (v-model) boolean
 *   target { type, content, context } · type='sentence' | 'word'
 *
 * @typedef {{ type: 'sentence'|'word', content: string, context?: any }} ExplainTarget
 */
import { ref, watch, computed, onBeforeUnmount } from 'vue'
import { useSSE } from '@/composables/useSSE'
import { useTTS } from '@/composables/useTTS'
import AskPanel from './AskPanel.vue'

const open = defineModel('open', { type: Boolean, default: false })
const props = defineProps({
  /** @type {import('vue').PropType<ExplainTarget | null>} */
  target: { type: Object, default: null },
})

const { stream: sseStream, streaming, abort: abortStream } = useSSE()
const { enqueue: ttsEnqueue, clear: ttsClear, playing: ttsPlaying } = useTTS()

function playTarget() {
  if (!props.target?.content) return
  ttsEnqueue(props.target.content, { manual: true })
}

onBeforeUnmount(() => {
  ttsClear()
})

const explanation = ref({
  summary: '',
  breakdown: '',
  translation: '',
  ipa: '',
  grammar: '',
})
const error = ref('')
const activeTab = ref('explain') // explain | ask

const hasContent = computed(() => Object.values(explanation.value).some((v) => v))

function reset() {
  explanation.value = {
    summary: '',
    breakdown: '',
    translation: '',
    ipa: '',
    grammar: '',
  }
  error.value = ''
  activeTab.value = 'explain'
}

async function fetchExplanation() {
  reset()
  if (!props.target) return

  try {
    await sseStream(
      '/practice/explain/stream',
      {
        type: props.target.type,
        content: props.target.content,
        context: props.target.context || {},
      },
      {
        mode: 'ndjson',
        onEvent: (evt) => {
          // 每个 NDJSON line 是 { field: 'summary', value: '...' } 或片段累积
          if (evt.field && evt.value != null) {
            if (evt.append) {
              explanation.value[evt.field] =
                (explanation.value[evt.field] || '') + evt.value
            } else {
              explanation.value[evt.field] = evt.value
            }
          } else if (evt.error) {
            error.value = evt.error
          }
        },
        onError: (err) => {
          error.value = err.message || '解读失败'
        },
      }
    )
  } catch (err) {
    error.value = err.message || '解读失败'
  }
}

watch(
  () => [open.value, props.target?.content],
  ([isOpen, _content]) => {
    if (isOpen && props.target?.content) {
      fetchExplanation()
    } else if (!isOpen) {
      abortStream()
    }
  }
)

function close() {
  open.value = false
}

function refId() {
  if (!props.target) return ''
  return `${props.target.type}:${props.target.content.slice(0, 50)}`
}
</script>

<template>
  <Transition name="drawer">
    <div v-if="open" class="modal-overlay" @click.self="close">
      <aside class="drawer">
        <header class="drawer-head">
          <div class="target">
            <span class="kind">{{ target?.type === 'word' ? '单词' : '句子' }}</span>
            <span class="content">{{ target?.content }}</span>
          </div>
          <button
            class="play-btn"
            :class="{ playing: ttsPlaying }"
            @click="playTarget"
            :disabled="!target?.content"
            aria-label="朗读"
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
          <div v-if="streaming && !hasContent" class="loading">解读中...</div>
          <div v-if="error" class="error">❌ {{ error }}</div>

          <section v-if="explanation.ipa" class="section">
            <h4>IPA 音标</h4>
            <div class="ipa">{{ explanation.ipa }}</div>
          </section>
          <section v-if="explanation.summary" class="section">
            <h4>速读</h4>
            <div>{{ explanation.summary }}</div>
          </section>
          <section v-if="explanation.translation" class="section">
            <h4>翻译</h4>
            <div>{{ explanation.translation }}</div>
          </section>
          <section v-if="explanation.breakdown" class="section">
            <h4>拆解</h4>
            <div class="pre">{{ explanation.breakdown }}</div>
          </section>
          <section v-if="explanation.grammar" class="section">
            <h4>语法</h4>
            <div class="pre">{{ explanation.grammar }}</div>
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
              summary: explanation.summary,
            }"
            placeholder="问点什么关于这句/这个词..."
            empty-hint="解读之外还有想深究的，问 Alex"
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
  gap: var(--space-3);
}
.target {
  flex: 1;
  min-width: 0;
}
.kind {
  display: inline-block;
  font-size: 11px;
  color: var(--accent);
  background: var(--accent-soft);
  padding: 2px 8px;
  border-radius: 999px;
  margin-bottom: 4px;
}
.content {
  display: block;
  font-weight: 500;
  word-break: break-word;
}
.play-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  font-size: 16px;
  color: var(--accent);
  background: var(--accent-soft);
  flex-shrink: 0;
  transition: background var(--duration) var(--ease);
}
.play-btn:active {
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
.ipa {
  font-family: 'SF Pro Text', Georgia, serif;
  font-size: 16px !important;
  color: var(--accent) !important;
}
.pre {
  white-space: pre-wrap;
}
.loading {
  text-align: center;
  color: var(--text-3);
  padding: var(--space-6);
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
