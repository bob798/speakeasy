// ── STT Provider 类 ──────────────────────────────────────────────────────

/**
 * AudioVAD — Web Audio API 音量检测
 * 持续监测麦克风音量，区分"有声音"和"静音"状态。
 */
class AudioVAD {
  constructor(stream, {
    silenceThresholdDb = -45,   // 宽松阈值，适合语言学习者
    silenceDurationMs  = 2000,  // 2 秒静音触发 onSilence
    onSilence = () => {},
    onVoice   = () => {},
  } = {}) {
    this._onSilence = onSilence;
    this._onVoice   = onVoice;
    this._thresholdDb  = silenceThresholdDb;
    this._silenceDurationMs = silenceDurationMs;

    const AC = window.AudioContext || window.webkitAudioContext;
    this._ctx     = new AC();
    this._analyser = this._ctx.createAnalyser();
    this._analyser.fftSize = 256;
    this._src = this._ctx.createMediaStreamSource(stream);
    this._src.connect(this._analyser);

    this._data     = new Uint8Array(this._analyser.frequencyBinCount);
    this._speaking = false;
    this._silenceStart = null;
    this._raf = null;
    this._stopped = false;
  }

  start() {
    const tick = () => {
      if (this._stopped) return;
      this._analyser.getByteFrequencyData(this._data);
      // 取平均能量转为 dB
      const avg = this._data.reduce((s, v) => s + v, 0) / this._data.length;
      const db  = avg > 0 ? 20 * Math.log10(avg / 255) : -Infinity;

      if (db > this._thresholdDb) {
        // 有声
        this._silenceStart = null;
        if (!this._speaking) {
          this._speaking = true;
          this._onVoice();
        }
      } else {
        // 静音
        if (this._speaking) {
          if (!this._silenceStart) this._silenceStart = performance.now();
          if (performance.now() - this._silenceStart >= this._silenceDurationMs) {
            this._speaking = false;
            this._silenceStart = null;
            this._onSilence();
          }
        }
      }
      this._raf = requestAnimationFrame(tick);
    };
    this._raf = requestAnimationFrame(tick);
  }

  stop() {
    this._stopped = true;
    if (this._raf) { cancelAnimationFrame(this._raf); this._raf = null; }
    try { this._ctx.close(); } catch (_) {}
  }
}

class STTProvider {
  isSupported() { return false; }
  start(onInterim, onFinal, onError) {}
  stop() {}
  cancel() {}
}

/**
 * ServerSTTProvider — 三层检测架构
 *   L1: 用户点击停止（主动）
 *   L2: AudioVAD 检测到 2 秒静音 → startCountdown(3000) → 自动停止
 *   L3: 30 秒绝对超时兜底
 */
class ServerSTTProvider extends STTProvider {
  constructor() {
    super();
    this.silenceThresholdDb = -45;
    this.silenceDurationMs  = 2000;
    this.absTimeout         = 30000;
  }

  isSupported() {
    return !!(navigator.mediaDevices?.getUserMedia) &&
           !!(window.AudioContext || window.webkitAudioContext) &&
           (
             location.protocol === 'https:' ||
             location.hostname === 'localhost' ||
             location.hostname === '127.0.0.1'
           );
  }

  start(onInterim, onFinal, onError) {
    this._cancelled = false;
    this._onError = onError;

    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => {
        if (this._cancelled) { stream.getTracks().forEach(t => t.stop()); return; }
        this._stream = stream;

        const mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg';
        this._rec = new MediaRecorder(stream, { mimeType: mime });
        const chunks = [];
        this._rec.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
        this._rec.onstop = async () => {
          this._cleanup();
          if (this._cancelled) return;
          if (!chunks.length) { onError({ type: 'EMPTY' }); return; }
          const blob = new Blob(chunks, { type: mime });
          const form = new FormData();
          form.append('audio', blob, 'audio.' + (mime.includes('webm') ? 'webm' : 'ogg'));
          const ctrl = new AbortController();
          const fetchTimer = setTimeout(() => ctrl.abort(), 15000);
          try {
            const res  = await fetch('/stt', { method: 'POST', body: form, signal: ctrl.signal });
            clearTimeout(fetchTimer);
            const data = await res.json();
            if (!res.ok) {
              if (data.fallback === 'webspeech') { onError({ type: 'FALLBACK' }); return; }
              onError({ type: 'SERVER', message: data.error });
            } else if (!data.text?.trim()) {
              onError({ type: 'EMPTY' });
            } else {
              onFinal(data.text.trim());
            }
          } catch (e) {
            clearTimeout(fetchTimer);
            onError({ type: e.name === 'AbortError' ? 'EMPTY' : 'NETWORK', message: e.message });
          }
        };

        // L2: VAD 静音检测
        this._vad = new AudioVAD(stream, {
          silenceThresholdDb: this.silenceThresholdDb,
          silenceDurationMs:  this.silenceDurationMs,
          onSilence: () => {
            // 静音 2 秒 → 启动 3 秒倒计时，倒计时结束自动停止
            if (typeof startCountdown === 'function') {
              startCountdown(3000, () => this.stop());
            } else {
              this.stop();
            }
          },
          onVoice: () => {
            // 检测到声音 → 取消倒计时
            if (typeof stopCountdown === 'function') stopCountdown();
          },
        });

        this._rec.start();
        this._vad.start();

        // L3: 绝对超时兜底
        this._absTimer = setTimeout(() => this.stop(), this.absTimeout);
      })
      .catch(e => {
        if (e.name === 'NotAllowedError') onError({ type: 'PERMISSION_DENIED' });
        else onError({ type: 'DEVICE', message: e.message });
      });
  }

  // L1: 用户主动点击停止
  stop() {
    clearTimeout(this._absTimer);
    if (typeof stopCountdown === 'function') stopCountdown();
    this._vad?.stop();
    if (this._rec?.state === 'recording') {
      this._rec.stop();
    } else if (!this._rec) {
      // getUserMedia 尚未 resolve，阻止后续 then() 执行
      this._cancelled = true;
      this._onError?.({ type: 'EMPTY' });
    }
  }

  cancel() {
    this._cancelled = true;
    clearTimeout(this._absTimer);
    if (typeof stopCountdown === 'function') stopCountdown();
    this._vad?.stop();
    if (this._rec) { this._rec.ondataavailable = null; this._rec.onstop = null; }
    if (this._rec?.state === 'recording') this._rec.stop();
    this._cleanup();
  }

  _cleanup() {
    this._stream?.getTracks().forEach(t => t.stop());
    this._stream = null;
  }
}

class WebSpeechSTTProvider extends STTProvider {
  isSupported() {
    return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  }

  start(onInterim, onFinal, onError) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    this._sr = new SR();
    this._sr.lang = 'en-US';
    this._sr.interimResults = true;
    this._sr.continuous = false;
    let _called = false;
    this._sr.onresult = e => {
      let interim = '', final = '';
      for (const r of e.results) {
        if (r.isFinal) final += r[0].transcript;
        else interim += r[0].transcript;
      }
      if (interim) onInterim(interim);
      if (final) { _called = true; onFinal(final.trim()); }
    };
    this._sr.onerror = e => {
      _called = true;
      if (e.error === 'not-allowed') onError({ type: 'PERMISSION_DENIED' });
      else onError({ type: 'SR_ERROR', message: e.error });
    };
    // onend 在 onresult/onerror 未触发时兜底重置状态
    this._sr.onend = () => {
      if (!_called) onError({ type: 'EMPTY' });
    };
    this._sr.start();
  }

  stop()   { this._sr?.stop(); }
  cancel() { this._sr?.abort(); }
}

function createSTTProvider() { return new ServerSTTProvider(); }
