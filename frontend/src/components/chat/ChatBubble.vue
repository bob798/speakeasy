<script setup>
/**
 * ChatBubble · 单条消息气泡
 * 迁移自 static/index.html:991-1076 的气泡样式
 * props: { role, content, streaming }
 * emits: tts-request（Phase 2b 接入自动朗读 + 解读弹窗）
 */
import { computed } from 'vue'

const props = defineProps({
  role: { type: String, required: true }, // 'user' | 'assistant' | 'system'
  content: { type: String, default: '' },
  streaming: { type: Boolean, default: false },
})

defineEmits(['tts-request', 'explain-request'])

const isUser = computed(() => props.role === 'user')
const showLoading = computed(() => props.streaming && !props.content)
</script>

<template>
  <div class="bubble" :class="[isUser ? 'user' : 'ai']">
    <div class="avatar" v-if="!isUser">🤖</div>
    <div class="body">
      <div v-if="showLoading" class="loading">
        <span></span><span></span><span></span>
      </div>
      <div v-else class="content">{{ content }}<span v-if="streaming" class="cursor">▋</span></div>
      <button
        v-if="!isUser && !streaming && content"
        class="tts-btn"
        @click="$emit('tts-request', content)"
        aria-label="朗读"
        title="朗读"
      >
        🔊
      </button>
    </div>
  </div>
</template>

<style scoped>
.bubble {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  padding: 0 var(--space-4);
  align-items: flex-end;
}
.bubble.user {
  flex-direction: row-reverse;
}
.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--accent-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}
.body {
  max-width: 72%;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  line-height: 1.55;
  word-break: break-word;
  position: relative;
}
.bubble.user .body {
  background: var(--accent);
  color: var(--text-inverse);
  border-bottom-right-radius: var(--radius-sm);
}
.bubble.ai .body {
  background: var(--bg-elevated);
  color: var(--text-1);
  border: 1px solid var(--border);
  border-bottom-left-radius: var(--radius-sm);
}
.content {
  white-space: pre-wrap;
}
.cursor {
  display: inline-block;
  margin-left: 2px;
  opacity: 0.6;
  animation: blink 1s step-end infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}
.loading {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}
.loading span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-3);
  animation: bounce 1.4s infinite ease-in-out both;
}
.loading span:nth-child(1) { animation-delay: -0.32s; }
.loading span:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
.tts-btn {
  position: absolute;
  bottom: -4px;
  right: -4px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  font-size: 11px;
  opacity: 0;
  transition: opacity var(--duration) var(--ease);
}
/* 触屏始终显示；桌面 hover 才显示 */
.bubble.ai:active .tts-btn,
.bubble.ai.show-tts .tts-btn {
  opacity: 1;
}
@media (hover: hover) {
  .bubble.ai:hover .tts-btn {
    opacity: 1;
  }
}
</style>
