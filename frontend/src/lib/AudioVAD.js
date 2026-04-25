/**
 * AudioVAD · Web Audio API 音量检测（从 static/js/stt-provider.js:7-69 迁出）
 *
 * 保留为 class 不做 composable 化，因为 requestAnimationFrame 高频 tick
 * + 内部 mutable state 用 class 最直接（Architect MF3 + Pass 3 设计决策）。
 *
 * 调用方（如 useSTT）通过构造函数注入回调，避免全局函数后门。
 *
 * @typedef {Object} AudioVADOptions
 * @property {number} [silenceThresholdDb=-35] 静音阈值(dB)
 * @property {number} [silenceDurationMs=2000] 连续静音多久触发 onSilence
 * @property {() => void} [onSilence]
 * @property {() => void} [onVoice]
 */

export class AudioVAD {
  /**
   * @param {MediaStream} stream
   * @param {AudioVADOptions} [opts]
   */
  constructor(stream, opts = {}) {
    const {
      silenceThresholdDb = -35,
      silenceDurationMs = 2000,
      onSilence = () => {},
      onVoice = () => {},
    } = opts

    this._onSilence = onSilence
    this._onVoice = onVoice
    this._thresholdDb = silenceThresholdDb
    this._silenceDurationMs = silenceDurationMs

    const AC = window.AudioContext || window.webkitAudioContext
    this._ctx = new AC()
    this._analyser = this._ctx.createAnalyser()
    this._analyser.fftSize = 256
    this._src = this._ctx.createMediaStreamSource(stream)
    this._src.connect(this._analyser)

    this._data = new Uint8Array(this._analyser.frequencyBinCount)
    this._speaking = false
    this._silenceStart = null
    this._raf = null
    this._stopped = false
  }

  start() {
    const tick = () => {
      if (this._stopped) return
      this._analyser.getByteFrequencyData(this._data)
      const avg = this._data.reduce((s, v) => s + v, 0) / this._data.length
      const db = avg > 0 ? 20 * Math.log10(avg / 255) : -Infinity

      if (db > this._thresholdDb) {
        this._silenceStart = null
        if (!this._speaking) {
          this._speaking = true
          this._onVoice()
        }
      } else {
        if (this._speaking) {
          if (!this._silenceStart) this._silenceStart = performance.now()
          if (performance.now() - this._silenceStart >= this._silenceDurationMs) {
            this._speaking = false
            this._silenceStart = null
            this._onSilence()
          }
        }
      }
      this._raf = requestAnimationFrame(tick)
    }
    this._raf = requestAnimationFrame(tick)
  }

  stop() {
    this._stopped = true
    if (this._raf) {
      cancelAnimationFrame(this._raf)
      this._raf = null
    }
    try {
      this._ctx.close()
    } catch {
      /* ignore already-closed */
    }
  }
}
