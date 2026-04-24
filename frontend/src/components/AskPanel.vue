<script setup>
/**
 * AskPanel.vue · V0.7 通用追问组件 Vue 重写
 * 契约保持与 ask-panel.js 一致（scope/refType/refId/contextPayload/placeholder/emptyHint）
 * DOM 操作彻底重写为响应式模板
 *
 * 用法：
 *   <AskPanel scope="practice_explain" ref-type="explanation" ref-id="abc"
 *             :context-payload="{ sentence }" @error="onErr" />
 */
import { ref, onMounted, nextTick, useTemplateRef } from 'vue'
import { useAskThread } from '@/composables/useAskThread'

const props = defineProps({
  scope: { type: String, required: true },
  refType: { type: String, required: true },
  refId: { type: [String, Number], required: true },
  contextPayload: { type: Object, default: () => ({}) },
  placeholder: { type: String, default: '问点什么…' },
  emptyHint: { type: String, default: '还没有追问，先问一个吧' },
  autoLoad: { type: Boolean, default: true },
})

defineEmits(['error'])

const { messages, busy, error, loadExisting, ask } = useAskThread({
  scope: props.scope,
  refType: props.refType,
  refId: props.refId,
  contextPayload: props.contextPayload,
})

const input = ref('')
const msgsBox = useTemplateRef('msgsBox')
const textareaEl = useTemplateRef('textareaEl')

async function onSend() {
  const v = input.value.trim()
  if (!v || busy.value) return
  input.value = ''
  autoGrow()
  await ask(v)
  await nextTick()
  scrollBottom()
}

function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    onSend()
  }
}

function autoGrow() {
  const el = textareaEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 100) + 'px'
}

function scrollBottom() {
  const el = msgsBox.value
  if (el) el.scrollTop = el.scrollHeight
}

onMounted(async () => {
  if (props.autoLoad) {
    await loadExisting()
    await nextTick()
    scrollBottom()
  }
})

defineExpose({ ask, reset: () => (input.value = '') })
</script>

<template>
  <div class="ap-root">
    <div ref="msgsBox" class="ap-messages">
      <div v-if="!messages.length" class="ap-empty">{{ emptyHint }}</div>
      <div
        v-for="(m, i) in messages"
        :key="i"
        class="ap-msg"
        :class="m.role"
      >
        <div class="ap-role">{{ m.role === 'user' ? 'You' : 'Tutor' }}</div>
        <div class="ap-bubble" :class="{ pending: m.pending }">{{ m.content }}</div>
      </div>
      <div v-if="error" class="ap-error">❌ {{ error }}</div>
    </div>
    <form class="ap-inputbar" @submit.prevent="onSend">
      <textarea
        ref="textareaEl"
        v-model="input"
        class="ap-input"
        :placeholder="placeholder"
        rows="1"
        :disabled="busy"
        @keydown="onKeydown"
        @input="autoGrow"
      ></textarea>
      <button type="submit" class="ap-send" :disabled="!input.trim() || busy">发送</button>
    </form>
  </div>
</template>

<style scoped>
.ap-root {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--bg-elevated);
}
.ap-messages {
  flex: 1;
  overflow-y: auto;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ap-empty {
  color: var(--text-3);
  font-size: 12px;
  text-align: center;
  padding: 18px 6px;
}
.ap-msg {
  display: flex;
  flex-direction: column;
  max-width: 92%;
  word-wrap: break-word;
}
.ap-msg.user {
  align-self: flex-end;
}
.ap-msg.assistant {
  align-self: flex-start;
}
.ap-bubble {
  padding: 8px 12px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
}
.ap-msg.user .ap-bubble {
  background: var(--accent-soft);
  color: var(--text-1);
  border-bottom-right-radius: 3px;
}
.ap-msg.assistant .ap-bubble {
  background: var(--bg);
  color: var(--text-1);
  border-bottom-left-radius: 3px;
}
.ap-role {
  font-size: 10px;
  color: var(--text-3);
  margin-bottom: 2px;
  letter-spacing: 0.5px;
}
.ap-msg.user .ap-role {
  text-align: right;
}
.ap-bubble.pending {
  opacity: 0.6;
  font-style: italic;
}
.ap-error {
  color: #b0403a;
  background: rgba(176, 64, 58, 0.1);
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 12px;
}
.ap-inputbar {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  border-top: 1px solid var(--border);
  background: var(--bg-elevated);
}
.ap-input {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  background: var(--bg);
  color: var(--text-1);
  resize: none;
  min-height: 36px;
  max-height: 100px;
}
.ap-input:focus {
  outline: none;
  border-color: var(--accent);
}
.ap-input:disabled {
  opacity: 0.6;
}
.ap-send {
  padding: 0 14px;
  border-radius: 8px;
  background: var(--accent);
  color: var(--text-inverse);
  font-size: 13px;
  font-weight: 500;
  transition: opacity var(--duration) var(--ease);
}
.ap-send:active {
  opacity: 0.8;
}
.ap-send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
