<script setup>
/**
 * SubtitleImport · B站 URL / 手动文本 / 历史字幕源
 * 迁移自 practice.html:535-618
 */
import { ref, onMounted } from 'vue'
import { usePractice } from '@/composables/usePractice'

const emit = defineEmits(['imported'])

const { importSubtitles, listSources, getSource } = usePractice()

const mode = ref('url') // url | manual
const url = ref('')
const manualText = ref('')
const cookies = ref('')
const showCookiesRetry = ref(false)
const submitting = ref(false)
const status = ref('')
const statusError = ref(false)

const history = ref([])
const historyOpen = ref(false)

async function onImport(useCookies = false) {
  if (submitting.value) return
  submitting.value = true
  status.value = '提取中... (B站可能要 10-30 秒)'
  statusError.value = false
  showCookiesRetry.value = false

  try {
    let payload = {}
    if (mode.value === 'url') {
      if (!url.value.trim()) {
        status.value = '请输入视频链接'
        statusError.value = true
        return
      }
      payload.url = url.value.trim()
      if (useCookies && cookies.value.trim()) {
        payload.cookies = cookies.value.trim()
      }
    } else {
      if (!manualText.value.trim()) {
        status.value = '请粘贴文本'
        statusError.value = true
        return
      }
      payload.text = manualText.value.trim()
    }

    const data = await importSubtitles(payload)

    // 后端 error 字段处理（无字幕、Whisper 失败、IP 被封等）
    if (data.error) {
      const msg = String(data.error)
      // B 站登录态保护错误兜底（cookies 重试）
      if (
        /412|登录|cookie/i.test(msg) ||
        msg.includes('登录态')
      ) {
        showCookiesRetry.value = true
        status.value = '需要登录态：请粘贴浏览器 cookies 后重试'
      } else {
        status.value = msg
      }
      statusError.value = true
      return  // ← 关键：不 emit imported，不让父级切到二栏
    }

    if (!data.segments || !data.segments.length) {
      status.value = '没有抓到任何字幕段，可手动粘贴文本'
      statusError.value = true
      return
    }

    status.value = `✅ 已导入 ${data.segments.length} 段字幕`
    emit('imported', data)
  } catch (err) {
    status.value = err.message || '提取失败'
    statusError.value = true
  } finally {
    submitting.value = false
  }
}

async function loadHistory() {
  try {
    const data = await listSources(10)
    history.value = data.sources || data.items || []
  } catch {
    /* 静默 */
  }
}

async function pickHistory(sourceId) {
  try {
    const src = await getSource(sourceId)
    historyOpen.value = false
    emit('imported', src)
  } catch (err) {
    status.value = err.message
    statusError.value = true
  }
}

onMounted(loadHistory)

defineExpose({ refreshHistory: loadHistory })
</script>

<template>
  <div class="import-panel">
    <div class="tabs">
      <button
        class="tab"
        :class="{ active: mode === 'url' }"
        @click="mode = 'url'"
      >
        视频链接
      </button>
      <button
        class="tab"
        :class="{ active: mode === 'manual' }"
        @click="mode = 'manual'"
      >
        粘贴文本
      </button>
      <button class="hist-btn" @click="historyOpen = !historyOpen" aria-label="历史">
        📚 {{ history.length }}
      </button>
    </div>

    <div v-if="mode === 'url'" class="field">
      <input
        v-model="url"
        placeholder="B站 / YouTube 视频链接"
        autocomplete="off"
      />
    </div>

    <div v-else class="field">
      <textarea
        v-model="manualText"
        placeholder="一行一句粘贴英文字幕"
        rows="4"
      ></textarea>
    </div>

    <button
      class="primary"
      :disabled="submitting"
      @click="onImport(false)"
    >
      {{ submitting ? '提取中...' : '提取' }}
    </button>

    <div v-if="showCookiesRetry" class="cookies-box">
      <input v-model="cookies" placeholder="粘贴 Netscape 格式 cookies 文本" />
      <button class="secondary" @click="onImport(true)">用 cookies 重试</button>
    </div>

    <p v-if="status" class="status" :class="{ error: statusError }">{{ status }}</p>

    <Transition name="fade">
      <div v-if="historyOpen" class="history">
        <h4>历史字幕源</h4>
        <ul v-if="history.length">
          <li
            v-for="s in history"
            :key="s.id"
            @click="pickHistory(s.id)"
          >
            <span class="title">{{ s.title || '(未命名)' }}</span>
            <span class="meta">{{ s.segment_count || 0 }} 段</span>
          </li>
        </ul>
        <p v-else class="empty">暂无历史</p>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.import-panel {
  padding: var(--space-4);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.tabs {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  align-items: center;
}
.tab {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  color: var(--text-2);
  font-size: 13px;
}
.tab.active {
  background: var(--accent-soft);
  color: var(--accent);
}
.hist-btn {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-3);
}
.field {
  margin-bottom: var(--space-3);
}
input,
textarea {
  width: 100%;
  padding: var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--text-1);
  font-size: 14px;
  outline: none;
}
input:focus,
textarea:focus {
  border-color: var(--accent);
}
textarea {
  resize: vertical;
}
.primary {
  width: 100%;
  padding: var(--space-3);
  background: var(--accent);
  color: var(--text-inverse);
  border-radius: var(--radius-sm);
  font-weight: 500;
}
.primary:active {
  background: var(--accent-hover);
}
.primary:disabled {
  opacity: 0.6;
}
.secondary {
  padding: var(--space-2) var(--space-3);
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: var(--radius-sm);
  font-size: 13px;
}
.cookies-box {
  margin-top: var(--space-3);
  display: flex;
  gap: var(--space-2);
}
.cookies-box input {
  flex: 1;
}
.status {
  margin: var(--space-3) 0 0;
  font-size: 13px;
  color: var(--text-3);
}
.status.error {
  color: #c6463a;
}
.history {
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px dashed var(--border);
}
.history h4 {
  margin: 0 0 var(--space-2);
  font-size: 12px;
  color: var(--text-3);
  letter-spacing: 0.5px;
}
.history ul {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 200px;
  overflow-y: auto;
}
.history li {
  padding: var(--space-2) var(--space-3);
  display: flex;
  justify-content: space-between;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
}
.history li:active {
  background: var(--accent-soft);
}
.title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  margin-right: var(--space-2);
}
.meta {
  color: var(--text-3);
  font-size: 11px;
  flex-shrink: 0;
}
.empty {
  color: var(--text-3);
  font-size: 12px;
  padding: var(--space-3);
  text-align: center;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration) var(--ease),
    max-height var(--duration) var(--ease);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
