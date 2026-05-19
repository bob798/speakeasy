/**
 * ExplanationModal · IPA 🎧 按钮测试 (#34)
 *
 * 覆盖：
 *  - phonetic 非空 → 单词区渲染 🎧
 *  - phonetic 空 → 不渲染 🎧
 *  - liaison 数组每项一个 🎧
 *  - 点 🎧 → 发出预期 POST body（含 phoneme_map）
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick, ref } from 'vue'

// ── 模块级 mock ───────────────────────────────────────────
const authFetchMock = vi.fn()
const authFetchJsonMock = vi.fn()
const sseStreamMock = vi.fn()
const ttsEnqueueMock = vi.fn()

vi.mock('@/composables/useAuthFetch', () => ({
  useAuthFetch: () => ({
    authFetch: authFetchMock,
    authFetchJson: authFetchJsonMock,
  }),
  getErrorMessage: (e) => String(e),
}))

vi.mock('@/composables/useSSE', () => ({
  useSSE: () => ({
    stream: sseStreamMock,
    streaming: ref(false),
    abort: vi.fn(),
  }),
}))

vi.mock('@/composables/useTTS', () => ({
  useTTS: () => ({
    enqueue: ttsEnqueueMock,
    clear: vi.fn(),
    stop: vi.fn(),
    playing: ref(false),
  }),
}))

vi.mock('@/composables/useScrollLock', () => ({
  useScrollLock: vi.fn(),
}))

vi.mock('@/config', () => ({
  API: { PRACTICE: '/practice', ARTICLES: '/articles', VOCAB: '/vocab' },
}))

// AskPanel 是 child component；测试不关心其内部，stub 掉
vi.mock('../AskPanel.vue', () => ({
  default: { name: 'AskPanel', render: () => null },
}))

// jsdom 不提供 Audio；测里只校验调用，不用真播
class FakeAudio {
  constructor(src) {
    this.src = src
    this.onended = null
    this.onerror = null
  }
  play() { return Promise.resolve() }
  pause() {}
}
globalThis.Audio = FakeAudio
if (!globalThis.URL.createObjectURL) {
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:fake')
  globalThis.URL.revokeObjectURL = vi.fn()
}

import ExplanationModal from '../ExplanationModal.vue'

// ── helpers ───────────────────────────────────────────────
async function mountModal({ target, dataPatch = {} }) {
  if (target.type === 'word') {
    // word 路径：authFetchJson 被调两次 (phonetic + explain)
    authFetchJsonMock.mockImplementation((url) => {
      if (typeof url === 'string' && url.includes('/phonetic')) {
        return Promise.resolve({ phonetic: dataPatch.phonetic || '' })
      }
      return Promise.resolve({ explanation: { phonetic: dataPatch.phonetic || '' } })
    })
  } else {
    // sentence 路径：sseStream 触发缓存命中事件
    sseStreamMock.mockImplementation(async (url, body, opts) => {
      opts?.onEvent?.({
        _cached: true,
        explanation: {
          meaning: dataPatch.meaning || '',
          grammar: dataPatch.grammar || '',
          phrases: dataPatch.phrases || [],
          liaison: dataPatch.liaison || [],
          current_level_points: [],
          next_level_points: [],
          narration: '',
        },
      })
    })
  }

  // 先 open=false 挂载，再切到 true 让 watcher 触发 fetchExplanation
  const wrapper = mount(ExplanationModal, {
    props: { open: false, target },
  })
  await wrapper.setProps({ open: true })
  await flushPromises()
  await nextTick()
  return wrapper
}

// ── tests ─────────────────────────────────────────────────
describe('ExplanationModal · IPA 🎧 按钮', () => {
  beforeEach(() => {
    authFetchMock.mockReset()
    authFetchJsonMock.mockReset()
    ttsEnqueueMock.mockReset()
  })

  it('word: phonetic 非空时单词区渲染 🎧 按钮', async () => {
    const wrapper = await mountModal({
      target: { type: 'word', content: 'schedule' },
      dataPatch: { phonetic: 'ˈskɛdʒuːl' },
    })
    const btn = wrapper.find('.ipa .ipa-tts-btn')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('aria-label')).toContain('schedule')
  })

  it('word: phonetic 为空时不渲染 🎧 按钮', async () => {
    const wrapper = await mountModal({
      target: { type: 'word', content: 'noipa' },
      dataPatch: { phonetic: '' },
    })
    expect(wrapper.find('.ipa .ipa-tts-btn').exists()).toBe(false)
  })

  it('sentence: liaison 数组每个 chunk 各渲染一个 🎧 按钮', async () => {
    const wrapper = await mountModal({
      target: { type: 'sentence', content: 'give me a hand would you' },
      dataPatch: {
        meaning: 'help me',
        liaison: [
          { chunk: 'give me', ipa: 'ɡɪmi', tip: 'T-flap' },
          { chunk: 'would you', ipa: 'wʊdʒu', tip: '/dʒ/' },
        ],
      },
    })
    const btns = wrapper.findAll('.liaison .ipa-tts-btn')
    expect(btns.length).toBe(2)
    expect(btns[0].attributes('aria-label')).toContain('give me')
    expect(btns[1].attributes('aria-label')).toContain('would you')
  })

  it('word: 点 🎧 发 POST /practice/tts，body 含正确 phoneme_map', async () => {
    authFetchMock.mockResolvedValue({
      ok: true,
      blob: async () => new Blob([new Uint8Array([1, 2, 3])], { type: 'audio/mpeg' }),
    })
    const wrapper = await mountModal({
      target: { type: 'word', content: 'schedule' },
      dataPatch: { phonetic: 'ˈskɛdʒuːl' },
    })
    await wrapper.find('.ipa .ipa-tts-btn').trigger('click')
    await flushPromises()

    expect(authFetchMock).toHaveBeenCalledOnce()
    const [url, opts] = authFetchMock.mock.calls[0]
    expect(url).toBe('/practice/tts')
    expect(opts.method).toBe('POST')
    const body = JSON.parse(opts.body)
    expect(body.text).toBe('schedule')
    expect(body.provider).toBe('azure')
    expect(body.phoneme_map).toEqual({ schedule: 'ˈskɛdʒuːl' })
  })

  it('sentence: 点连读 chunk 的 🎧 发出对应 chunk 的 phoneme_map', async () => {
    authFetchMock.mockResolvedValue({
      ok: true,
      blob: async () => new Blob([new Uint8Array([1])], { type: 'audio/mpeg' }),
    })
    const wrapper = await mountModal({
      target: { type: 'sentence', content: 'give me a hand' },
      dataPatch: {
        meaning: 'help me',
        liaison: [{ chunk: 'give me', ipa: 'ɡɪmi', tip: 'T-flap' }],
      },
    })
    await wrapper.find('.liaison .ipa-tts-btn').trigger('click')
    await flushPromises()

    expect(authFetchMock).toHaveBeenCalledOnce()
    const body = JSON.parse(authFetchMock.mock.calls[0][1].body)
    expect(body.text).toBe('give me')
    expect(body.phoneme_map).toEqual({ 'give me': 'ɡɪmi' })
  })

  it('word: explain calls use /articles/* and carry source/item_type fields', async () => {
    const wrapper = await mountModal({
      target: {
        type: 'word',
        content: 'schedule',
        context: { vocab_source_type: 'article', vocab_source_ref: 'ep42' },
      },
      dataPatch: { phonetic: 'ˈskɛdʒuːl' },
    })
    await flushPromises()

    // authFetchJson called twice: phonetic + explain
    expect(authFetchJsonMock).toHaveBeenCalledTimes(2)
    const [phoneticUrl, phoneticBody] = authFetchJsonMock.mock.calls[0]
    const [explainUrl, explainBody] = authFetchJsonMock.mock.calls[1]

    expect(phoneticUrl).toBe('/articles/explain/phonetic')
    expect(phoneticBody.source_type).toBe('article')
    expect(phoneticBody.source_ref).toBe('ep42')
    expect(phoneticBody.item_type).toBe('word')

    expect(explainUrl).toBe('/articles/explain')
    expect(explainBody.source_type).toBe('article')
    expect(explainBody.source_ref).toBe('ep42')
    expect(explainBody.item_type).toBe('word')

    // phonetic and explain share the same item_type
    expect(phoneticBody.item_type).toBe(explainBody.item_type)
  })

  it('sentence: stream call uses /articles/explain/stream and carries source/item_type fields', async () => {
    // Mount manually to control sseStreamMock capture (mountModal helper overwrites it)
    let capturedUrl = ''
    let capturedBody = {}
    sseStreamMock.mockImplementation(async (url, body, opts) => {
      capturedUrl = url
      capturedBody = body
      opts?.onEvent?.({
        _cached: true,
        explanation: { meaning: 'help', grammar: '', phrases: [], liaison: [], current_level_points: [], next_level_points: [], narration: '' },
      })
    })

    const target = {
      type: 'sentence',
      content: 'give me a hand',
      context: { vocab_source_type: 'article', vocab_source_ref: 'ep42' },
    }
    const wrapper = mount(ExplanationModal, {
      props: { open: false, target },
    })
    await wrapper.setProps({ open: true })
    await flushPromises()
    await nextTick()

    expect(capturedUrl).toBe('/articles/explain/stream')
    expect(capturedBody.source_type).toBe('article')
    expect(capturedBody.source_ref).toBe('ep42')
    expect(capturedBody.item_type).toBe('sentence')
  })

  it('word phrase: item_type is "phrase" for multi-token word', async () => {
    const wrapper = await mountModal({
      target: { type: 'word', content: 'give up' },
      dataPatch: { phonetic: '' },
    })
    await flushPromises()

    expect(authFetchJsonMock).toHaveBeenCalledTimes(2)
    const [, phoneticBody] = authFetchJsonMock.mock.calls[0]
    const [, explainBody] = authFetchJsonMock.mock.calls[1]
    expect(phoneticBody.item_type).toBe('phrase')
    expect(explainBody.item_type).toBe('phrase')
  })
})
