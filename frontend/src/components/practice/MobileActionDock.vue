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
