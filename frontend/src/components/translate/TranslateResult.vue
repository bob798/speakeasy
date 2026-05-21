<script setup>
/**
 * TranslateResult · 右栏译文区
 * - 译文展示 + loading 状态 + stale 提示 + toolbar placeholder + vocab 状态行
 */

defineProps({
  text: {
    type: String,
    default: '',
  },
  loading: {
    type: Boolean,
    default: false,
  },
  savedToVocab: {
    type: Boolean,
    default: false,
  },
  isAuthenticated: {
    type: Boolean,
    default: false,
  },
  stale: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
  direction: {
    type: String,
    default: 'zh2en',
  },
})
</script>

<template>
  <div class="result-panel">
    <div class="panel-header">
      <span class="lang-badge">
        {{ direction === 'zh2en' ? 'English' : '中文' }}
      </span>
      <!-- Toolbar placeholder: word interaction and TTS come in PR2/PR3 -->
      <div class="toolbar-placeholder"></div>
    </div>

    <div class="result-body">
      <!-- Loading state -->
      <div v-if="loading" class="state-placeholder loading" aria-live="polite">
        <span class="loading-dots">翻译中</span>
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="state-placeholder error">
        {{ error }}
      </div>

      <!-- Stale indicator (direction was swapped) -->
      <div v-else-if="stale && text" class="stale-banner" role="status">
        已切换方向，结果仅供参考，请重新翻译
      </div>

      <!-- Result text -->
      <div
        v-if="text && !loading"
        class="result-text"
        :class="{ stale }"
        aria-label="译文"
      >{{ text }}</div>

      <!-- Empty placeholder -->
      <div v-if="!text && !loading && !error" class="state-placeholder empty">
        译文会显示在这里
      </div>
    </div>

    <!-- Footer: vocab status -->
    <div v-if="text && !loading" class="footer">
      <span v-if="savedToVocab" class="vocab-saved">⭐ 已自动加入生词本</span>
    </div>
  </div>
</template>

<style scoped>
.result-panel {
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
  justify-content: space-between;
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

.toolbar-placeholder {
  height: 20px;
}

.result-body {
  flex: 1;
  padding: var(--space-3);
  overflow-y: auto;
  position: relative;
}

.result-text {
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-1);
  white-space: pre-wrap;
  word-break: break-word;
}

.result-text.stale {
  opacity: 0.6;
}

.state-placeholder {
  font-size: 14px;
  color: var(--text-3);
}

.state-placeholder.empty {
  font-style: italic;
}

.state-placeholder.loading {
  font-style: italic;
}

.loading-dots::after {
  content: '';
  animation: dots 1.2s steps(3, end) infinite;
}

@keyframes dots {
  0%   { content: ''; }
  33%  { content: '.'; }
  66%  { content: '..'; }
  100% { content: '...'; }
}

.state-placeholder.error {
  color: #c6463a;
}

.stale-banner {
  font-size: 12px;
  color: #e67e22;
  background: color-mix(in srgb, #e67e22 10%, transparent);
  border: 1px solid color-mix(in srgb, #e67e22 30%, transparent);
  border-radius: var(--radius-sm);
  padding: var(--space-1) var(--space-2);
  margin-bottom: var(--space-2);
}

.footer {
  padding: var(--space-2) var(--space-3);
  border-top: 1px solid var(--border);
  background: var(--bg);
  min-height: 32px;
}

.vocab-saved {
  font-size: 12px;
  color: var(--accent);
}
</style>
