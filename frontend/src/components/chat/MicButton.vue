<script setup>
/**
 * MicButton · STT 录音按钮 + 倒计时环
 * 组合 useSTT + useCountdown · 替代 static/js/app.js:219-299 的 onMicClick 状态机
 *
 * emits:
 *   recognized(text)  · STT 最终结果
 *   error(msg)        · 用户可感知的错误
 *   interim(text)     · 可选：实时识别中文字（Phase 2b+ 可接 ChatInput）
 */
import { ref, computed, onBeforeUnmount } from 'vue'
import { useSTT } from '@/composables/useSTT'
import { useCountdown } from '@/composables/useCountdown'

const emit = defineEmits(['recognized', 'error', 'interim'])

const stt = useSTT()
const countdown = useCountdown()

const state = ref('idle') // idle | recording | processing
const generation = ref(0)

const cssState = computed(() => `state-${state.value}`)
const countdownPct = computed(() =>
  countdown.active.value && countdown.remainingMs.value > 0
    ? Math.max(0, Math.min(100, (1 - countdown.remainingMs.value / 3000) * 100))
    : 0
)

function setState(next) {
  state.value = next
}

function onClick() {
  if (state.value === 'idle') _startRecording()
  else if (state.value === 'recording') _stopRecording()
  else if (state.value === 'processing') _cancel()
}

function _startRecording() {
  if (!stt.isSupported()) {
    emit('error', '浏览器不支持录音或需要 HTTPS')
    return
  }
  const gen = ++generation.value
  setState('recording')

  stt.start({
    onInterim: (txt) => {
      if (generation.value !== gen) return
      emit('interim', txt)
    },
    onFinal: (text) => {
      if (generation.value !== gen) return
      setState('idle')
      countdown.stop()
      emit('interim', '')
      emit('recognized', text)
    },
    onError: (err) => {
      if (generation.value !== gen) return
      setState('idle')
      countdown.stop()
      emit('interim', '')
      switch (err.type) {
        case 'PERMISSION_DENIED':
          emit('error', '请在浏览器设置中允许麦克风权限')
          break
        case 'EMPTY':
          emit('error', '没有检测到语音，请再试')
          break
        case 'FALLBACK':
          emit('error', '语音服务暂不可用，已切换到浏览器内置方案')
          break
        case 'NETWORK':
          emit('error', '网络错误，请检查连接')
          break
        default:
          emit('error', err.message || '识别失败，请重试')
      }
    },
    onCountdownStart: (ms, done) => {
      countdown.start(ms, done)
    },
    onCountdownCancel: () => {
      countdown.stop()
    },
  })
}

function _stopRecording() {
  setState('processing')
  stt.stop()
  // 10s 超时兜底
  const safeGen = generation.value
  setTimeout(() => {
    if (state.value === 'processing' && generation.value === safeGen) {
      ++generation.value
      setState('idle')
      emit('error', '识别超时，请重试')
    }
  }, 10000)
}

function _cancel() {
  ++generation.value
  stt.cancel()
  countdown.stop()
  setState('idle')
  emit('interim', '')
}

onBeforeUnmount(() => {
  stt.cancel()
  countdown.stop()
})
</script>

<template>
  <button
    type="button"
    class="mic"
    :class="cssState"
    :aria-label="state === 'idle' ? '开始录音' : state === 'recording' ? '停止录音' : '处理中'"
    @click="onClick"
  >
    <svg
      v-if="state !== 'processing'"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 1 0 6 0V5a3 3 0 0 0-3-3z"/>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
      <line x1="12" y1="19" x2="12" y2="22"/>
    </svg>
    <svg
      v-else
      class="spinner"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2.5"
      stroke-linecap="round"
    >
      <path d="M12 2a10 10 0 0 1 10 10" />
    </svg>
    <!-- 倒计时环：静音 2s 后 3s 倒计时触发自动 stop -->
    <svg
      v-if="countdown.active.value"
      class="countdown-ring"
      viewBox="0 0 36 36"
      aria-hidden="true"
    >
      <circle
        class="ring-bg"
        cx="18"
        cy="18"
        r="15"
        fill="none"
        stroke-width="2"
      />
      <circle
        class="ring-fg"
        cx="18"
        cy="18"
        r="15"
        fill="none"
        stroke-width="2"
        stroke-linecap="round"
        :stroke-dasharray="`${countdownPct * 0.942} 100`"
      />
    </svg>
  </button>
</template>

<style scoped>
.mic {
  position: relative;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--text-2);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background var(--duration) var(--ease), color var(--duration) var(--ease);
}
.mic:active {
  transform: scale(0.92);
}
.mic.state-recording {
  background: var(--accent);
  color: var(--text-inverse);
  border-color: var(--accent);
  animation: pulse 1.2s ease-in-out infinite;
}
.mic.state-processing {
  background: var(--accent-soft);
  color: var(--accent);
  border-color: var(--accent);
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--accent-soft); }
  50% { box-shadow: 0 0 0 8px transparent; }
}
.spinner {
  animation: spin 0.9s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.countdown-ring {
  position: absolute;
  inset: -3px;
  width: calc(100% + 6px);
  height: calc(100% + 6px);
  pointer-events: none;
  transform: rotate(-90deg);
}
.ring-bg {
  stroke: var(--border);
  opacity: 0.3;
}
.ring-fg {
  stroke: var(--accent);
  transition: stroke-dasharray 60ms linear;
}
</style>
