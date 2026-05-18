<script setup>
/**
 * Practice · V0.12 手机端重设计
 *
 * 桌面端 (>= 768px) 仍走 SentenceList + PracticePlayer（不动）。
 * 手机端 (< 768px) 走 MobileSentenceList + MobileActionDock，
 * 所有副作用（TTS / 录音 / API / 状态机）集中在本文件。
 *
 * 设计文档：docs/superpowers/specs/2026-05-12-practice-mobile-redesign.md
 * 实现计划：docs/superpowers/plans/2026-05-12-practice-mobile-redesign.md
 */
import { ref, computed, watch, onActivated, onDeactivated, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { usePracticeStore } from '@/stores/practice'
import { usePractice } from '@/composables/usePractice'
import { useRecorder } from '@/composables/useRecorder'
import { useAuthFetch, getErrorMessage } from '@/composables/useAuthFetch'
import { useScrollLock } from '@/composables/useScrollLock'
import { useBreakpoint } from '@/composables/useBreakpoint'

import SubtitleImport from '@/components/practice/SubtitleImport.vue'
import SentenceList from '@/components/practice/SentenceList.vue'
import PracticePlayer from '@/components/practice/PracticePlayer.vue'
import MobileSentenceList from '@/components/practice/MobileSentenceList.vue'
import MobileActionDock from '@/components/practice/MobileActionDock.vue'
import ExplanationModal from '@/components/ExplanationModal.vue'

defineOptions({ name: 'Practice' })

const router = useRouter()
const store = usePracticeStore()
const { createCards, ttsBlob, rateCard } = usePractice()
const { authFetch } = useAuthFetch()
const recorder = useRecorder()
const { isMobile } = useBreakpoint()

// ---- 通用 / 桌面端原有逻辑 ----
const explainOpen = ref(false)
const explainTarget = ref(null)
const toast = ref({ show: false, text: '', type: 'info' })

const hasSource = computed(
  () => !!store.currentSource && (store.segments?.length || 0) > 0
)
const isBbcSource = computed(() => {
  const s = store.currentSource
  return !!s && (s.source_type === 'bbc_eaw' || s.type === 'bbc_eaw')
})

function showToast(text, type = 'info', duration = 2500) {
  toast.value = { show: true, text, type }
  setTimeout(() => (toast.value.show = false), duration)
}

// ---- 手机端本地状态（不入 Pinia） ----
const selectedWord = ref(null)         // { word, display } | null
const sheetOpen = ref(false)
const recordingSegIdx = ref(null)
const hasPlayedBack = ref(false)
const isPlayingTTS = ref(false)
const practicedCount = ref(0)
// #26 手机端评分（方案 C：录完自动进入）
const ratingMode = ref(false)
const ratingBusy = ref(false)
let _ttsAudio = null
let _ttsUrl = null
let _lastRequestKey = null

useScrollLock(sheetOpen)

// 跨断点（resize 跨 768px）时清状态防泄漏
watch(isMobile, () => {
  selectedWord.value = null
  sheetOpen.value = false
  _releaseTTS()
  if (recorder.recording.value) recorder.stop()
  recordingSegIdx.value = null
  ratingMode.value = false
})

// 录音停下且已有录音 → 自动进入评分模式（#26 方案 C）
// codex review: 仅当录音归属当前句时才进；否则切句中途 onstop 异步落地会给新句错误开启评分
watch(
  () => recorder.recording.value,
  (isRec, wasRec) => {
    if (
      wasRec && !isRec && recorder.url.value && isMobile.value &&
      recordingSegIdx.value === store.currentIdx
    ) {
      ratingMode.value = true
    }
  }
)

// 切句即退出评分模式（避免拿上一句的评分意图给新句）
watch(
  () => store.currentIdx,
  () => {
    ratingMode.value = false
  }
)

function gotoBbcReview() {
  const slug = store.currentSource?.slug || store.currentSource?.id
  if (!slug) return
  router.push({ name: 'bbc-review', params: { slug } })
}

function getAuthHeaders() {
  try {
    const t = localStorage.getItem('v2:auth.token') || localStorage.getItem('token')
    return t ? { Authorization: 'Bearer ' + t } : {}
  } catch { return {} }
}

async function onImported(data) {
  if (!data.id && data.source_id) data.id = data.source_id
  store.loadSource(data)

  const segs = (data.segments || []).map((seg, i) => ({
    text: seg.content,
    context: JSON.stringify({ segIdx: i, from: seg.from, to: seg.to }),
    segIdx: i,
  }))

  try {
    const existingResp = await fetch('/practice/cards?limit=200', {
      headers: getAuthHeaders(),
    })
    const existingCards = existingResp.ok
      ? ((await existingResp.json()).cards || [])
      : []

    const cardBySegIdx = {}
    for (const c of existingCards) {
      let segIdx = null
      try {
        const ctx = c.context ? JSON.parse(c.context) : {}
        if (typeof ctx.segIdx === 'number') segIdx = ctx.segIdx
      } catch { /* ignore */ }
      if (segIdx == null) {
        segIdx = segs.findIndex((s) => s.text === c.text)
      }
      if (segIdx >= 0 && segIdx < segs.length) {
        cardBySegIdx[segIdx] = { ...c, segIdx }
      }
    }

    const missing = segs.filter((_, i) => !cardBySegIdx[i])
    if (missing.length) {
      await createCards({ items: missing })
      const refetchResp = await fetch('/practice/cards?limit=200', {
        headers: getAuthHeaders(),
      })
      const refetched = refetchResp.ok
        ? ((await refetchResp.json()).cards || [])
        : []
      for (const c of refetched) {
        let segIdx = null
        try {
          const ctx = c.context ? JSON.parse(c.context) : {}
          if (typeof ctx.segIdx === 'number') segIdx = ctx.segIdx
        } catch { /* ignore */ }
        if (segIdx == null) segIdx = segs.findIndex((s) => s.text === c.text)
        if (segIdx >= 0 && segIdx < segs.length) {
          cardBySegIdx[segIdx] = { ...c, segIdx }
        }
      }
    }

    store.cards = Object.values(cardBySegIdx)
    showToast(`已导入 ${segs.length} 段`, 'info')
  } catch (err) {
    const msg = getErrorMessage(err, '卡片初始化失败')
    if (msg) showToast(msg, 'error')
  }
}

function onSelect(idx) {
  store.setCurrentIdx(idx)
}

function onExplain(payload) {
  let target
  if (typeof payload === 'string') {
    target = { type: 'sentence', content: payload }
  } else {
    target = { type: payload.type, content: payload.content }
    if (payload.sentence) target.sentence = payload.sentence
  }
  const src = store.currentSource || {}
  const isBbc = src.source_type === 'bbc_eaw' || src.type === 'bbc_eaw'
  const vocabRef = isBbc
    ? { vocab_source_type: 'bbc_eaw', vocab_source_ref: src.slug || src.id || null }
    : { vocab_source_type: 'practice', vocab_source_ref: src.id || src.source_id || null }
  target.context = {
    source: 'practice',
    source_id: src.id,
    ...vocabRef,
    ...(target.sentence ? { sentence: target.sentence } : {}),
  }
  explainTarget.value = target
  explainOpen.value = true
}

function onRated({ level }) {
  showToast(`已评 ${level}`, 'info', 1200)
}

function onNewImport() {
  store.reset()
  sheetOpen.value = false
}

// ---- 手机端：选词 / 切句 / dock 动作 ----
function _releaseTTS() {
  if (_ttsAudio) { _ttsAudio.pause(); _ttsAudio = null }
  if (_ttsUrl)   { URL.revokeObjectURL(_ttsUrl); _ttsUrl = null }
  isPlayingTTS.value = false
}

function onMobileSelectSentence(idx) {
  if (idx === store.currentIdx) return
  // 状态机：录音中切句要 confirm
  if (recorder.recording.value) {
    const ok = window.confirm('正在录音，停止并切换到这一句？')
    if (!ok) return
    recorder.stop()
    recorder.reset()
    recordingSegIdx.value = null
  }
  _releaseTTS()
  // codex review (#26): practicedCount 不再随切句自增；只有评分成功才计，否则 coach 文案与实际进度不符
  store.setCurrentIdx(idx)
  selectedWord.value = null
  hasPlayedBack.value = false
}

function onMobileSelectWord({ word, display }) {
  selectedWord.value = { word, display }
}
function onMobileClearWord() {
  selectedWord.value = null
}

function onMobileExplain() {
  // 与 onMobileSpeak 对齐：触发即推进 _lastRequestKey，让在飞 TTS 响应被丢弃
  _lastRequestKey = `explain:${store.currentIdx}:${selectedWord.value?.word || '__'}:${Date.now()}`
  if (selectedWord.value) {
    onExplain({
      type: 'word',
      content: selectedWord.value.display,
      sentence: store.currentSegment?.content || '',
    })
  } else {
    onExplain(store.currentSegment?.content || '')
  }
}

async function onMobileSpeak() {
  const key = `tts:${store.currentIdx}:${selectedWord.value?.word || '__'}:${Date.now()}`
  _lastRequestKey = key
  _releaseTTS()
  isPlayingTTS.value = true
  try {
    const text = selectedWord.value ? selectedWord.value.display : (store.currentSegment?.content || '')
    if (!text) {
      isPlayingTTS.value = false
      return
    }
    const blob = await ttsBlob({
      text,
      provider: store.provider,
      speed: store.speed,
    })
    if (_lastRequestKey !== key) return // stale 丢弃
    _ttsUrl = URL.createObjectURL(blob)
    _ttsAudio = new Audio(_ttsUrl)
    _ttsAudio.onended = () => { if (_lastRequestKey === key) isPlayingTTS.value = false }
    await _ttsAudio.play()
  } catch (err) {
    const msg = getErrorMessage(err, 'TTS 失败')
    if (msg) showToast(msg, 'error')
    isPlayingTTS.value = false
  }
}

async function onMobileToggleRecord() {
  if (recorder.recording.value) {
    // codex round 2: 不再立刻清 recordingSegIdx —— 它是「这段录音属于哪一句」的标记，
    // onstop 异步落地后 watcher 才能用它判断是否给当前句开评分模式。
    // 留到下次 start() 时再覆盖。
    recorder.stop()
    hasPlayedBack.value = false
  } else {
    recorder.reset()
    ratingMode.value = false       // 新一轮，退出评分（如有）
    await recorder.start()
    if (recorder.error.value) {
      showToast(recorder.error.value, 'error')
      return
    }
    recordingSegIdx.value = store.currentIdx
  }
}

function onMobilePlayback() {
  if (!recorder.url.value) {
    showToast('先录一段', 'info', 1200)
    return
  }
  const a = new Audio(recorder.url.value)
  a.play()
  hasPlayedBack.value = true
}

// #26 评分模式（方案 C）— 录完自动进入；选完评分自动跳下一句
// codex review:
//  - 把 ratedIdx 在 await 前捕获，避免用户切句中途让 markPracticed/跳句落到错段
//  - 评分成功后 practicedCount 自增（之前只在切句时 +1，导致 coach 文案与实际不符）
async function onMobileRate(level) {
  if (ratingBusy.value) return
  const ratedIdx = store.currentIdx
  const card = store.cards.find((c) => c.segIdx === ratedIdx)
  if (!card?.id) {
    showToast('卡片未就绪，重新选一下句子再来', 'error', 2000)
    ratingMode.value = false
    return
  }
  ratingBusy.value = true
  try {
    await rateCard(card.id, level)
    // 评分写到的是 ratedIdx 的卡，markPracticed 也必须对齐 ratedIdx
    store.markPracticed(ratedIdx, level)
    practicedCount.value += 1
    showToast(`✅ 已评 ${({ again: 'Again', hard: 'Hard', good: 'Good', easy: 'Easy' })[level]}`, 'success', 1200)
    // 用户在请求过程中可能已切句 / 重录，只有当前还停在被评分的那一句才推动 UI
    if (store.currentIdx === ratedIdx) {
      ratingMode.value = false
      recorder.reset()
      hasPlayedBack.value = false
      if (ratedIdx < store.segments.length - 1) {
        setTimeout(() => {
          // 二次校验：定时器触发时用户仍在 ratedIdx 才跳
          if (store.currentIdx === ratedIdx) {
            store.setCurrentIdx(ratedIdx + 1)
          }
        }, 400)
      }
    }
  } catch (err) {
    const msg = getErrorMessage(err, '评分失败')
    if (msg) showToast(msg, 'error')
  } finally {
    ratingBusy.value = false
  }
}

async function onMobileRedoRecord() {
  // 退出评分 + 立即开新录音
  ratingMode.value = false
  recorder.reset()
  hasPlayedBack.value = false
  await recorder.start()
  if (recorder.error.value) {
    showToast(recorder.error.value, 'error')
    return
  }
  recordingSegIdx.value = store.currentIdx
}

// ⚙ sheet 焦点管理（spec §可访问性 #5）
const sheetTriggerRef = ref(null)
const sheetRef = ref(null)
const INERT_SELECTORS = '.topbar, .m-list, .dock, .layout'

function onOpenSettings() {
  sheetTriggerRef.value = document.activeElement
  sheetOpen.value = true
  // 屏蔽背景 a11y 树
  document.querySelectorAll(INERT_SELECTORS).forEach((el) => el.setAttribute('inert', ''))
  // 等下一帧 DOM 出现再 focus
  setTimeout(() => {
    const first = sheetRef.value?.querySelector('button')
    if (first) first.focus()
  }, 60)
}
function onCloseSettings() {
  sheetOpen.value = false
  document.querySelectorAll(INERT_SELECTORS).forEach((el) => el.removeAttribute('inert'))
  if (sheetTriggerRef.value && typeof sheetTriggerRef.value.focus === 'function') {
    sheetTriggerRef.value.focus()
  }
}

// Esc 关闭 sheet
function _onEscape(e) {
  if (e.key === 'Escape' && sheetOpen.value) onCloseSettings()
}
window.addEventListener('keydown', _onEscape)

// 切句时清 TTS
watch(
  () => store.currentIdx,
  (n, o) => {
    if (n === o) return
    _releaseTTS()
  }
)

onActivated(() => {})
onDeactivated(() => {})
onBeforeUnmount(() => {
  _releaseTTS()
  recorder.reset()
  window.removeEventListener('keydown', _onEscape)
})
</script>

<template>
  <div class="practice-page" :class="{ mobile: isMobile }">
    <header class="topbar">
      <RouterLink class="back" to="/">← 返回</RouterLink>
      <div class="title">发音练习</div>
      <div class="topbar-right">
        <!-- 桌面端原有按钮 -->
        <template v-if="!isMobile">
          <button
            v-if="hasSource && isBbcSource"
            class="bbc-btn"
            @click="gotoBbcReview"
            title="开始/继续这篇 BBC 文章的 SRS 复习"
          >📖 复习</button>
          <button
            v-if="hasSource"
            class="new-btn"
            @click="onNewImport"
            title="重新导入字幕"
          >🔄</button>
        </template>
        <!-- 手机端：单一 ⚙ 设置入口 -->
        <button
          v-if="isMobile && hasSource"
          class="settings-btn"
          @click="onOpenSettings"
          aria-label="打开设置"
        >
          <span aria-hidden="true">⚙</span>
          <span>设置</span>
        </button>
      </div>
    </header>

    <div v-if="!hasSource" class="import-wrap">
      <SubtitleImport @imported="onImported" />
    </div>

    <!-- 桌面端布局 -->
    <div v-else-if="!isMobile" class="layout">
      <aside class="left">
        <div class="progress">
          <div class="progress-bar" :style="{ width: `${store.progressPct}%` }"></div>
        </div>
        <div class="stats">
          {{ store.totalPracticed }}/{{ store.segments.length }} 已练
          · Again: {{ store.ratingResults.again }}
          · Good: {{ store.ratingResults.good }}
        </div>
        <SentenceList @select="onSelect" @explain="onExplain" />
      </aside>
      <main class="right">
        <PracticePlayer
          @rated="onRated"
          @explain="onExplain"
          @toast="({ text, type, duration }) => showToast(text, type || 'info', duration || 2000)"
        />
      </main>
    </div>

    <!-- 手机端布局 -->
    <template v-else>
      <MobileSentenceList
        :selected-word="selectedWord"
        @select-sentence="onMobileSelectSentence"
        @select-word="onMobileSelectWord"
        @clear-word="onMobileClearWord"
      />
      <MobileActionDock
        :selected-word="selectedWord"
        :recording="recorder.recording.value"
        :is-playing-t-t-s="isPlayingTTS"
        :has-recording="!!recorder.url.value"
        :has-played-back="hasPlayedBack"
        :current-idx="store.currentIdx"
        :total-segments="store.segments.length"
        :practiced-count="practicedCount"
        :rating-mode="ratingMode"
        :rating-busy="ratingBusy"
        @explain="onMobileExplain"
        @speak="onMobileSpeak"
        @toggle-record="onMobileToggleRecord"
        @playback="onMobilePlayback"
        @rate="onMobileRate"
        @redo-record="onMobileRedoRecord"
      />
    </template>

    <!-- ⚙ 手机端 sheet -->
    <Teleport to="body">
      <Transition name="sheet">
        <div
          v-if="sheetOpen"
          class="sheet-mask"
          @click.self="onCloseSettings"
          @keydown.esc="onCloseSettings"
        >
          <aside ref="sheetRef" class="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title">
            <h4 id="sheet-title">设置</h4>
            <div class="sheet-row">
              <label>语速</label>
              <div class="seg-pick">
                <button
                  v-for="opt in [
                    { v: '-40%', label: '慢' },
                    { v: '-20%', label: '偏慢' },
                    { v: '+0%',  label: '正常' },
                    { v: '+20%', label: '偏快' },
                  ]"
                  :key="opt.v"
                  type="button"
                  :class="{ active: store.speed === opt.v }"
                  @click="store.speed = opt.v"
                >{{ opt.label }}</button>
              </div>
            </div>
            <div class="sheet-row">
              <label>TTS 引擎</label>
              <div class="seg-pick">
                <button
                  v-for="opt in [
                    { v: 'edge',   label: 'Edge' },
                    { v: 'azure',  label: 'Azure' },
                    { v: 'google', label: 'Google' },
                  ]"
                  :key="opt.v"
                  type="button"
                  :class="{ active: store.provider === opt.v }"
                  @click="store.provider = opt.v"
                >{{ opt.label }}</button>
              </div>
            </div>

            <div class="sheet-divider"></div>

            <button
              v-if="isBbcSource"
              class="sheet-action"
              type="button"
              @click="gotoBbcReview(); onCloseSettings()"
            >
              <span class="sa-ico">📖</span>
              <span class="sa-body">
                <span class="sa-title">BBC 复习</span>
                <span class="sa-desc">基于 SRS 的文章复习</span>
              </span>
              <span class="sa-chev">›</span>
            </button>
            <button
              class="sheet-action"
              type="button"
              @click="onNewImport()"
            >
              <span class="sa-ico">🔄</span>
              <span class="sa-body">
                <span class="sa-title">重新导入字幕</span>
                <span class="sa-desc">换一集、换一篇</span>
              </span>
              <span class="sa-chev">›</span>
            </button>

            <div class="sheet-footer-note">
              ℹ︎ 关于复习评分 · 录完一句后会自动出现 Again / Hard / Good / Easy 评分，
              FSRS 会按你的反馈安排下次复习。点「重录」可重新来过。
            </div>
          </aside>
        </div>
      </Transition>
    </Teleport>

    <ExplanationModal v-model:open="explainOpen" :target="explainTarget" />

    <Transition name="toast">
      <div v-if="toast.show" class="toast" :class="toast.type">{{ toast.text }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.practice-page {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  background: var(--bg);
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  padding-top: calc(var(--safe-top) + var(--space-3));
  background: var(--bg-overlay);
  backdrop-filter: saturate(180%) blur(16px);
  border-bottom: 1px solid var(--border);
}
.title {
  font-weight: 600;
  color: var(--accent);
}
.back {
  color: var(--text-2);
  font-size: 14px;
}
.topbar-right {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.new-btn,
.bbc-btn {
  padding: 6px var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--accent);
  color: var(--text-inverse);
  font-size: 13px;
  font-weight: 500;
  transition: background var(--duration) var(--ease);
  touch-action: manipulation;
  white-space: nowrap;
}
.bbc-btn {
  background: rgba(61, 107, 79, 0.18);
  color: var(--accent);
  border: 1px solid var(--accent);
}
.bbc-btn:active {
  transform: scale(0.96);
  background: var(--accent);
  color: var(--text-inverse);
}
.new-btn:active {
  transform: scale(0.96);
  background: var(--accent-hover);
}

/* mobile ⚙ 设置 胶囊按钮 */
.settings-btn {
  min-width: 44px;
  height: 36px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  gap: 4px;
  border-radius: 18px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 14px;
  font-weight: 500;
  font-family: inherit;
  border: none;
  cursor: pointer;
}
.settings-btn:focus { outline: none; }
.settings-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.settings-btn:active { background: var(--accent); color: var(--text-inverse); transform: scale(0.96); }

.import-wrap {
  max-width: 560px;
  width: 100%;
  margin: var(--space-5) auto;
  padding: 0 var(--space-4);
}

/* 桌面端 layout · 沿用 */
.layout {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(220px, 36%) 1fr;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  min-height: 0;
}
.left {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-height: 0;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.progress {
  height: 4px;
  background: var(--border);
}
.progress-bar {
  height: 100%;
  background: var(--accent);
  transition: width var(--duration) var(--ease);
}
.stats {
  padding: var(--space-2) var(--space-3);
  font-size: 11px;
  color: var(--text-3);
  border-bottom: 1px solid var(--border);
}
.right {
  min-height: 0;
}

/* 手机端：layout 块隐藏 · 让 MobileSentenceList(flex:1) + sticky Dock 接管 */
.practice-page.mobile .layout { display: none; }

.toast {
  position: fixed;
  bottom: calc(var(--safe-bottom) + var(--space-5));
  left: 50%;
  transform: translateX(-50%);
  background: var(--text-1);
  color: var(--text-inverse);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius);
  font-size: 13px;
  z-index: var(--z-toast);
  max-width: calc(100% - var(--space-5) * 2);
  text-align: center;
}
.toast.error { background: #c6463a; }
.toast-enter-active,
.toast-leave-active { transition: opacity var(--duration) var(--ease); }
.toast-enter-from,
.toast-leave-to { opacity: 0; }

/* ⚙ sheet · 底部 */
.sheet-mask {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  z-index: var(--z-modal);
  display: flex;
  align-items: flex-end;
}
.sheet {
  width: 100%;
  background: var(--bg-elevated);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  padding: var(--space-4);
  padding-bottom: calc(var(--space-4) + var(--safe-bottom));
  max-height: 80dvh;
  overflow-y: auto;
}
.sheet h4 { margin: 0 0 var(--space-3); font-size: 14px; color: var(--text-2); }
.sheet-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
}
.sheet-row label { font-size: 14px; color: var(--text-1); }
.seg-pick { display: flex; gap: 4px; }
.seg-pick button {
  padding: 6px 10px;
  font-size: 12px;
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--text-2);
  border: 1px solid var(--border);
  font-family: inherit;
  cursor: pointer;
}
.seg-pick button:focus { outline: none; }
.seg-pick button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.seg-pick button.active {
  background: var(--accent); color: #fff; border-color: var(--accent);
}
.sheet-divider {
  height: 1px;
  background: var(--border);
  margin: 12px 0;
}
.sheet-action {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 10px 8px;
  border: none;
  background: transparent;
  border-radius: var(--radius);
  cursor: pointer;
  font-family: inherit;
  text-align: left;
  transition: background 120ms var(--ease);
}
.sheet-action:active { background: var(--bg); }
.sheet-action:focus { outline: none; }
.sheet-action:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.sheet-action .sa-ico {
  width: 36px; height: 36px;
  display: grid; place-items: center;
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: var(--radius-sm);
  font-size: 18px;
}
.sheet-action .sa-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}
.sheet-action .sa-title { font-size: 14px; color: var(--text-1); font-weight: 500; }
.sheet-action .sa-desc { font-size: 11px; color: var(--text-3); }
.sheet-action .sa-chev { color: var(--text-3); font-size: 18px; }
.sheet-footer-note {
  margin-top: 12px;
  padding: 10px 12px;
  background: var(--bg);
  border-radius: var(--radius-sm);
  font-size: 11px;
  color: var(--text-3);
  line-height: 1.5;
}
.sheet-footer-note a { color: var(--accent); text-decoration: underline; }

.sheet-enter-active, .sheet-leave-active {
  transition: opacity 200ms var(--ease);
}
.sheet-enter-active .sheet, .sheet-leave-active .sheet {
  transition: transform 220ms var(--ease);
}
.sheet-enter-from, .sheet-leave-to { opacity: 0; }
.sheet-enter-from .sheet, .sheet-leave-to .sheet { transform: translateY(100%); }
</style>
