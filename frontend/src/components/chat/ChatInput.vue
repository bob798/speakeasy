<script setup>
/**
 * ChatInput · V0.9.3 修
 *   - textarea autoGrow 正确渲染（之前 flex:1 冲突导致高度不变）
 *   - 移动键盘 · focus 时 scrollIntoView({block:'end'}) 避免被键盘盖住
 *   - VisualViewport 监听键盘弹出 · 顶到可视底部
 */
import { ref, watch, useTemplateRef, onMounted, onBeforeUnmount } from 'vue'
import MicButton from './MicButton.vue'

const props = defineProps({
  placeholder: { type: String, default: '说点什么... (Shift+Enter 换行)' },
  disabled: { type: Boolean, default: false },
  enableStt: { type: Boolean, default: true },
})
const emit = defineEmits(['send', 'stt-error'])

const text = ref('')
const interim = ref('')
const textarea = useTemplateRef('textarea')
const micRef = useTemplateRef('micRef')
const barRef = useTemplateRef('barRef')

function autoGrow() {
  const el = textarea.value
  if (!el) return
  el.style.height = 'auto'
  const next = Math.min(el.scrollHeight, 180)
  el.style.height = next + 'px'
}

watch(text, autoGrow, { flush: 'post' })

function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    submit()
  }
}

function submit() {
  const v = text.value.trim()
  if (!v || props.disabled) return
  emit('send', v)
  text.value = ''
  autoGrow()
}

function onRecognized(recognized) {
  const clean = recognized.trim()
  if (!clean) return
  emit('send', clean)
}

function onSTTError(msg) {
  interim.value = ''
  emit('stt-error', msg)
}

// 移动键盘 · iOS/Android 键盘弹出时让输入框露出来
function onFocus() {
  setTimeout(() => {
    const el = barRef.value
    if (!el) return
    el.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }, 350) // 等键盘动画
}

// iOS VisualViewport 键盘事件 · 实时调整底部偏移
function onViewportResize() {
  const vv = window.visualViewport
  if (!vv || !barRef.value) return
  const bottomGap = window.innerHeight - vv.height - vv.offsetTop
  // 键盘弹出时 bottomGap > 0，把输入栏往上推
  barRef.value.style.transform = bottomGap > 50 ? `translateY(-${bottomGap}px)` : ''
}

onMounted(() => {
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', onViewportResize)
    window.visualViewport.addEventListener('scroll', onViewportResize)
  }
})

onBeforeUnmount(() => {
  if (window.visualViewport) {
    window.visualViewport.removeEventListener('resize', onViewportResize)
    window.visualViewport.removeEventListener('scroll', onViewportResize)
  }
})

defineExpose({
  focus: () => textarea.value?.focus(),
  triggerMic: () => micRef.value?.triggerStart(),
  isMicIdle: () => micRef.value?.isIdle?.() ?? true,
})
</script>

<template>
  <form ref="barRef" class="input-bar" @submit.prevent="submit">
    <MicButton
      v-if="enableStt"
      ref="micRef"
      @recognized="onRecognized"
      @error="onSTTError"
      @interim="interim = $event"
    />
    <div class="text-col">
      <div v-if="interim" class="interim">{{ interim }}</div>
      <textarea
        ref="textarea"
        v-model="text"
        :placeholder="placeholder"
        :disabled="disabled"
        rows="1"
        @keydown="onKeydown"
        @focus="onFocus"
        @input="autoGrow"
      ></textarea>
    </div>
    <button
      type="submit"
      class="send"
      :disabled="!text.trim() || disabled"
      aria-label="发送"
    >
      ↑
    </button>
  </form>
</template>

<style scoped>
.input-bar {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  padding-bottom: calc(var(--space-3) + var(--safe-bottom));
  background: var(--bg-overlay);
  backdrop-filter: saturate(180%) blur(16px);
  border-top: 1px solid var(--border);
  align-items: flex-end;
  position: sticky;
  bottom: 0;
  transition: transform 0.2s var(--ease);
  will-change: transform;
  z-index: 5;
}
.text-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.interim {
  padding: 2px var(--space-2);
  font-size: 12px;
  color: var(--text-3);
  font-style: italic;
}
textarea {
  /* 关键：不要 flex:1，让 height 由 JS 控制 */
  width: 100%;
  min-height: 40px;
  max-height: 180px;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 16px;            /* 16px 防 iOS 自动缩放 */
  line-height: 1.5;
  resize: none;
  background: var(--bg-elevated);
  color: var(--text-1);
  outline: none;
  overflow-y: auto;
  box-sizing: border-box;
  font-family: inherit;
}
textarea:focus {
  border-color: var(--accent);
}
textarea:disabled {
  opacity: 0.5;
}
.send {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--accent);
  color: var(--text-inverse);
  font-size: 18px;
  font-weight: 600;
  flex-shrink: 0;
  transition: transform var(--duration) var(--ease),
    opacity var(--duration) var(--ease);
}
.send:active {
  transform: scale(0.9);
  background: var(--accent-hover);
}
.send:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
</style>
