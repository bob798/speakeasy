/**
 * useSTT · 语音转文字三层架构
 *
 * 迁移自 static/js/stt-provider.js，保留语义：
 * - L1 用户主动 stop
 * - L2 AudioVAD 静音 2s → （可选倒计时）→ 自动 stop
 * - L3 12s 绝对超时兜底
 *
 * 改造点（Architect MF3 + Critic REV-6）：
 * - 移除 window.startCountdown/stopCountdown 全局后门
 * - 倒计时通过调用方注入的 callbacks 参数驱动
 * - Vue 组件 unmount 时自动释放 stream/recorder/VAD
 *
 * @typedef {{ type: string, message?: string }} STTError
 * @typedef {Object} STTStartOptions
 * @property {(text: string) => void} [onInterim]
 * @property {(text: string) => void} onFinal
 * @property {(err: STTError) => void} onError
 * @property {(ms: number, done: () => void) => void} [onCountdownStart] · L2 静音时触发
 * @property {() => void} [onCountdownCancel] · 检测到声音时触发
 */

import { ref, onBeforeUnmount } from 'vue'
import { AudioVAD } from '@/lib/AudioVAD'
import { useAuthStore } from '@/stores/auth'

const DEFAULTS = {
  silenceThresholdDb: -35,
  silenceDurationMs: 2000,
  absTimeoutMs: 12000,
  countdownMs: 3000, // hands-free 传 0 跳过
  endpoint: '/stt',
  fetchTimeoutMs: 15000,
}

export function useSTT(opts = {}) {
  const config = { ...DEFAULTS, ...opts }
  const recording = ref(false)

  let _stream = null
  let _rec = null
  let _vad = null
  let _absTimer = null
  let _cancelled = false
  let _callbacks = null // STTStartOptions

  function isSupported() {
    return (
      !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia) &&
      !!(window.AudioContext || window.webkitAudioContext) &&
      (location.protocol === 'https:' ||
        location.hostname === 'localhost' ||
        location.hostname === '127.0.0.1')
    )
  }

  /**
   * @param {STTStartOptions} options
   */
  async function start(options) {
    if (recording.value) return
    _callbacks = options
    _cancelled = false
    recording.value = true

    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (e) {
      recording.value = false
      if (e.name === 'NotAllowedError') {
        options.onError({ type: 'PERMISSION_DENIED' })
      } else {
        options.onError({ type: 'DEVICE', message: e.message })
      }
      return
    }

    if (_cancelled) {
      stream.getTracks().forEach((t) => t.stop())
      recording.value = false
      return
    }
    _stream = stream

    const mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg'
    _rec = new MediaRecorder(stream, { mimeType: mime })
    const chunks = []

    _rec.ondataavailable = (e) => {
      if (e.data.size) chunks.push(e.data)
    }
    _rec.onstop = async () => {
      _cleanup()
      if (_cancelled) return
      if (!chunks.length) {
        options.onError({ type: 'EMPTY' })
        return
      }
      const blob = new Blob(chunks, { type: mime })
      const form = new FormData()
      form.append('audio', blob, 'audio.' + (mime.includes('webm') ? 'webm' : 'ogg'))

      const ctrl = new AbortController()
      const fetchTimer = setTimeout(() => ctrl.abort(), config.fetchTimeoutMs)
      try {
        const authStore = useAuthStore()
        const headers = {}
        if (authStore.token) headers['Authorization'] = 'Bearer ' + authStore.token
        const res = await fetch(config.endpoint, {
          method: 'POST',
          body: form,
          headers,
          signal: ctrl.signal,
        })
        clearTimeout(fetchTimer)
        const data = await res.json()
        if (!res.ok) {
          if (data.fallback === 'webspeech') {
            options.onError({ type: 'FALLBACK' })
          } else {
            options.onError({ type: 'SERVER', message: data.error })
          }
        } else if (!data.text || !data.text.trim()) {
          options.onError({ type: 'EMPTY' })
        } else {
          options.onFinal(data.text.trim())
        }
      } catch (e) {
        clearTimeout(fetchTimer)
        options.onError({
          type: e.name === 'AbortError' ? 'EMPTY' : 'NETWORK',
          message: e.message,
        })
      }
    }

    // L2 VAD
    _vad = new AudioVAD(stream, {
      silenceThresholdDb: config.silenceThresholdDb,
      silenceDurationMs: config.silenceDurationMs,
      onSilence: () => {
        if (config.countdownMs > 0 && typeof options.onCountdownStart === 'function') {
          options.onCountdownStart(config.countdownMs, () => stop())
        } else {
          stop()
        }
      },
      onVoice: () => {
        options.onCountdownCancel?.()
      },
    })

    _rec.start()
    _vad.start()

    // L3 绝对超时
    _absTimer = setTimeout(() => stop(), config.absTimeoutMs)
  }

  function stop() {
    if (!recording.value) return
    clearTimeout(_absTimer)
    _callbacks?.onCountdownCancel?.()
    _vad?.stop()
    if (_rec?.state === 'recording') {
      _rec.stop()
    } else if (!_rec) {
      _cancelled = true
      _callbacks?.onError?.({ type: 'EMPTY' })
    }
    recording.value = false
  }

  function cancel() {
    _cancelled = true
    clearTimeout(_absTimer)
    _callbacks?.onCountdownCancel?.()
    _vad?.stop()
    if (_rec) {
      _rec.ondataavailable = null
      _rec.onstop = null
      if (_rec.state === 'recording') _rec.stop()
    }
    _cleanup()
    recording.value = false
  }

  function _cleanup() {
    _stream?.getTracks().forEach((t) => t.stop())
    _stream = null
  }

  onBeforeUnmount(() => {
    cancel()
  })

  return {
    recording,
    isSupported,
    start,
    stop,
    cancel,
  }
}
