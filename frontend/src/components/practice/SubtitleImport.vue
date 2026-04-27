<script setup>
/**
 * SubtitleImport · V0.9.5 重设计
 *   - 历史列表默认可见（chip 横滑条 · 不再隐藏到 📚 按钮后）
 *   - 错误状态正确处理（不静默切到二栏空白）
 *   - 4 段示例库（带文案）一键导入
 */
import { ref, onMounted } from 'vue'
import { usePractice } from '@/composables/usePractice'
import { getErrorMessage } from '@/composables/useAuthFetch'

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
const historyLoading = ref(false)

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

    if (data.error) {
      const msg = String(data.error)
      if (/412|登录|cookie/i.test(msg) || msg.includes('登录态')) {
        showCookiesRetry.value = true
        status.value = '需要登录态：请粘贴浏览器 cookies 后重试'
      } else {
        status.value = msg
      }
      statusError.value = true
      return
    }

    if (!data.segments || !data.segments.length) {
      status.value = '没有抓到任何字幕段，可手动粘贴文本'
      statusError.value = true
      return
    }

    status.value = `✅ 已导入 ${data.segments.length} 段字幕`
    emit('imported', data)
  } catch (err) {
    const msg = getErrorMessage(err, '提取失败')
    if (msg) {
      status.value = msg
      statusError.value = true
    }
  } finally {
    submitting.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const data = await listSources(20)
    history.value = data.items || data.sources || []
  } catch {
    /* 静默 */
  } finally {
    historyLoading.value = false
  }
}

async function pickHistory(sourceId) {
  try {
    const src = await getSource(sourceId)
    src.id = sourceId  // 确保 id 存在，PracticePlayer cardBySegIdx 用
    emit('imported', src)
  } catch (err) {
    const msg = getErrorMessage(err)
    if (msg) {
      status.value = msg
      statusError.value = true
    }
  }
}

function loadSample() {
  manualText.value = `Hold tight please!
This is Anna, on a bus going to an interview for a job as a sales executive at Tip Top Trading.
How are you feeling Anna?
Oh, a little nervous but I really want this job.
Well don't worry Anna, as long as you say the right things, you'll be fine.
The right things? Like what?
You need to sell yourself, be confident, not arrogant and give examples.
A good example that comes to mind.
I'm particularly proud of.
Timekeeping is important to me.`
  mode.value = 'manual'
  status.value = '已填示例 · 点击下方"提取"开始练习'
  statusError.value = false
}

onMounted(loadHistory)

defineExpose({ refreshHistory: loadHistory })
</script>

<template>
  <div class="import-panel">
    <!-- 历史列表 · 默认可见 -->
    <section v-if="history.length" class="history-row">
      <h4>历史字幕 · 点击重新练习</h4>
      <div class="history-chips">
        <button
          v-for="s in history"
          :key="s.id"
          class="hist-chip"
          @click="pickHistory(s.id)"
        >
          <span class="kind">{{ s.source_type === 'manual' ? '📋' : (s.source_type === 'youtube' ? '🎬' : '📺') }}</span>
          <span class="title">{{ s.title || '(未命名)' }}</span>
        </button>
      </div>
    </section>

    <h4 v-if="history.length" class="new-import-h">新导入</h4>

    <div class="tabs">
      <button class="tab" :class="{ active: mode === 'url' }" @click="mode = 'url'">
        视频链接
      </button>
      <button class="tab" :class="{ active: mode === 'manual' }" @click="mode = 'manual'">
        粘贴文本
      </button>
    </div>

    <div v-if="mode === 'url'" class="field">
      <input
        v-model="url"
        placeholder="B站 / YouTube 视频链接"
        autocomplete="off"
        @keydown.enter="onImport(false)"
      />
    </div>

    <div v-else class="field">
      <textarea
        v-model="manualText"
        placeholder="一行一句粘贴英文字幕"
        rows="6"
      ></textarea>
      <button class="link-btn" @click="loadSample">
        💡 试试示例（BBC English at Work · 10 句）
      </button>
    </div>

    <button class="primary" :disabled="submitting" @click="onImport(false)">
      {{ submitting ? '提取中...' : '提取字幕' }}
    </button>

    <div v-if="showCookiesRetry" class="cookies-box">
      <input v-model="cookies" placeholder="粘贴 Netscape 格式 cookies 文本" />
      <button class="secondary" @click="onImport(true)">用 cookies 重试</button>
    </div>

    <p v-if="status" class="status" :class="{ error: statusError }">{{ status }}</p>
  </div>
</template>

<style scoped>
.import-panel {
  padding: var(--space-4);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.history-row {
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: 1px dashed var(--border);
}
.history-row h4,
.new-import-h {
  margin: 0 0 var(--space-2);
  font-size: 11px;
  color: var(--text-3);
  letter-spacing: 0.5px;
  text-transform: uppercase;
  font-weight: 600;
}
.new-import-h {
  margin-top: var(--space-3);
}
.history-chips {
  display: flex;
  gap: var(--space-2);
  overflow-x: auto;
  padding-bottom: 4px;
  scrollbar-width: thin;
}
.history-chips::-webkit-scrollbar {
  height: 4px;
}
.hist-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px var(--space-3);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 13px;
  color: var(--text-1);
  white-space: nowrap;
  flex-shrink: 0;
  max-width: 220px;
  touch-action: manipulation;
  transition: all var(--duration) var(--ease);
}
.hist-chip:active {
  background: var(--accent-soft);
  transform: scale(0.96);
}
.hist-chip .kind {
  font-size: 14px;
  flex-shrink: 0;
}
.hist-chip .title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tabs {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
.tab {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  color: var(--text-2);
  font-size: 13px;
  background: var(--bg);
  transition: all var(--duration) var(--ease);
}
.tab.active {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 500;
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
  font-family: inherit;
}
input:focus,
textarea:focus {
  border-color: var(--accent);
}
textarea {
  resize: vertical;
}
.link-btn {
  display: block;
  margin-top: var(--space-2);
  padding: 4px 0;
  background: transparent;
  color: var(--accent);
  font-size: 12px;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.primary {
  width: 100%;
  padding: var(--space-3);
  background: var(--accent);
  color: var(--text-inverse);
  border-radius: var(--radius-sm);
  font-weight: 500;
  font-size: 14px;
  transition: background var(--duration) var(--ease);
  touch-action: manipulation;
}
.primary:active {
  background: var(--accent-hover);
  transform: scale(0.98);
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
</style>
