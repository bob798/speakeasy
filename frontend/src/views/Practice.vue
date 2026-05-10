<script setup>
/**
 * Practice · 主战场 2 · V0.8 重写版
 * 迁移自 static/practice.html 1529 行 → 分解为 Import / SentenceList / PracticePlayer
 *
 * Phase 3 核心路径：
 *   导入字幕 → 选句 → 创建卡片 → 播 TTS → 录音对比 → FSRS 评分
 *
 * keep-alive include=Practice · onDeactivated 清 TTS & recorder
 */
import { ref, computed, onActivated, onDeactivated } from 'vue'
import { usePracticeStore } from '@/stores/practice'
import { usePractice } from '@/composables/usePractice'
import { getErrorMessage } from '@/composables/useAuthFetch'
import { useScrollLock } from '@/composables/useScrollLock'
import SubtitleImport from '@/components/practice/SubtitleImport.vue'
import SentenceList from '@/components/practice/SentenceList.vue'
import PracticePlayer from '@/components/practice/PracticePlayer.vue'
import ExplanationModal from '@/components/ExplanationModal.vue'
import { useRouter } from 'vue-router'

defineOptions({ name: 'Practice' })

const router = useRouter()

const store = usePracticeStore()
const { createCards } = usePractice()

const explainOpen = ref(false)
const explainTarget = ref(null)
const toast = ref({ show: false, text: '', type: 'info' })
const listDrawerOpen = ref(false)
useScrollLock(listDrawerOpen)

// 必须有 source 且至少有一段；空段时仍展示导入页面，避免卡死
const hasSource = computed(
  () => !!store.currentSource && (store.segments?.length || 0) > 0
)

const isBbcSource = computed(() => {
  const s = store.currentSource
  return !!s && (s.source_type === 'bbc_eaw' || s.type === 'bbc_eaw')
})

function gotoBbcReview() {
  const slug = store.currentSource?.slug || store.currentSource?.id
  if (!slug) return
  router.push({ name: 'bbc-review', params: { slug } })
}

function showToast(text, type = 'info', duration = 2500) {
  toast.value = { show: true, text, type }
  setTimeout(() => (toast.value.show = false), duration)
}

async function onImported(data) {
  // 给 source 兜底一个 id（新导入时后端可能返回 id，从历史进入时后端返回时可能没带 id）
  if (!data.id && data.source_id) data.id = data.source_id
  store.loadSource(data)

  // Bug fix: CardItem.context 必须是 str，之前发 dict 导致 422
  const segs = (data.segments || []).map((seg, i) => ({
    text: seg.content,
    context: JSON.stringify({ segIdx: i, from: seg.from, to: seg.to }),
    segIdx: i,  // 前端本地跟踪用，后端 pydantic 会忽略 extras
  }))

  try {
    // 优先从后端拉该 source 下已有的 cards（历史模式）
    const existingResp = await fetch('/practice/cards?limit=200', {
      headers: getAuthHeaders(),
    })
    const existingCards = existingResp.ok
      ? ((await existingResp.json()).cards || [])
      : []

    // segIdx 映射：从 card.context 读出 segIdx；没有就按 text 匹配
    const cardBySegIdx = {}
    for (const c of existingCards) {
      let segIdx = null
      try {
        const ctx = c.context ? JSON.parse(c.context) : {}
        if (typeof ctx.segIdx === 'number') segIdx = ctx.segIdx
      } catch {
        /* ignore */
      }
      if (segIdx == null) {
        // fallback by text match
        segIdx = segs.findIndex((s) => s.text === c.text)
      }
      if (segIdx >= 0 && segIdx < segs.length) {
        cardBySegIdx[segIdx] = { ...c, segIdx }
      }
    }

    // 判断是否需要补创建：缺哪些 segIdx
    const missing = segs.filter((_, i) => !cardBySegIdx[i])
    if (missing.length) {
      await createCards({ items: missing })
      // POST 只返 {created, skipped}，需要重新 GET 拉完整 cards 列表
      const refetchResp = await fetch('/practice/cards?limit=200', {
        headers: getAuthHeaders(),
      })
      const refetched = refetchResp.ok
        ? ((await refetchResp.json()).cards || [])
        : []
      for (const c of refetched) {
        if (cardBySegIdx[segs.findIndex((s) => s.text === c.text)]) continue
        let segIdx = null
        try {
          const ctx = c.context ? JSON.parse(c.context) : {}
          if (typeof ctx.segIdx === 'number') segIdx = ctx.segIdx
        } catch {
          /* ignore */
        }
        if (segIdx == null) {
          segIdx = segs.findIndex((s) => s.text === c.text)
        }
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

function getAuthHeaders() {
  try {
    const t =
      localStorage.getItem('v2:auth.token') || localStorage.getItem('token')
    return t ? { Authorization: 'Bearer ' + t } : {}
  } catch {
    return {}
  }
}

function onSelect(idx) {
  store.setCurrentIdx(idx)
  listDrawerOpen.value = false  // 选完关抽屉（手机端）
}

function onExplain(payload) {
  // 兼容两种 emit 形式：
  //   string  → 整句解读
  //   { type, content, sentence? } → 单词或整句解读
  let target
  if (typeof payload === 'string') {
    target = { type: 'sentence', content: payload }
  } else {
    target = { type: payload.type, content: payload.content }
    if (payload.sentence) target.sentence = payload.sentence
  }
  // 来源识别：BBC EAW 走 bbc_eaw 域，便于联动文章级 SRS；其它走 practice
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
}

onActivated(() => {
  // 路由切回来时不做特殊恢复；keep-alive 已经保留 state
})
onDeactivated(() => {
  // 不清 state，store 继续保持
})
</script>

<template>
  <div class="practice-page">
    <header class="topbar">
      <RouterLink class="back" to="/">← 返回</RouterLink>
      <div class="title">发音练习</div>
      <div class="topbar-right">
        <!-- 手机端打开句子列表抽屉 -->
        <button
          v-if="hasSource"
          class="list-btn mobile-only"
          @click="listDrawerOpen = true"
          :title="`句子列表 ${store.currentIdx + 1}/${store.segments.length}`"
        >
          📜 {{ store.currentIdx + 1 }}/{{ store.segments.length }}
        </button>
        <button
          v-if="hasSource && isBbcSource"
          class="bbc-btn"
          @click="gotoBbcReview"
          title="开始/继续这篇 BBC 文章的 SRS 复习"
        >
          📖 复习
        </button>
        <button
          v-if="hasSource"
          class="new-btn"
          @click="onNewImport"
          title="重新导入字幕"
        >
          🔄
        </button>
      </div>
    </header>

    <div v-if="!hasSource" class="import-wrap">
      <SubtitleImport @imported="onImported" />
    </div>

    <div v-else class="layout">
      <!-- 桌面端左栏 · 手机端通过抽屉展示同一组件 -->
      <aside class="left desktop-only">
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

    <!-- 手机端句子列表抽屉 -->
    <Teleport to="body">
      <Transition name="list-drawer">
        <div
          v-if="listDrawerOpen && hasSource"
          class="list-drawer-overlay"
          @click.self="listDrawerOpen = false"
        >
          <aside class="list-drawer">
            <header class="ld-head">
              <h3>📜 句子列表 · {{ store.currentIdx + 1 }}/{{ store.segments.length }}</h3>
              <button class="ld-close" @click="listDrawerOpen = false" aria-label="关闭">×</button>
            </header>
            <div class="ld-progress">
              <div class="ld-progress-bar" :style="{ width: `${store.progressPct}%` }"></div>
            </div>
            <div class="ld-stats">
              {{ store.totalPracticed }}/{{ store.segments.length }} 已练 ·
              Again: {{ store.ratingResults.again }} ·
              Good: {{ store.ratingResults.good }}
            </div>
            <div class="ld-body">
              <SentenceList @select="onSelect" @explain="onExplain" />
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
.list-btn,
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
.list-btn {
  background: var(--bg-elevated);
  color: var(--text-1);
  border: 1px solid var(--border);
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
.new-btn:active,
.list-btn:active {
  transform: scale(0.96);
}
.new-btn:active {
  background: var(--accent-hover);
}
.import-wrap {
  max-width: 560px;
  width: 100%;
  margin: var(--space-5) auto;
  padding: 0 var(--space-4);
}

/* 默认：手机单栏（PracticePlayer 全宽），左栏隐藏 */
.layout {
  flex: 1;
  display: block;
  padding: var(--space-3) var(--space-4);
  min-height: 0;
}
.desktop-only {
  display: none;
}
.mobile-only {
  display: inline-flex;
}

/* ≥768px：双栏，桌面端原布局 */
@media (min-width: 768px) {
  .layout {
    display: grid;
    grid-template-columns: minmax(220px, 36%) 1fr;
    gap: var(--space-3);
  }
  .desktop-only {
    display: flex;
  }
  .mobile-only {
    display: none;
  }
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
}
.toast.error {
  background: #c6463a;
}
.toast-enter-active,
.toast-leave-active {
  transition: opacity var(--duration) var(--ease);
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
}

/* 句子列表抽屉 · 手机端从左滑入 */
.list-drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: var(--z-modal);
  display: flex;
}
.list-drawer {
  width: 90%;
  max-width: 380px;
  height: 100dvh;
  background: var(--bg);
  display: flex;
  flex-direction: column;
  box-shadow: 4px 0 24px rgba(0, 0, 0, 0.15);
}
.ld-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  padding-top: calc(var(--safe-top) + var(--space-3));
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border);
}
.ld-head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-1);
}
.ld-close {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  font-size: 22px;
  line-height: 1;
  color: var(--text-2);
  border-radius: 50%;
  background: transparent;
}
.ld-progress {
  height: 4px;
  background: var(--border);
}
.ld-progress-bar {
  height: 100%;
  background: var(--accent);
  transition: width var(--duration) var(--ease);
}
.ld-stats {
  padding: 6px var(--space-4);
  font-size: 11px;
  color: var(--text-3);
  border-bottom: 1px solid var(--border);
}
.ld-body {
  flex: 1;
  overflow-y: auto;
  padding-bottom: calc(var(--safe-bottom) + var(--space-3));
}

.list-drawer-enter-active,
.list-drawer-leave-active {
  transition: opacity 0.2s ease;
}
.list-drawer-enter-active .list-drawer,
.list-drawer-leave-active .list-drawer {
  transition: transform 0.25s cubic-bezier(0.32, 0.72, 0, 1);
}
.list-drawer-enter-from,
.list-drawer-leave-to {
  opacity: 0;
}
.list-drawer-enter-from .list-drawer,
.list-drawer-leave-to .list-drawer {
  transform: translateX(-100%);
}
</style>
