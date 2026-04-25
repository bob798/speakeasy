<script setup>
/**
 * PracticePlayer · V0.9.3
 *
 * 修:
 *   - 选中句子无 card 时自动补创建（不再卡在"卡片准备中"）
 *   - 单词解读入口：输入框 + 点击句中单词（从当前句拆词）
 *   - 所有按钮加 active 反馈 + toast 回显
 *   - 评分按 Easy 后自动跳下一句（沿用老版）
 */
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { usePracticeStore } from '@/stores/practice'
import { usePractice } from '@/composables/usePractice'
import { useRecorder } from '@/composables/useRecorder'
import { useAuthFetch } from '@/composables/useAuthFetch'

const emit = defineEmits(['rated', 'explain', 'toast'])

const store = usePracticeStore()
const { ttsBlob, rateCard, createCards } = usePractice()
const { authFetch } = useAuthFetch()
const recorder = useRecorder()

const ttsAudio = ref(null)
const ttsUrl = ref(null)
const ttsLoading = ref(false)
const ratingBusy = ref(false)
const cardLoading = ref(false)
const wordQuery = ref('')

const segment = computed(() => store.currentSegment)
const currentCard = computed(() =>
  store.cards.find((c) => c.segIdx === store.currentIdx) || null
)
const words = computed(() => {
  if (!segment.value) return []
  // 拆词（保留单词，过滤标点与空白）
  const re = /[A-Za-z][A-Za-z'-]*/g
  const result = []
  let m
  while ((m = re.exec(segment.value.content)) !== null) {
    if (!result.includes(m[0])) result.push(m[0])
  }
  return result
})

// 自动补卡片
watch(
  [() => store.currentIdx, () => store.segments.length],
  async () => {
    if (!segment.value || currentCard.value) return
    if (cardLoading.value) return
    cardLoading.value = true
    try {
      const segText = segment.value.content
      const ctxStr = JSON.stringify({
        segIdx: store.currentIdx,
        from: segment.value.from,
        to: segment.value.to,
      })
      // POST 返 {created, skipped}（无 cards 数组）· 随后 GET 拉回
      await createCards({
        items: [{ text: segText, context: ctxStr }],
      })
      // 再 GET 取新卡（text 匹配）
      const resp = await authFetch('/practice/cards?limit=200')
      if (resp.ok) {
        const list = (await resp.json()).cards || []
        // 找到 text 匹配的 card，建立 segIdx 映射
        const match = list.find((c) => {
          if (c.text === segText) return true
          // normalize 兜底：后端可能做过 text normalize
          return String(c.text).toLowerCase().trim() === segText.toLowerCase().trim()
        })
        if (match) {
          store.upsertCard({ ...match, segIdx: store.currentIdx })
        }
      }
    } catch (err) {
      emit('toast', { text: '卡片创建失败: ' + (err.message || err), type: 'error' })
    } finally {
      cardLoading.value = false
    }
  },
  { immediate: true }
)

async function playTTS() {
  if (!segment.value) return
  ttsLoading.value = true
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
    emit('toast', { text: '▶ 播放中', type: 'info', duration: 1000 })
  } catch (err) {
    emit('toast', { text: err.message || 'TTS 失败', type: 'error' })
  } finally {
    ttsLoading.value = false
  }
}

function playRecording() {
  if (!recorder.url.value) return
  const a = new Audio(recorder.url.value)
  a.play()
  emit('toast', { text: '▶ 回放', type: 'info', duration: 1000 })
}

async function toggleRecord() {
  if (recorder.recording.value) {
    recorder.stop()
    emit('toast', { text: '⏹ 已停止', type: 'info', duration: 1200 })
  } else {
    recorder.reset()
    await recorder.start()
    if (!recorder.error.value) {
      emit('toast', { text: '🎤 录音中...', type: 'info', duration: 1500 })
    }
  }
}

async function rate(level) {
  if (!currentCard.value?.id || ratingBusy.value) return
  ratingBusy.value = true
  try {
    await rateCard(currentCard.value.id, level)
    store.markPracticed(store.currentIdx, level)
    emit('rated', { idx: store.currentIdx, level })
    emit('toast', { text: `✅ 已评 ${_labelOf(level)}`, type: 'success', duration: 1200 })
    // 自动跳下一句
    if (store.currentIdx < store.segments.length - 1) {
      setTimeout(() => store.setCurrentIdx(store.currentIdx + 1), 400)
    }
  } catch (err) {
    emit('toast', { text: err.message || '评分失败', type: 'error' })
  } finally {
    ratingBusy.value = false
  }
}

function _labelOf(level) {
  return { again: 'Again', hard: 'Hard', good: 'Good', easy: 'Easy' }[level] || level
}

function onSentenceExplain() {
  if (segment.value) {
    emit('explain', { type: 'sentence', content: segment.value.content })
  }
}

function onWordExplain(word) {
  if (!word) return
  emit('explain', {
    type: 'word',
    content: word.trim(),
    sentence: segment.value?.content || '',
  })
}

function onQueryExplain() {
  const w = wordQuery.value.trim()
  if (!w) return
  onWordExplain(w)
  wordQuery.value = ''
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

// 换句时清 TTS/录音
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
      <!-- 句子 + 解读 -->
      <header class="text-box">
        <p class="sentence">{{ segment.content }}</p>
        <button class="explain" @click="onSentenceExplain" aria-label="解读整句">
          💡 解读整句
        </button>
      </header>

      <!-- 单词解读入口 -->
      <section v-if="words.length" class="word-row">
        <p class="hint">想查哪个词？点下面或直接输入：</p>
        <div class="words">
          <button
            v-for="w in words"
            :key="w"
            class="word-chip"
            @click="onWordExplain(w)"
          >
            {{ w }}
          </button>
        </div>
        <div class="word-input">
          <input
            v-model="wordQuery"
            placeholder="输入其它单词..."
            @keydown.enter="onQueryExplain"
          />
          <button class="btn-mini" :disabled="!wordQuery.trim()" @click="onQueryExplain">
            查
          </button>
        </div>
      </section>

      <!-- 播放 / 录音 -->
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
            <span v-if="ttsLoading" class="spin">⏳</span>
            <span v-else>🔊 原音</span>
          </button>
          <button
            class="btn record"
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
        <p v-if="recorder.error.value" class="err">{{ recorder.error.value }}</p>
      </section>

      <!-- 评分 -->
      <section class="rating">
        <p v-if="cardLoading" class="hint">卡片准备中...</p>
        <p v-else-if="!currentCard" class="hint">⚠ 卡片缺失 · 点任意句子重试</p>
        <template v-else>
          <p class="hint">练一次，给自己打分：</p>
          <div class="btn-row rate-row">
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
          <p v-if="ratingBusy" class="hint sub">保存中...</p>
        </template>
      </section>
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
  flex-wrap: wrap;
}
.sentence {
  flex: 1;
  min-width: 0;
  font-size: 18px;
  line-height: 1.6;
  color: var(--text-1);
  margin: 0;
  font-weight: 500;
}
.explain {
  flex-shrink: 0;
  padding: var(--space-2) var(--space-3);
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  transition: all var(--duration) var(--ease);
}
.explain:active {
  background: var(--accent);
  color: var(--text-inverse);
  transform: scale(0.96);
}

.word-row {
  padding: var(--space-3);
  background: var(--bg);
  border-radius: var(--radius-sm);
}
.hint {
  font-size: 12px;
  color: var(--text-3);
  margin: 0 0 var(--space-2);
}
.hint.sub {
  margin-top: var(--space-2);
  text-align: center;
}
.words {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: var(--space-3);
}
.word-chip {
  padding: 6px var(--space-3);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 13px;
  color: var(--text-1);
  transition: all 0.12s var(--ease);
  /* 关键：消除 iOS 300ms tap 延迟 · 防止 double-tap-zoom */
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  /* 保证点击区够大，移动端 40px 最小 */
  min-height: 36px;
}
.word-chip:active {
  background: var(--accent);
  color: var(--text-inverse);
  border-color: var(--accent);
  transform: scale(0.92);
}
.word-input {
  display: flex;
  gap: var(--space-2);
}
.word-input input {
  flex: 1;
  padding: 6px var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 14px;
  background: var(--bg-elevated);
  outline: none;
}
.word-input input:focus {
  border-color: var(--accent);
}
.btn-mini {
  padding: 0 var(--space-3);
  background: var(--accent);
  color: var(--text-inverse);
  border-radius: var(--radius-sm);
  font-size: 13px;
  transition: background var(--duration) var(--ease);
}
.btn-mini:active {
  background: var(--accent-hover);
}
.btn-mini:disabled {
  opacity: 0.4;
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
  transition: all var(--duration) var(--ease);
}
.btn:active {
  transform: scale(0.94);
  background: var(--bg);
}
.btn:disabled {
  opacity: 0.5;
  transform: none;
}
.btn.primary {
  background: var(--accent);
  color: var(--text-inverse);
  border-color: var(--accent);
}
.btn.primary:active {
  background: var(--accent-hover);
}
.btn.record.recording {
  background: #c6463a;
  color: var(--text-inverse);
  border-color: #c6463a;
  animation: record-pulse 1s infinite;
}
@keyframes record-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(198, 70, 58, 0.4); }
  50% { box-shadow: 0 0 0 6px transparent; }
}
.spin {
  display: inline-block;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

.rating {
  padding-top: var(--space-3);
  border-top: 1px dashed var(--border);
}
.rate-row {
  gap: var(--space-2);
}
.rate {
  font-weight: 500;
}
/* 评分按钮 · 饱和色彰显可用 · 不再像 disabled */
.rate-again { background: #c6463a; color: #fff; border-color: #c6463a; }
.rate-hard  { background: #d69e2e; color: #fff; border-color: #d69e2e; }
.rate-good  { background: var(--accent); color: #fff; border-color: var(--accent); }
.rate-easy  { background: #2f7a40; color: #fff; border-color: #2f7a40; }
.rate:active {
  filter: brightness(0.88);
  transform: scale(0.95);
}
.rate:disabled {
  filter: grayscale(0.4) brightness(0.85);
}
.err {
  color: #c6463a;
  font-size: 12px;
  margin: 0;
}
</style>
