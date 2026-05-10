<script setup>
/**
 * SubtitleImport · V0.9.5 重设计
 *   - 历史列表默认可见（chip 横滑条 · 不再隐藏到 📚 按钮后）
 *   - 错误状态正确处理（不静默切到二栏空白）
 *   - 4 段示例库（带文案）一键导入
 */
import { ref, computed, onMounted } from 'vue'
import { useScrollLock } from '@/composables/useScrollLock'
import { usePractice } from '@/composables/usePractice'
import { getErrorMessage } from '@/composables/useAuthFetch'

const emit = defineEmits(['imported'])

const {
  importSubtitles,
  listSources,
  getSource,
  listEawEpisodes,
  getEawEpisode,
} = usePractice()

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
const eawEpisodes = ref([])
const eawLoading = ref(false)
const drawer = ref(null) // 'history' | 'eaw' | null
const drawerOpen = computed(() => !!drawer.value)
useScrollLock(drawerOpen)
const eawSearch = ref('')

const filteredEaw = computed(() => {
  const q = eawSearch.value.trim().toLowerCase()
  if (!q) return eawEpisodes.value
  return eawEpisodes.value.filter(
    (e) =>
      (e.title || '').toLowerCase().includes(q) ||
      (e.topic || '').toLowerCase().includes(q) ||
      (e.description || '').toLowerCase().includes(q)
  )
})

function openDrawer(which) {
  drawer.value = which
  eawSearch.value = ''
}
function closeDrawer() {
  drawer.value = null
}

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
  closeDrawer()
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

async function loadEaw() {
  eawLoading.value = true
  try {
    const data = await listEawEpisodes(100)
    eawEpisodes.value = data.items || []
  } catch {
    /* 静默 · BBC EAW 没数据不阻塞 */
  } finally {
    eawLoading.value = false
  }
}

async function pickEaw(slug) {
  closeDrawer()
  try {
    const ep = await getEawEpisode(slug)
    // PracticePlayer.cardBySegIdx 用 source.id 区分；用 slug 字符串作 id
    ep.id = `eaw:${slug}`
    emit('imported', ep)
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

onMounted(() => {
  loadHistory()
  loadEaw()
})

defineExpose({ refreshHistory: loadHistory })
</script>

<template>
  <div class="import-panel">
    <!-- 字幕来源 · 抽屉触发器 -->
    <section v-if="history.length || eawEpisodes.length" class="source-grid">
      <button
        v-if="eawEpisodes.length"
        class="source-card eaw-card"
        @click="openDrawer('eaw')"
      >
        <span class="ico">📚</span>
        <span class="info">
          <span class="t">BBC English at Work</span>
          <span class="sub">{{ eawEpisodes.length }} 集 · 公共语料</span>
        </span>
        <span class="chev">›</span>
      </button>
      <button
        v-if="history.length"
        class="source-card"
        @click="openDrawer('history')"
      >
        <span class="ico">🕒</span>
        <span class="info">
          <span class="t">我的历史字幕</span>
          <span class="sub">{{ history.length }} 条 · 点击重新练习</span>
        </span>
        <span class="chev">›</span>
      </button>
    </section>

    <h4 v-if="history.length || eawEpisodes.length" class="new-import-h">新导入</h4>

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

  <!-- 抽屉 · 竖向列表 -->
  <Teleport to="body">
    <Transition name="drawer">
      <div v-if="drawer" class="drawer-overlay" @click.self="closeDrawer">
        <aside class="drawer">
          <header class="drawer-head">
            <h3 v-if="drawer === 'eaw'">📚 BBC English at Work · {{ eawEpisodes.length }}</h3>
            <h3 v-else>🕒 我的历史字幕 · {{ history.length }}</h3>
            <button class="close" @click="closeDrawer" aria-label="关闭">×</button>
          </header>

          <div v-if="drawer === 'eaw'" class="drawer-body">
            <input
              v-model="eawSearch"
              class="search"
              placeholder="搜索集名 / 主题..."
            />
            <ul class="vlist">
              <li
                v-for="ep in filteredEaw"
                :key="ep.slug"
                class="vitem eaw-vitem"
                @click="pickEaw(ep.slug)"
              >
                <div class="vrow">
                  <span class="vico">🎓</span>
                  <span class="vtitle">{{ ep.title || ep.slug }}</span>
                </div>
                <div v-if="ep.topic || ep.description" class="vmeta">
                  <span v-if="ep.topic" class="vtopic">{{ ep.topic }}</span>
                  <span v-if="ep.description" class="vdesc">{{ ep.description }}</span>
                </div>
              </li>
              <li v-if="!filteredEaw.length" class="vempty">无匹配集</li>
            </ul>
          </div>

          <div v-else class="drawer-body">
            <ul class="vlist">
              <li
                v-for="s in history"
                :key="s.id"
                class="vitem"
                @click="pickHistory(s.id)"
              >
                <div class="vrow">
                  <span class="vico">{{ s.source_type === 'manual' ? '📋' : (s.source_type === 'youtube' ? '🎬' : '📺') }}</span>
                  <span class="vtitle">{{ s.title || '(未命名)' }}</span>
                </div>
                <div v-if="s.created_at" class="vmeta">
                  <span class="vdate">{{ s.created_at.slice(0, 10) }}</span>
                </div>
              </li>
              <li v-if="!history.length" class="vempty">还没有历史字幕</li>
            </ul>
          </div>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.import-panel {
  padding: var(--space-4);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.new-import-h {
  margin: var(--space-4) 0 var(--space-2);
  font-size: 11px;
  color: var(--text-3);
  letter-spacing: 0.5px;
  text-transform: uppercase;
  font-weight: 600;
}

/* 字幕来源 · 双卡片入口 */
.source-grid {
  display: grid;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
.source-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  padding: var(--space-3);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  text-align: left;
  cursor: pointer;
  touch-action: manipulation;
  transition: background var(--duration) var(--ease),
    border-color var(--duration) var(--ease);
}
.source-card:active {
  background: var(--accent-soft);
  border-color: var(--accent);
}
.source-card.eaw-card {
  background: var(--accent-soft);
  border-color: transparent;
}
.source-card .ico {
  font-size: 24px;
  flex-shrink: 0;
}
.source-card .info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.source-card .info .t {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.source-card.eaw-card .info .t {
  color: var(--accent);
}
.source-card .info .sub {
  font-size: 12px;
  color: var(--text-3);
}
.source-card .chev {
  font-size: 24px;
  color: var(--text-3);
  flex-shrink: 0;
}

/* 抽屉 */
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: var(--z-modal);
  display: flex;
  justify-content: flex-end;
}
.drawer {
  width: 100%;
  max-width: 420px;
  height: 100dvh;
  background: var(--bg);
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.15);
}
.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  padding-top: calc(var(--safe-top) + var(--space-3));
  border-bottom: 1px solid var(--border);
  background: var(--bg-elevated);
}
.drawer-head h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-1);
}
.drawer-head .close {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  font-size: 24px;
  line-height: 1;
  color: var(--text-2);
  border-radius: 50%;
  background: transparent;
}
.drawer-head .close:active {
  background: var(--bg);
}
.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-3) var(--space-4) calc(var(--safe-bottom) + var(--space-4));
}
.search {
  width: 100%;
  margin-bottom: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  font-size: 14px;
  outline: none;
}
.search:focus {
  border-color: var(--accent);
}
.vlist {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.vitem {
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  touch-action: manipulation;
  transition: background var(--duration) var(--ease);
}
.vitem:hover {
  background: var(--bg-elevated);
}
.vitem:active {
  background: var(--accent-soft);
  transform: scale(0.99);
}
.eaw-vitem {
  border-left: 3px solid var(--accent);
}
.vrow {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.vico {
  font-size: 16px;
  flex-shrink: 0;
}
.vtitle {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-1);
  flex: 1;
  min-width: 0;
}
.vmeta {
  margin-top: 4px;
  margin-left: 24px;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.4;
}
.vtopic {
  padding: 1px 8px;
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: 8px;
  font-size: 11px;
}
.vdesc {
  flex: 1;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.vempty {
  padding: var(--space-4);
  text-align: center;
  color: var(--text-3);
  font-size: 13px;
}

.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.2s ease;
}
.drawer-enter-active .drawer,
.drawer-leave-active .drawer {
  transition: transform 0.25s cubic-bezier(0.32, 0.72, 0, 1);
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from .drawer,
.drawer-leave-to .drawer {
  transform: translateX(100%);
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
