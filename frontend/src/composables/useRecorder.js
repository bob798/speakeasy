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
  // codex review (#32): start session 序号，让 reset()/再次 start() 后晚到的 onstop 不再污染 blob/url
  let _startSeq = 0

  function isSupported() {
    // codex review (#32): 同时校验 MediaRecorder 存在；某些手机浏览器（如旧版 iOS Safari）
    // 有 mediaDevices 但缺 MediaRecorder，构造时直接 ReferenceError
    return (
      !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia) &&
      typeof MediaRecorder !== 'undefined' &&
      (location.protocol === 'https:' ||
        location.hostname === 'localhost' ||
        location.hostname === '127.0.0.1')
    )
  }

  async function start() {
    if (recording.value) return
    error.value = ''
    _release()
    _startSeq++
    const mySeq = _startSeq

    try {
      _stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (e) {
      error.value =
        e.name === 'NotAllowedError' ? '请在浏览器设置中允许麦克风权限' : '录音设备错误'
      return
    }

    // 若 await 期间 reset()/再次 start() 把 _startSeq 推进了，本次 start 作废
    if (mySeq !== _startSeq) {
      _stream?.getTracks().forEach((t) => t.stop())
      _stream = null
      return
    }

    const mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg'
    _rec = new MediaRecorder(_stream, { mimeType: mime })
    _chunks = []

    _rec.ondataavailable = (e) => {
      if (mySeq !== _startSeq) return       // stale 来自旧 session 的事件
      if (e.data.size) _chunks.push(e.data)
    }
    _rec.onstop = () => {
      // 来自旧 session 的 onstop（reset/重启后）：只清 stream，不写 blob/url
      if (mySeq !== _startSeq) {
        _stopTracks()
        return
      }
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
    // 推进 session 序号 → 在飞 / 排队的 onstop 看到不匹配会自动作废
    _startSeq++
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
