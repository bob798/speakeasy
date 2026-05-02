/**
 * useVoiceCommand · 连续语音命令（demo · V0.10 P8）
 *
 * 包装 useSTT 形成"听 → 识别 → 匹配关键词 → 触发动作 → 再听"的循环。
 *
 * 设计选择（demo 阶段）：
 * - 关键词匹配：normalize 后做包含匹配；命中第一个就触发
 * - 多语言：中文别名 → 命令；英文直接匹配命令名
 * - 失败安全：未识别 / 网络错 / 麦克风拒绝 → 停止 active，反馈给上层
 * - 不接 LLM 兜底（demo 先看够不够用）
 *
 * 用法：
 *   const vc = useVoiceCommand({
 *     commands: {
 *       again: () => rate('again'),
 *       good:  () => rate('good'),
 *     },
 *     aliases: {
 *       '再来':   'again',
 *       '可以':   'good',
 *       '不会':   'again',
 *     },
 *     onUnmatched: (text) => console.log('未识别:', text),
 *     onError:     (err) => toast(err),
 *   })
 *   vc.start()  // 进入持续听
 *   vc.stop()   // 退出
 *
 * @typedef {Record<string, () => void | Promise<void>>} CommandMap
 * @typedef {Record<string, string>} AliasMap
 */
import { ref, onBeforeUnmount } from 'vue'
import { useSTT } from './useSTT'

const RESTART_GAP_MS = 250  // 每次识别后稍等一下再重启监听

function normalize(text) {
  return (text || '')
    .toLowerCase()
    .replace(/[。，、？！.!?,]/g, '')
    .trim()
}

/**
 * @param {{ commands: CommandMap, aliases?: AliasMap, onMatched?: (cmd:string,text:string)=>void, onUnmatched?: (text:string)=>void, onError?: (err:any)=>void }} opts
 */
export function useVoiceCommand(opts) {
  const stt = useSTT({ countdownMs: 0 }) // 倒计时关掉 · 静音直接 stop
  const active = ref(false)
  const listening = stt.recording
  const lastHeard = ref('')
  const lastCommand = ref('')
  let _restartTimer = null

  function _matchCommand(text) {
    const normalized = normalize(text)
    if (!normalized) return null

    // 1. 直接命中命令名
    for (const cmd of Object.keys(opts.commands || {})) {
      if (normalized.includes(cmd.toLowerCase())) return cmd
    }
    // 2. 别名命中
    for (const [alias, cmd] of Object.entries(opts.aliases || {})) {
      if (normalized.includes(alias.toLowerCase())) return cmd
    }
    return null
  }

  function _scheduleRestart() {
    if (!active.value) return
    clearTimeout(_restartTimer)
    _restartTimer = setTimeout(() => {
      if (active.value) _listenOnce()
    }, RESTART_GAP_MS)
  }

  async function _listenOnce() {
    if (!active.value) return
    if (listening.value) return
    await stt.start({
      onFinal: (text) => {
        lastHeard.value = text
        const cmd = _matchCommand(text)
        if (cmd) {
          lastCommand.value = cmd
          try {
            const fn = opts.commands[cmd]
            if (typeof fn === 'function') fn()
            opts.onMatched?.(cmd, text)
          } catch (err) {
            opts.onError?.({ type: 'HANDLER', message: err?.message })
          }
        } else {
          opts.onUnmatched?.(text)
        }
        _scheduleRestart()
      },
      onError: (err) => {
        // EMPTY / FALLBACK 静默重启；其它停下
        if (err.type === 'EMPTY' || err.type === 'FALLBACK') {
          _scheduleRestart()
          return
        }
        active.value = false
        opts.onError?.(err)
      },
    })
  }

  async function start() {
    if (!stt.isSupported()) {
      opts.onError?.({ type: 'UNSUPPORTED', message: 'STT 不支持当前环境（需要 https 或 localhost）' })
      return
    }
    if (active.value) return
    active.value = true
    lastHeard.value = ''
    lastCommand.value = ''
    _listenOnce()
  }

  function stop() {
    active.value = false
    clearTimeout(_restartTimer)
    stt.cancel()
  }

  onBeforeUnmount(() => {
    stop()
  })

  return {
    active,
    listening,
    lastHeard,
    lastCommand,
    isSupported: stt.isSupported,
    start,
    stop,
  }
}
