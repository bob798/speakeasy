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
  const events = {}
  const instance = {
    state: 'inactive',
    ondataavailable: null,
    onstop: null,
    start: vi.fn(function () {
      this.state = 'recording'
    }),
    stop: vi.fn(function () {
      this.state = 'inactive'
      // 模拟一次 chunk + onstop 触发
      if (this.ondataavailable) this.ondataavailable({ data: new Blob(['xx'], { type: 'audio/webm' }) })
      if (this.onstop) this.onstop()
    }),
  }
  // 用 events 暴露给测试 inspect
  Object.defineProperty(instance, '__events', { value: events })
  return instance
}

let mediaRecorderInstance = null

beforeEach(() => {
  // jsdom 默认无 mediaDevices；每个 case 先放上
  mediaRecorderInstance = makeMediaRecorder()

  globalThis.MediaRecorder = vi.fn(() => mediaRecorderInstance)
  globalThis.MediaRecorder.isTypeSupported = vi.fn(() => true)

  const fakeStream = {
    getTracks: () => [{ stop: vi.fn() }],
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
})
