import { computed } from 'vue'

/**
 * Coach bar 状态机 · 纯派生 · 不持有 state
 *
 * 状态优先级：recording > isPlayingTTS > selectedWord > hasPlayedBack > hasRecording > idle
 *
 * @param {{
 *   selectedWord:   import('vue').Ref<{word:string, display:string}|null>,
 *   recording:      import('vue').Ref<boolean>,
 *   isPlayingTTS:   import('vue').Ref<boolean>,
 *   hasRecording:   import('vue').Ref<boolean>,
 *   hasPlayedBack:  import('vue').Ref<boolean>,
 *   currentIdx:     import('vue').Ref<number>,
 *   totalSegments:  import('vue').Ref<number>,
 *   practicedCount: import('vue').Ref<number>,
 * }} state
 */
export function useCoachBar(state) {
  const coachCopy = computed(() => {
    if (state.recording.value) return '录音中 · 念完点停止'
    if (state.isPlayingTTS.value) return '听着…'
    if (state.selectedWord.value) return `解读 "${state.selectedWord.value.display}"`
    if (state.hasRecording.value && state.hasPlayedBack.value) return '比一比，节奏对齐了吗'
    if (state.hasRecording.value) return '收到了 · 回放听听自己'
    return '先听我读一次'
  })

  const coachClass = computed(() => (state.recording.value ? 'recording' : ''))

  const coachProgress = computed(() => {
    const base = `第 ${state.currentIdx.value + 1}/${state.totalSegments.value} 句`
    return state.practicedCount.value > 0
      ? `${base} · 已完成 ${state.practicedCount.value}`
      : base
  })

  return { coachCopy, coachClass, coachProgress }
}
