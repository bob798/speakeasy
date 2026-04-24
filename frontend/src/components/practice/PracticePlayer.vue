<script setup>
/**
 * PracticePlayer · 右侧练习区
 * 展示当前句 + TTS 播放 + 录音对比 + FSRS 评分
 * 迁移自 practice.html showControlsForLine / playTTS / startRecording / stopRecording 等
 */
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { usePracticeStore } from '@/stores/practice'
import { usePractice } from '@/composables/usePractice'
import { useRecorder } from '@/composables/useRecorder'

const emit = defineEmits(['rated', 'explain'])

const store = usePracticeStore()
const { ttsBlob, rateCard } = usePractice()
const recorder = useRecorder()

const ttsAudio = ref(null)
const ttsUrl = ref(null)
const ttsLoading = ref(false)
const ttsError = ref('')
const ratingBusy = ref(false)

const segment = computed(() => store.currentSegment)
const currentCardId = computed(() => {
  if (!segment.value) return null
  const card = store.cards.find((c) => c.segIdx === store.currentIdx)
  return card?.id || null
})

async function playTTS() {
  if (!segment.value) return
  ttsLoading.value = true
  ttsError.value = ''
  try {
    const blob = await ttsBlob({
      text: segment.value.content,
      provider: store.provider,
      speed: store.speed,
    })
    _releaseTTS()
    ttsUrl.value = URL.createObjectURL(blob)
    ttsAudio.value = new Audio(ttsUrl.value)
    await ttsAudio.value.play()
  } catch (err) {
    ttsError.value = err.message
  } finally {
    ttsLoading.value = false
  }
}

function playRecording() {
  if (!recorder.url.value) return
  const a = new Audio(recorder.url.value)
  a.play()
}

async function toggleRecord() {
  if (recorder.recording.value) {
    recorder.stop()
  } else {
    recorder.reset()
    await recorder.start()
  }
}

async function rate(level) {
  if (!currentCardId.value || ratingBusy.value) return
  ratingBusy.value = true
  try {
    await rateCard(currentCardId.value, level)
    store.markPracticed(store.currentIdx, level)
    emit('rated', { idx: store.currentIdx, level })
    // 自动跳下一句
    if (store.currentIdx < store.segments.length - 1) {
      store.setCurrentIdx(store.currentIdx + 1)
    }
  } catch (err) {
    ttsError.value = err.message
  } finally {
    ratingBusy.value = false
  }
}

function onExplain() {
  if (segment.value) emit('explain', segment.value.content)
}

function _releaseTTS() {
  if (ttsAudio.value) {
    ttsAudio.value.pause()
    ttsAudio.value = null
  }
  if (ttsUrl.value) {
    URL.revokeObjectURL(ttsUrl.value)
    ttsUrl.value = null
  }
}

// 换句时清理 TTS 缓存
watch(
  () => store.currentIdx,
  () => {
    _releaseTTS()
    recorder.reset()
  }
)

onBeforeUnmount(() => {
  _releaseTTS()
})
</script>

<template>
  <div class="player">
    <div v-if="!segment" class="empty-state">
      <p>👈 选一句开始练习</p>
    </div>

    <template v-else>
      <header class="text-box">
        <p class="sentence">{{ segment.content }}</p>
        <button class="explain" @click="onExplain" aria-label="解读">💡 解读</button>
      </header>

      <section class="controls">
        <div class="row">
          <label>语速：</label>
          <select v-model="store.speed">
            <option value="-40%">慢</option>
            <option value="-20%">偏慢</option>
            <option value="+0%">正常</option>
            <option value="+20%">偏快</option>
          </select>
          <label>引擎：</label>
          <select v-model="store.provider">
            <option value="edge">Edge</option>
            <option value="doubao">豆包</option>
          </select>
        </div>

        <div class="row btn-row">
          <button class="btn primary" :disabled="ttsLoading" @click="playTTS">
            {{ ttsLoading ? '加载中...' : '🔊 原音' }}
          </button>
          <button
            class="btn"
            :class="{ recording: recorder.recording.value }"
            @click="toggleRecord"
          >
            {{ recorder.recording.value ? '⏹ 停止' : '🎤 录音' }}
          </button>
          <button
            class="btn"
            :disabled="!recorder.url.value"
            @click="playRecording"
          >
            ▶ 回放
          </button>
        </div>

        <p v-if="ttsError" class="err">{{ ttsError }}</p>
        <p v-if="recorder.error.value" class="err">{{ recorder.error.value }}</p>
      </section>

      <section v-if="currentCardId" class="rating">
        <p class="hint">给自己打分（FSRS）：</p>
        <div class="btn-row">
          <button class="btn rate rate-again" :disabled="ratingBusy" @click="rate('again')">
            Again
          </button>
          <button class="btn rate rate-hard" :disabled="ratingBusy" @click="rate('hard')">
            Hard
          </button>
          <button class="btn rate rate-good" :disabled="ratingBusy" @click="rate('good')">
            Good
          </button>
          <button class="btn rate rate-easy" :disabled="ratingBusy" @click="rate('easy')">
            Easy
          </button>
        </div>
      </section>
      <p v-else class="hint">（卡片准备中...）</p>
    </template>
  </div>
</template>

<style scoped>
.player {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  height: 100%;
  overflow-y: auto;
}
.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-3);
}
.text-box {
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
}
.sentence {
  flex: 1;
  font-size: 18px;
  line-height: 1.6;
  color: var(--text-1);
  margin: 0;
  font-weight: 500;
}
.explain {
  flex-shrink: 0;
  padding: var(--space-1) var(--space-2);
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: var(--radius-sm);
  font-size: 12px;
}
.controls {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  flex-wrap: wrap;
}
.row label {
  font-size: 13px;
  color: var(--text-2);
}
select {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  font-size: 13px;
}
.btn-row {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.btn {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  color: var(--text-1);
  font-size: 13px;
  flex: 1;
  min-width: 80px;
}
.btn:active {
  background: var(--bg);
}
.btn:disabled {
  opacity: 0.5;
}
.btn.primary {
  background: var(--accent);
  color: var(--text-inverse);
  border-color: var(--accent);
}
.btn.recording {
  background: #c6463a;
  color: var(--text-inverse);
  border-color: #c6463a;
  animation: pulse 1s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}
.rating .hint {
  font-size: 12px;
  color: var(--text-3);
  margin: 0 0 var(--space-2);
}
.rate {
  font-weight: 500;
}
.rate-again { background: rgba(198, 70, 58, 0.1); color: #c6463a; }
.rate-hard  { background: rgba(214, 158, 46, 0.1); color: #b07a1a; }
.rate-good  { background: rgba(61, 107, 79, 0.1); color: var(--accent); }
.rate-easy  { background: rgba(46, 150, 64, 0.15); color: #2f7a40; }
.err {
  color: #c6463a;
  font-size: 12px;
  margin: 0;
}
.hint {
  font-size: 12px;
  color: var(--text-3);
}
</style>
