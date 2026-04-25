/**
 * useCountdown · Push-to-talk 倒计时环
 *
 * 替代 static/js/index.html 里的全局 startCountdown/stopCountdown，
 * 移除 stt-provider.js:149-158 对 window 全局函数的后门依赖（Architect MF3 + Critic REV-6）。
 *
 * 强约束：
 * - 不挂 window.startCountdown / window.stopCountdown
 * - 不提供全局后门
 * - 所有触发路径必须通过本 composable 返回的函数引用
 *
 * @typedef {Object} CountdownApi
 * @property {import('vue').Ref<number>} remainingMs
 * @property {import('vue').Ref<boolean>} active
 * @property {(ms: number, onExpire: () => void) => void} start
 * @property {() => void} stop
 */

import { ref, onBeforeUnmount } from 'vue'

/**
 * @returns {CountdownApi}
 */
export function useCountdown() {
  const remainingMs = ref(0)
  const active = ref(false)

  let _timer = null
  let _raf = null
  let _expireCb = null
  let _endAt = 0

  /**
   * @param {number} ms 总倒计时毫秒
   * @param {() => void} onExpire 到期回调
   */
  function start(ms, onExpire) {
    stop()
    if (!ms || ms <= 0) {
      // 零倒计时 → 立即触发（兼容 hands-free 模式）
      onExpire?.()
      return
    }
    _expireCb = onExpire
    _endAt = performance.now() + ms
    active.value = true
    remainingMs.value = ms

    // setTimeout 负责到期触发（精确）；rAF 负责 UI 刷新（平滑）
    _timer = setTimeout(() => {
      active.value = false
      remainingMs.value = 0
      const cb = _expireCb
      _expireCb = null
      cb?.()
    }, ms)

    const tick = () => {
      if (!active.value) return
      const left = Math.max(0, _endAt - performance.now())
      remainingMs.value = left
      if (left > 0) {
        _raf = requestAnimationFrame(tick)
      }
    }
    _raf = requestAnimationFrame(tick)
  }

  function stop() {
    if (_timer) {
      clearTimeout(_timer)
      _timer = null
    }
    if (_raf) {
      cancelAnimationFrame(_raf)
      _raf = null
    }
    active.value = false
    remainingMs.value = 0
    _expireCb = null
  }

  onBeforeUnmount(() => {
    stop()
  })

  return {
    remainingMs,
    active,
    start,
    stop,
  }
}
