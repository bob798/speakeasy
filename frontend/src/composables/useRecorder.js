/**
 * useRecorder · 纯 MediaRecorder 录音（不走 STT）
 * Practice 用来做"录音对比"：录下 blob → URL.createObjectURL → 与 TTS 原音对比播放
 *
 * 与 useSTT 的区别：
 * - useSTT: 录音 + VAD + 倒计时 + 发 /stt 转文字
 * - useRecorder: 只录音 + 返回 Blob，不发网络
 */

import { ref, onBeforeUnmount } from 'vue'

export function useRecorder() {
  const recording = ref(false)
  const blob = ref(null)
  const url = ref(null)
  const error = ref('')

  let _rec = null
  let _stream = null
  let _chunks = []

  function isSupported() {
    return (
      !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia) &&
      (location.protocol === 'https:' ||
        location.hostname === 'localhost' ||
        location.hostname === '127.0.0.1')
    )
  }

  async function start() {
    if (recording.value) return
    error.value = ''
    _release()

    try {
      _stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (e) {
      error.value =
        e.name === 'NotAllowedError' ? '请在浏览器设置中允许麦克风权限' : '录音设备错误'
      return
    }

    const mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg'
    _rec = new MediaRecorder(_stream, { mimeType: mime })
    _chunks = []

    _rec.ondataavailable = (e) => {
      if (e.data.size) _chunks.push(e.data)
    }
    _rec.onstop = () => {
      if (_chunks.length) {
        blob.value = new Blob(_chunks, { type: mime })
        if (url.value) URL.revokeObjectURL(url.value)
        url.value = URL.createObjectURL(blob.value)
      }
      _stopTracks()
      recording.value = false
    }

    _rec.start()
    recording.value = true
  }

  function stop() {
    if (_rec && _rec.state === 'recording') {
      _rec.stop()
    } else {
      _stopTracks()
      recording.value = false
    }
  }

  function reset() {
    stop()
    if (url.value) {
      URL.revokeObjectURL(url.value)
      url.value = null
    }
    blob.value = null
    error.value = ''
  }

  function _stopTracks() {
    _stream?.getTracks().forEach((t) => t.stop())
    _stream = null
  }

  function _release() {
    if (url.value) {
      URL.revokeObjectURL(url.value)
      url.value = null
    }
    blob.value = null
  }

  onBeforeUnmount(() => {
    reset()
  })

  return {
    recording,
    blob,
    url,
    error,
    isSupported,
    start,
    stop,
    reset,
  }
}
