class TTSProvider {
    isSupported() { return false; }
    async speak(text, onStart, onEnd, onError) {}
    stop() {}
}

class ServerTTSProvider extends TTSProvider {
    isSupported() { return true; }

    async speak(text, onStart, onEnd, onError) {
        try {
            const res = await fetch(CONFIG.TTS_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text })
            });
            if (!res.ok) {
                const d = await res.json();
                if (d.fallback === 'webspeech') { this._ws(text, onStart, onEnd, onError); return; }
                throw new Error(d.error || 'TTS_FAILED');
            }
            const url = URL.createObjectURL(await res.blob());
            this._audio = new Audio(url);
            this._audio.onplay  = onStart;
            this._audio.onended = () => { URL.revokeObjectURL(url); this._audio = null; onEnd(); };
            // audio 元素自身出错 → 降级 WebSpeech
            this._audio.onerror = () => {
                URL.revokeObjectURL(url);
                this._audio = null;
                this._ws(text, onStart, onEnd, onError);
            };
            // play() 被浏览器自动播放策略拒绝 → 降级 WebSpeech
            await this._audio.play().catch((e) => {
                URL.revokeObjectURL(url);
                this._audio = null;
                this._ws(text, onStart, onEnd, onError);
            });
        } catch (e) {
            console.error('[TTS]', e);
            this._ws(text, onStart, onEnd, onError);
        }
    }

    stop() {
        if (this._audio) { this._audio.pause(); this._audio.src = ''; this._audio = null; }
        if (window.speechSynthesis) window.speechSynthesis.cancel();
    }

    // WebSpeech 降级：等待 voices 加载完毕再播
    _ws(text, onStart, onEnd, _onError) {
        if (!window.speechSynthesis) { onEnd(); return; }
        window.speechSynthesis.cancel();
        const doSpeak = () => {
            const u = new SpeechSynthesisUtterance(text);
            u.lang = 'en-US';
            u.rate = 0.9;
            const v = speechSynthesis.getVoices().find(v => v.lang.startsWith('en'));
            if (v) u.voice = v;
            u.onstart = onStart;
            u.onend   = onEnd;
            u.onerror = () => onEnd(); // 出错也推进队列，不卡死
            speechSynthesis.speak(u);
        };
        const voices = speechSynthesis.getVoices();
        if (voices.length) {
            doSpeak();
        } else {
            speechSynthesis.onvoiceschanged = () => {
                speechSynthesis.onvoiceschanged = null;
                doSpeak();
            };
        }
    }
}

class TTSQueue {
    constructor(provider) { this.p = provider; this.q = []; this.busy = false; }

    enqueue(text, manual = false) {
        if (manual) { this.q = []; this.p.stop(); this.busy = false; }
        this.q.push(text);
        if (!this.busy) this._next();
    }

    clear() { this.q = []; this.p.stop(); this.busy = false; }

    async _next() {
        if (!this.q.length) { this.busy = false; return; }
        this.busy = true;
        await new Promise(resolve => this.p.speak(this.q.shift(), () => {}, resolve, resolve));
        this._next();
    }
}

function createTTSProvider() { return new ServerTTSProvider(); }
