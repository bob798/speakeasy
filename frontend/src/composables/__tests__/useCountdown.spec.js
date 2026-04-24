/**
 * useCountdown 单测 · 倒计时核心行为
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useCountdown } from '../useCountdown'

describe('useCountdown', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('0ms 或负数 · 立即触发 onExpire', () => {
    const { start, active } = useCountdown()
    const cb = vi.fn()
    start(0, cb)
    expect(cb).toHaveBeenCalledTimes(1)
    expect(active.value).toBe(false)
  })

  it('正常倒计时到期触发 onExpire', () => {
    const { start, active } = useCountdown()
    const cb = vi.fn()
    start(3000, cb)
    expect(active.value).toBe(true)
    expect(cb).not.toHaveBeenCalled()

    vi.advanceTimersByTime(3000)
    expect(cb).toHaveBeenCalledTimes(1)
    expect(active.value).toBe(false)
  })

  it('stop() 在到期前取消', () => {
    const { start, stop, active } = useCountdown()
    const cb = vi.fn()
    start(3000, cb)
    vi.advanceTimersByTime(1500)
    stop()
    vi.advanceTimersByTime(5000)
    expect(cb).not.toHaveBeenCalled()
    expect(active.value).toBe(false)
  })

  it('连续 start · 前一个被覆盖', () => {
    const { start, active } = useCountdown()
    const cb1 = vi.fn()
    const cb2 = vi.fn()
    start(3000, cb1)
    start(1000, cb2)
    vi.advanceTimersByTime(1000)
    expect(cb1).not.toHaveBeenCalled()
    expect(cb2).toHaveBeenCalledTimes(1)
    expect(active.value).toBe(false)
  })

  it('不提供全局后门 · window.startCountdown 不存在', () => {
    useCountdown()
    expect(typeof window.startCountdown).toBe('undefined')
    expect(typeof window.stopCountdown).toBe('undefined')
  })
})
