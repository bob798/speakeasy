/**
 * useTTS · 服务器 TTS + WebSpeech 降级 + 队列
 *
 * 迁移自 static/js/tts-provider.js，保留：
 * - ServerTTSProvider → 调用 /tts 返回 mp3 → new Audio 播放
 * - 降级链：Audio 失败 / autoplay blocked → WebSpeech
 * - TTSQueue 支持 enqueue/clear；Vue 组件 unmount 自动 clear
 *
 * @typedef {Object} TTSApi
 * @property {import('vue').Ref<boolean>} playing
 * @property {(text: string, opts?: { manual?: boolean }) => void} enqueue · manual=true 清空后插队
 * @property {() => void} clear
 * @property {() => void} stop · 立即停止当前播放
 */

import { ref, onBeforeUnmount } from 'vue'

const TTS_ENDPOINT = '/tts'

function _webSpeechSpeak(text, onStart, onEnd) {
  if (!window.speechSynthesis) {
    onEnd()
    return
  }
  window.speechSynthesis.cancel()
  const doSpeak = () => {
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'en-US'
    u.rate = 0.9
    const v = speechSynthesis.getVoices().find((v) => v.lang.startsWith('en'))
    if (v) u.voice = v
    u.onstart = onStart
    u.onend = onEnd
    u.onerror = () => onEnd()
    speechSynthesis.speak(u)
  }
  const voices = speechSynthesis.getVoices()
  if (voices.length) {
    doSpeak()
  } else {
    speechSynthesis.onvoiceschanged = () => {
      speechSynthesis.onvoiceschanged = null
      doSpeak()
    }
  }
}

/**
 * @returns {TTSApi}
 */
export function useTTS() {
  const playing = ref(false)
  let _audio = null
  let _queue = []
  let _busy = false

  async function _speakOne(text, onStart, onEnd) {
    try {
      const res = await fetch(TTS_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        if (d.fallback === 'webspeech') {
          _webSpeechSpeak(text, onStart, onEnd)
          return
        }
        throw new Error(d.error || 'TTS_FAILED')
      }
      const url = URL.createObjectURL(await res.blob())
      _audio = new Audio(url)
      _audio.onplay = onStart
      _audio.onended = () => {
        URL.revokeObjectURL(url)
        _audio = null
        onEnd()
      }
      _audio.onerror = () => {
        URL.revokeObjectURL(url)
        _audio = null
        _webSpeechSpeak(text, onStart, onEnd)
      }
      try {
        await _audio.play()
      } catch {
        URL.revokeObjectURL(url)
        _audio = null
        _webSpeechSpeak(text, onStart, onEnd)
      }
    } catch (err) {
      console.warn('[useTTS]', err)
      _webSpeechSpeak(text, onStart, onEnd)
    }
  }

  async function _drainQueue() {
    if (!_queue.length) {
      _busy = false
      playing.value = false
      return
    }
    _busy = true
    const text = _queue.shift()
    await new Promise((resolve) => {
      _speakOne(
        text,
        () => (playing.value = true),
        () => resolve()
      )
    })
    _drainQueue()
  }

  /**
   * @param {string} text
   * @param {{ manual?: boolean }} [opts] · manual=true 清空队列插队
   */
  function enqueue(text, opts = {}) {
    if (opts.manual) {
      clear()
    }
    _queue.push(text)
    if (!_busy) _drainQueue()
  }

  function stop() {
    if (_audio) {
      _audio.pause()
      _audio.src = ''
      _audio = null
    }
    if (window.speechSynthesis) window.speechSynthesis.cancel()
    playing.value = false
  }

  function clear() {
    _queue = []
    stop()
    _busy = false
  }

  onBeforeUnmount(() => {
    clear()
  })

  return {
    playing,
    enqueue,
    clear,
    stop,
  }
}
