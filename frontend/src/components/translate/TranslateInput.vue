<script setup>
/**
 * TranslateInput · 左栏翻译输入区
 * - textarea + 字符计数 + 方向标签 badge
 */

const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  direction: {
    type: String,
    required: true,
  },
  maxLen: {
    type: Number,
    default: 1000,
  },
})

const emit = defineEmits(['update:modelValue'])

function onInput(e) {
  emit('update:modelValue', e.target.value)
}
</script>

<template>
  <div class="input-panel">
    <div class="panel-header">
      <span class="lang-badge">
        {{ direction === 'zh2en' ? '中文' : 'English' }}
      </span>
    </div>

    <textarea
      :value="modelValue"
      @input="onInput"
      :placeholder="direction === 'zh2en' ? '输入中文…' : 'Enter English…'"
      :maxlength="maxLen"
      class="source-textarea"
      aria-label="翻译输入框"
    ></textarea>

    <div class="footer">
      <span class="counter" :class="{ warn: modelValue.length > maxLen * 0.9 }">
        {{ modelValue.length }} / {{ maxLen }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.input-panel {
  display: flex;
  flex-direction: column;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  height: 100%;
  min-height: 320px;
}

.panel-header {
  display: flex;
  align-items: center;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}

.lang-badge {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-2);
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.source-textarea {
  flex: 1;
  width: 100%;
  padding: var(--space-3);
  border: none;
  background: transparent;
  font-size: 15px;
  line-height: 1.7;
  outline: none;
  resize: none;
  font-family: inherit;
  color: var(--text-1);
  min-height: 240px;
}

.source-textarea::placeholder {
  color: var(--text-3);
}

.input-panel:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 15%, transparent);
}

.footer {
  display: flex;
  justify-content: flex-end;
  padding: var(--space-2) var(--space-3);
  border-top: 1px solid var(--border);
  background: var(--bg);
}

.counter {
  font-size: 11px;
  color: var(--text-3);
}

.counter.warn {
  color: #e67e22;
}
</style>
