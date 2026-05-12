import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { useCoachBar } from '../useCoachBar'

function setup(overrides = {}) {
  const state = {
    selectedWord:  ref(null),
    recording:     ref(false),
    isPlayingTTS:  ref(false),
    hasRecording:  ref(false),
    hasPlayedBack: ref(false),
    currentIdx:    ref(0),
    totalSegments: ref(9),
    practicedCount: ref(0),
    ...overrides,
  }
  return { state, ...useCoachBar(state) }
}

describe('useCoachBar', () => {
  it('空闲：先听我读一次', () => {
    const { coachCopy, coachProgress } = setup()
    expect(coachCopy.value).toBe('先听我读一次')
    expect(coachProgress.value).toBe('第 1/9 句')
  })

  it('选词后：解读 "<word>"', () => {
    const { coachCopy } = setup({ selectedWord: ref({ word: 'schedule', display: 'schedule' }) })
    expect(coachCopy.value).toBe('解读 "schedule"')
  })

  it('TTS 播放中：听着…', () => {
    const { coachCopy } = setup({ isPlayingTTS: ref(true) })
    expect(coachCopy.value).toBe('听着…')
  })

  it('录音中：录音中 · 念完点停止', () => {
    const { coachCopy, coachClass } = setup({ recording: ref(true) })
    expect(coachCopy.value).toBe('录音中 · 念完点停止')
    expect(coachClass.value).toBe('recording')
  })

  it('录完未回放：收到了 · 回放听听自己', () => {
    const { coachCopy } = setup({ hasRecording: ref(true) })
    expect(coachCopy.value).toBe('收到了 · 回放听听自己')
  })

  it('录完已回放：比一比，节奏对齐了吗', () => {
    const { coachCopy } = setup({
      hasRecording: ref(true),
      hasPlayedBack: ref(true),
    })
    expect(coachCopy.value).toBe('比一比，节奏对齐了吗')
  })

  it('已完成 N 句时进度带 · 已完成 N', () => {
    const { coachProgress } = setup({
      currentIdx: ref(2),
      practicedCount: ref(3),
    })
    expect(coachProgress.value).toBe('第 3/9 句 · 已完成 3')
  })

  it('状态优先级：录音 > TTS > 选词 > 录完 > 空闲', () => {
    const { coachCopy } = setup({
      selectedWord: ref({ word: 'x', display: 'x' }),
      hasRecording: ref(true),
      recording: ref(true),
    })
    expect(coachCopy.value).toBe('录音中 · 念完点停止')
  })
})
