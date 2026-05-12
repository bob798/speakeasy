/**
 * practiceStore · 发音练习 state
 *
 * 替代 static/practice.html 的全局 let 变量（segments/practiceQueue/currentIdx/markedIndices 等）。
 * keep-alive 策略下 Practice.vue 的 state 在路由切换不丢。
 * V0.9.6+ 加进度持久化：localStorage 记每个 source 的 currentIdx /
 *                       practiced / ratings，下次进同一 source 自动恢复。
 *
 * @typedef {{ from: number, to: number, content: string }} Segment
 * @typedef {{ id: number, text: string, card_state?: string, segIdx?: number }} PracticeCard
 * @typedef {{ id: string|number, title: string, segments: Segment[], audio_file?: string, source_type?: string }} SubtitleSource
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

const PROGRESS_KEY = 'v2:practice.progress'
const LAST_SOURCE_KEY = 'v2:practice.lastSource'

function _loadProgressMap() {
  try {
    const raw = localStorage.getItem(PROGRESS_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function _saveProgressMap(map) {
  try {
    localStorage.setItem(PROGRESS_KEY, JSON.stringify(map))
  } catch {
    /* 配额满或隐私模式 · 静默 */
  }
}

export const usePracticeStore = defineStore('practice', () => {
  /** @type {import('vue').Ref<SubtitleSource|null>} */
  const currentSource = ref(null)
  /** @type {import('vue').Ref<PracticeCard[]>} */
  const cards = ref([])
  const currentIdx = ref(0)
  const markedIndices = ref(new Set())
  const practicedIndices = ref(new Set())
  const ratingResults = ref({ again: 0, hard: 0, good: 0, easy: 0 })
  const provider = ref('edge') // edge | azure | google  (后端 multi_tts 支持 + openai)
  const speed = ref('+0%')

  const segments = computed(() => currentSource.value?.segments || [])
  const currentSegment = computed(() => segments.value[currentIdx.value] || null)
  const totalPracticed = computed(() => practicedIndices.value.size)
  const progressPct = computed(() => {
    const total = segments.value.length
    return total ? Math.round((totalPracticed.value / total) * 100) : 0
  })

  function _persist() {
    if (!currentSource.value?.id) return
    const map = _loadProgressMap()
    map[String(currentSource.value.id)] = {
      idx: currentIdx.value,
      practicedIndices: [...practicedIndices.value],
      markedIndices: [...markedIndices.value],
      ratingResults: { ...ratingResults.value },
      title: currentSource.value.title || '',
      sourceType: currentSource.value.source_type || '',
      updatedAt: new Date().toISOString(),
    }
    _saveProgressMap(map)
    try {
      localStorage.setItem(LAST_SOURCE_KEY, String(currentSource.value.id))
    } catch {
      /* ignore */
    }
  }

  function loadSource(source) {
    currentSource.value = source

    // 试图从 localStorage 恢复进度
    const map = _loadProgressMap()
    const saved = source?.id != null ? map[String(source.id)] : null
    if (saved) {
      currentIdx.value = Math.min(
        saved.idx || 0,
        Math.max(0, (source.segments?.length || 1) - 1)
      )
      practicedIndices.value = new Set(saved.practicedIndices || [])
      markedIndices.value = new Set(saved.markedIndices || [])
      ratingResults.value = saved.ratingResults || {
        again: 0, hard: 0, good: 0, easy: 0,
      }
    } else {
      currentIdx.value = 0
      markedIndices.value = new Set()
      practicedIndices.value = new Set()
      ratingResults.value = { again: 0, hard: 0, good: 0, easy: 0 }
    }
    _persist()
  }

  function setCurrentIdx(idx) {
    if (idx >= 0 && idx < segments.value.length) {
      currentIdx.value = idx
      _persist()
    }
  }

  function markPracticed(idx, rating) {
    practicedIndices.value.add(idx)
    if (rating in ratingResults.value) {
      ratingResults.value[rating]++
    }
    // 触发响应式：Set 需要 reassign
    practicedIndices.value = new Set(practicedIndices.value)
    markedIndices.value = new Set(markedIndices.value).add(idx)
    _persist()
  }

  function upsertCard(card) {
    const idx = cards.value.findIndex((c) => c.id === card.id)
    if (idx >= 0) {
      cards.value[idx] = { ...cards.value[idx], ...card }
    } else {
      cards.value.push(card)
    }
  }

  function reset() {
    currentSource.value = null
    cards.value = []
    currentIdx.value = 0
    markedIndices.value = new Set()
    practicedIndices.value = new Set()
    ratingResults.value = { again: 0, hard: 0, good: 0, easy: 0 }
  }

  /**
   * 取最近练过的 source id（不含当前 session）· 用于"继续上次"按钮
   */
  function getLastSourceId() {
    try {
      return localStorage.getItem(LAST_SOURCE_KEY)
    } catch {
      return null
    }
  }

  /**
   * 取所有保存过的 source 进度摘要（按 updatedAt 倒序）· 用于历史抽屉
   */
  function listProgress() {
    const map = _loadProgressMap()
    return Object.entries(map)
      .map(([id, p]) => ({ id, ...p }))
      .sort((a, b) => (b.updatedAt || '').localeCompare(a.updatedAt || ''))
  }

  return {
    currentSource,
    cards,
    currentIdx,
    markedIndices,
    practicedIndices,
    ratingResults,
    provider,
    speed,
    segments,
    currentSegment,
    totalPracticed,
    progressPct,
    loadSource,
    setCurrentIdx,
    markPracticed,
    upsertCard,
    reset,
    getLastSourceId,
    listProgress,
  }
})
