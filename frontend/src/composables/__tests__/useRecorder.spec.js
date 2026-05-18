/**
 * useRecorder · 录音组合式 API 单测 (#32)
 *
 * 覆盖手机端「录音 → blob → URL.createObjectURL → 回放」全链路状态机：
 *   - start() 调 getUserMedia + 开 MediaRecorder + recording=true
 *   - stop() 进 onstop 后 blob/url 就绪 + recording=false
 *   - 权限拒绝 → error 友好文案，不抛
 *   - reset() 释放旧 URL + 清 blob
 *   - 同 instance 重复 start 不重入
 *   - 不支持环境（无 mediaDevices）→ isSupported() = false
 *
 * 因 jsdom 不提供 MediaRecorder / mediaDevices，每个 test 独立桩。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useRecorder } from '../useRecorder'
import { nextTick } from 'vue'

function makeMediaRecorder() {
  // codex review (#32 🔴): 真实 MediaRecorder.stop 后 ondataavailable / onstop 异步触发；
  // 同步触发的 mock 会掩盖 reset() / 重启与晚到 onstop 之间的状态竞争 bug。
  const instance = {
    state: 'inactive',
    ondataavailable: null,
    onstop: null,
    start: vi.fn(function () {
      this.state = 'recording'
    }),
    stop: vi.fn(function () {
      this.state = 'inactive'
      const self = this
      // 异步派发模拟真实浏览器行为
      queueMicrotask(() => {
        if (self.ondataavailable) {
          self.ondataavailable({ data: new Blob(['xx'], { type: 'audio/webm' }) })
        }
        if (self.onstop) self.onstop()
      })
    }),
  }
  return instance
}

let mediaRecorderInstance = null
let trackStopSpy = null   // 暴露给测试断言 stream.getTracks()[i].stop() 是否被调用

beforeEach(() => {
  // jsdom 默认无 mediaDevices；每个 case 先放上
  mediaRecorderInstance = makeMediaRecorder()

  globalThis.MediaRecorder = vi.fn(() => mediaRecorderInstance)
  globalThis.MediaRecorder.isTypeSupported = vi.fn(() => true)

  // 单 track 单次 stop spy，便于断言「stream 关闭释放麦克风」
  trackStopSpy = vi.fn()
  const fakeStream = {
    getTracks: () => [{ stop: trackStopSpy }],
  }
  globalThis.navigator.mediaDevices = {
    getUserMedia: vi.fn().mockResolvedValue(fakeStream),
  }

  if (!globalThis.URL.createObjectURL) {
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:fake-recorder')
    globalThis.URL.revokeObjectURL = vi.fn()
  } else {
    vi.spyOn(globalThis.URL, 'createObjectURL').mockReturnValue('blob:fake-recorder')
    vi.spyOn(globalThis.URL, 'revokeObjectURL').mockImplementation(() => {})
  }
})

afterEach(() => {
  vi.restoreAllMocks()
  delete globalThis.MediaRecorder
  // navigator.mediaDevices 在某些实现下不可 delete；置 undefined 即可
  globalThis.navigator.mediaDevices = undefined
})

describe('useRecorder', () => {
  it('start(): 调 getUserMedia + 创建 MediaRecorder + recording=true', async () => {
    const r = useRecorder()
    expect(r.recording.value).toBe(false)

    await r.start()

    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({ audio: true })
    expect(globalThis.MediaRecorder).toHaveBeenCalledOnce()
    expect(mediaRecorderInstance.start).toHaveBeenCalled()
    expect(r.recording.value).toBe(true)
  })

  it('stop(): onstop 触发后写入 blob/url + recording=false', async () => {
    const r = useRecorder()
    await r.start()
    r.stop()
    await nextTick()

    expect(r.recording.value).toBe(false)
    expect(r.blob.value).toBeInstanceOf(Blob)
    expect(r.url.value).toBe('blob:fake-recorder')
    expect(URL.createObjectURL).toHaveBeenCalled()
  })

  it('权限拒绝 → error 友好提示 + recording 不切 true', async () => {
    const denyErr = new Error('denied')
    denyErr.name = 'NotAllowedError'
    navigator.mediaDevices.getUserMedia.mockRejectedValueOnce(denyErr)

    const r = useRecorder()
    await r.start()

    expect(r.error.value).toMatch(/麦克风权限/)
    expect(r.recording.value).toBe(false)
    expect(globalThis.MediaRecorder).not.toHaveBeenCalled()
  })

  it('设备级错误（非 NotAllowedError） → 兜底文案', async () => {
    navigator.mediaDevices.getUserMedia.mockRejectedValueOnce(
      Object.assign(new Error('boom'), { name: 'NotFoundError' }),
    )
    const r = useRecorder()
    await r.start()

    expect(r.error.value).toBe('录音设备错误')
    expect(r.recording.value).toBe(false)
  })

  it('reset(): 释放 URL + 清 blob + 清 error', async () => {
    const r = useRecorder()
    await r.start()
    r.stop()
    await nextTick()
    expect(r.url.value).toBe('blob:fake-recorder')

    r.reset()

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:fake-recorder')
    expect(r.url.value).toBeNull()
    expect(r.blob.value).toBeNull()
    expect(r.error.value).toBe('')
  })

  it('start() 已在录音时不重入', async () => {
    const r = useRecorder()
    await r.start()
    const firstCallCount = navigator.mediaDevices.getUserMedia.mock.calls.length
    await r.start()
    expect(navigator.mediaDevices.getUserMedia.mock.calls.length).toBe(firstCallCount)
  })

  it('isSupported(): 当前 jsdom + 我们桩的 mediaDevices → true（localhost 协议）', () => {
    // jsdom 默认 hostname=localhost，满足分支
    const r = useRecorder()
    expect(r.isSupported()).toBe(true)
  })

  it('isSupported(): 没 mediaDevices → false', () => {
    globalThis.navigator.mediaDevices = undefined
    const r = useRecorder()
    expect(r.isSupported()).toBe(false)
  })

  it('stop() 在未录音时只清 stream，不进 onstop', async () => {
    const r = useRecorder()
    // 不 start 直接 stop
    r.stop()
    expect(r.recording.value).toBe(false)
    expect(r.blob.value).toBeNull()
  })

  it('webm 不支持时回落到 ogg', async () => {
    globalThis.MediaRecorder.isTypeSupported.mockImplementation((m) => m === 'audio/ogg')
    const r = useRecorder()
    await r.start()
    // 验证 MediaRecorder 构造时收到 audio/ogg
    expect(globalThis.MediaRecorder).toHaveBeenCalledWith(
      expect.anything(),
      { mimeType: 'audio/ogg' },
    )
  })

  // ── codex review (#32) 补强 ───────────────────────────────────

  it('isSupported(): 有 mediaDevices 但 MediaRecorder 缺失 → false (老 iOS Safari)', () => {
    delete globalThis.MediaRecorder
    const r = useRecorder()
    expect(r.isSupported()).toBe(false)
  })

  it('stop(): 释放 stream 关闭 mic（track.stop() 被调用）', async () => {
    const r = useRecorder()
    await r.start()
    expect(trackStopSpy).not.toHaveBeenCalled()
    r.stop()
    await nextTick()
    await Promise.resolve()  // 让 microtask 跑完
    expect(trackStopSpy).toHaveBeenCalled()
  })

  it('reset() 在 stop pending 时不被晚到的 onstop 污染 (race: codex review 🔴)', async () => {
    // 真 bug 场景：
    //   r.stop() → MediaRecorder 异步触发 onstop
    //   onstop fire 之前用户调 reset()
    //   原实现：onstop 还会写 blob.value/url.value → reset 清空白做工
    //   修后：reset 推进 _startSeq，stale onstop 检测到不匹配后只清 stream
    const r = useRecorder()
    await r.start()
    expect(r.recording.value).toBe(true)

    r.stop()       // 派发 onstop 到 microtask queue
    r.reset()      // 立刻 reset，应使 pending onstop 失效

    // 让所有 microtask 执行完
    await Promise.resolve()
    await Promise.resolve()
    await nextTick()

    expect(r.blob.value).toBeNull()
    expect(r.url.value).toBeNull()
    // codex round 2 regression：reset 后 recording 不能卡 true，否则下次 start() 早 return
    expect(r.recording.value).toBe(false)
  })

  it('reset() 后能立刻 start() 新 session (codex round 2 regression)', async () => {
    // 场景：用户录到一半反悔点重录 → reset() + start()
    // 修前：reset 仅推 _startSeq，stale onstop 走早 return 跳过 recording=false → start() 早 return
    const r = useRecorder()
    await r.start()
    expect(r.recording.value).toBe(true)

    r.reset()                                  // 不等 onstop 异步
    expect(r.recording.value).toBe(false)      // 必须同步可见

    const startCallsBefore = navigator.mediaDevices.getUserMedia.mock.calls.length
    await r.start()                            // 这次必须能真正进
    expect(r.recording.value).toBe(true)
    expect(navigator.mediaDevices.getUserMedia.mock.calls.length).toBe(startCallsBefore + 1)
  })

  it('start() 在 getUserMedia await 期间被 reset() 作废 → 新 stream 立刻 stop', async () => {
    // 用 deferred 暴露 getUserMedia 的 await，模拟竞争
    let resolveStream
    const trackStop = vi.fn()
    navigator.mediaDevices.getUserMedia.mockReturnValue(
      new Promise((resolve) => { resolveStream = (s) => resolve(s) }),
    )

    const r = useRecorder()
    const startPromise = r.start()
    r.reset()                              // 在 await 期间作废
    resolveStream({ getTracks: () => [{ stop: trackStop }] })  // 现在让 stream 落地
    await startPromise

    expect(r.recording.value).toBe(false)
    expect(trackStop).toHaveBeenCalled()   // 拿到 stream 但因 stale 立即关闭
    expect(globalThis.MediaRecorder).not.toHaveBeenCalled()  // 不应创建 recorder
  })
})
