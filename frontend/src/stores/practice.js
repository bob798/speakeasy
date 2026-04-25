/**
 * practiceStore · 发音练习 state
 *
 * 替代 static/practice.html 的全局 let 变量（segments/practiceQueue/currentIdx/markedIndices 等）。
 * keep-alive 策略下 Practice.vue 的 state 在路由切换不丢。
 *
 * @typedef {{ from: number, to: number, content: string }} Segment
 * @typedef {{ id: number, text: string, card_state?: string, segIdx?: number }} PracticeCard
 * @typedef {{ id: string, title: string, segments: Segment[], audio_file?: string, source_type?: string }} SubtitleSource
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const usePracticeStore = defineStore('practice', () => {
  /** @type {import('vue').Ref<SubtitleSource|null>} */
  const currentSource = ref(null)
  /** @type {import('vue').Ref<PracticeCard[]>} */
  const cards = ref([])
  const currentIdx = ref(0)
  const markedIndices = ref(new Set())
  const practicedIndices = ref(new Set())
  const ratingResults = ref({ again: 0, hard: 0, good: 0, easy: 0 })
  const provider = ref('edge') // edge | doubao
  const speed = ref('+0%')

  const segments = computed(() => currentSource.value?.segments || [])
  const currentSegment = computed(() => segments.value[currentIdx.value] || null)
  const totalPracticed = computed(() => practicedIndices.value.size)
  const progressPct = computed(() => {
    const total = segments.value.length
    return total ? Math.round((totalPracticed.value / total) * 100) : 0
  })

  function loadSource(source) {
    currentSource.value = source
    currentIdx.value = 0
    markedIndices.value = new Set()
    practicedIndices.value = new Set()
    ratingResults.value = { again: 0, hard: 0, good: 0, easy: 0 }
  }

  function setCurrentIdx(idx) {
    if (idx >= 0 && idx < segments.value.length) {
      currentIdx.value = idx
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
  }
})
