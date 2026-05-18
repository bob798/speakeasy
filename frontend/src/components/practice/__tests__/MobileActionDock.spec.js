/**
 * MobileActionDock · 评分模式 (#26)
 *
 * 覆盖：
 *  - ratingMode=false 时显示默认 record/playback 行，不渲染评分按钮
 *  - ratingMode=true 时显示评分 4 按钮 + 回放/重录
 *  - 点 4 个评分按钮各 emit('rate', 对应 level)
 *  - 点重录 emit('redo-record')
 *  - ratingBusy=true 时评分按钮全 disabled
 */
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/composables/useCoachBar', () => ({
  useCoachBar: () => ({
    coachCopy: { value: 'practice' },
    coachClass: { value: '' },
    coachProgress: { value: '1 / 10' },
  }),
}))

import MobileActionDock from '../MobileActionDock.vue'

function mountDock(props = {}) {
  return mount(MobileActionDock, {
    props: {
      currentIdx: 0,
      totalSegments: 10,
      practicedCount: 0,
      ...props,
    },
  })
}

describe('MobileActionDock · 评分模式 (#26)', () => {
  it('默认模式：渲染录音/回放，不渲染评分按钮', () => {
    const w = mountDock({ ratingMode: false })
    expect(w.find('.dock-btn.record').exists()).toBe(true)
    expect(w.findAll('.rate').length).toBe(0)
  })

  it('评分模式：渲染 4 个评分按钮 + 回放 + 重录，隐藏 explain/speak 行', () => {
    const w = mountDock({ ratingMode: true, hasRecording: true })
    const rateBtns = w.findAll('.rate')
    expect(rateBtns.length).toBe(4)
    expect(rateBtns[0].text()).toBe('Again')
    expect(rateBtns[1].text()).toBe('Hard')
    expect(rateBtns[2].text()).toBe('Good')
    expect(rateBtns[3].text()).toBe('Easy')
    // 默认模式的录音/语音按钮不在
    expect(w.find('.dock-btn.record').exists()).toBe(false)
    // 评分模式 dock 里有重录按钮（aria-label 含「重新录」）
    const labels = w.findAll('.dock-btn').map((b) => b.attributes('aria-label') || '')
    expect(labels.some((l) => l.includes('重新录'))).toBe(true)
    expect(labels.some((l) => l.includes('回放'))).toBe(true)
  })

  it.each([
    ['again', 0],
    ['hard',  1],
    ['good',  2],
    ['easy',  3],
  ])('点 %s → emit rate with %s', async (level, idx) => {
    const w = mountDock({ ratingMode: true, hasRecording: true })
    await w.findAll('.rate')[idx].trigger('click')
    expect(w.emitted('rate')).toBeTruthy()
    expect(w.emitted('rate')[0]).toEqual([level])
  })

  it('点重录按钮 → emit redo-record', async () => {
    const w = mountDock({ ratingMode: true, hasRecording: true })
    const redoBtn = w.findAll('.dock-btn').find((b) =>
      (b.attributes('aria-label') || '').includes('重新录')
    )
    expect(redoBtn).toBeTruthy()
    await redoBtn.trigger('click')
    expect(w.emitted('redo-record')).toBeTruthy()
  })

  it('ratingBusy=true → 4 个评分按钮均 disabled', () => {
    const w = mountDock({ ratingMode: true, ratingBusy: true, hasRecording: true })
    const rateBtns = w.findAll('.rate')
    for (const btn of rateBtns) {
      expect(btn.attributes('disabled')).toBeDefined()
    }
  })

  it('ratingBusy=true → 回放/重录也 disabled (codex review)', () => {
    // 防止评分请求在飞期间用户点重录把新录音 reset 掉 / 跳句错位
    const w = mountDock({ ratingMode: true, ratingBusy: true, hasRecording: true })
    const labels = w.findAll('.dock-btn')
    const redo = labels.find((b) => (b.attributes('aria-label') || '').includes('重新录'))
    const playback = labels.find((b) => (b.attributes('aria-label') || '').includes('回放'))
    expect(redo).toBeTruthy()
    expect(playback).toBeTruthy()
    expect(redo.attributes('disabled')).toBeDefined()
    expect(playback.attributes('disabled')).toBeDefined()
  })
})
