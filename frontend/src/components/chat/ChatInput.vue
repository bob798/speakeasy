<script setup>
/**
 * ChatInput · 底部输入栏
 * Phase 2a 文字发送 · Phase 2b 接入 mic 按钮和倒计时环
 * 迁移自 static/index.html:1244-1280
 */
import { ref, watch } from 'vue'

const props = defineProps({
  placeholder: { type: String, default: '说点什么... (Shift+Enter 换行)' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['send'])

const text = ref('')
const textarea = ref(null)

function autoGrow() {
  const el = textarea.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 180) + 'px'
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

defineExpose({ focus: () => textarea.value?.focus() })
</script>

<template>
  <form class="input-bar" @submit.prevent="submit">
    <textarea
      ref="textarea"
      v-model="text"
      :placeholder="placeholder"
      :disabled="disabled"
      rows="1"
      @keydown="onKeydown"
    ></textarea>
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
}
textarea {
  flex: 1;
  min-height: 40px;
  max-height: 180px;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 16px;
  line-height: 1.5;
  resize: none;
  background: var(--bg-elevated);
  color: var(--text-1);
  outline: none;
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
  transform: scale(0.92);
}
.send:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
</style>
