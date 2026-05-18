/**
 * usePractice · 发音练习 API 操作集合 单测 (#32)
 *
 * 覆盖手机端 TTS / 评分 / 卡片创建链路，按 contract 验证 URL + method + body
 * 不测网络层（那是 useAuthFetch 的责任），mock 掉 useAuthFetch 上抓 fetch 行为
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// 用模块级 mock 替换 useAuthFetch，留 spy 给后续断言用
const authFetchMock = vi.fn()
const authFetchJsonMock = vi.fn()

vi.mock('../useAuthFetch', () => ({
  useAuthFetch: () => ({
    authFetch: authFetchMock,
    authFetchJson: authFetchJsonMock,
  }),
}))

vi.mock('@/config', () => ({
  API: {
    PRACTICE: '/practice',
  },
}))

import { usePractice } from '../usePractice'

beforeEach(() => {
  authFetchMock.mockReset()
  authFetchJsonMock.mockReset()
})

describe('usePractice · 发音练习 API', () => {
  it('rateCard: POST /practice/cards/{id}/review with {rating}', async () => {
    authFetchJsonMock.mockResolvedValue({ next_review: '2026-05-19T00:00:00' })
    const { rateCard } = usePractice()

    const out = await rateCard(42, 'good')

    expect(authFetchJsonMock).toHaveBeenCalledOnce()
    expect(authFetchJsonMock).toHaveBeenCalledWith(
      '/practice/cards/42/review',
      { rating: 'good' },
    )
    expect(out).toEqual({ next_review: '2026-05-19T00:00:00' })
  })

  it('createCards: POST /practice/cards 透传 payload + 返回响应 JSON', async () => {
    const respPayload = { created: 2, skipped: 0 }
    authFetchJsonMock.mockResolvedValue(respPayload)
    const { createCards } = usePractice()

    const payload = {
      items: [
        { text: 'Hello', context: '{}' },
        { text: 'World', context: '{}' },
      ],
    }
    const out = await createCards(payload)

    expect(authFetchJsonMock).toHaveBeenCalledWith('/practice/cards', payload)
    // codex round 2: 也断言返回值，防 wrapper 哪天悄悄丢掉 response body
    expect(out).toEqual(respPayload)
  })

  it('ttsBlob: POST /practice/tts 透传 text/provider/speed + 返回 blob', async () => {
    const fakeBlob = new Blob([new Uint8Array([1, 2, 3])], { type: 'audio/mpeg' })
    authFetchMock.mockResolvedValue({
      ok: true,
      blob: async () => fakeBlob,
    })
    const { ttsBlob } = usePractice()

    const out = await ttsBlob({ text: 'Hello', provider: 'azure', speed: '+20%' })

    expect(authFetchMock).toHaveBeenCalledOnce()
    const [url, opts] = authFetchMock.mock.calls[0]
    expect(url).toBe('/practice/tts')
    expect(opts.method).toBe('POST')
    expect(opts.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(JSON.parse(opts.body)).toEqual({
      text: 'Hello',
      provider: 'azure',
      speed: '+20%',
    })
    expect(out).toBe(fakeBlob)
  })

  it('ttsBlob: 缺省 provider=edge, speed=+0%', async () => {
    authFetchMock.mockResolvedValue({
      ok: true,
      blob: async () => new Blob(['x']),
    })
    const { ttsBlob } = usePractice()

    await ttsBlob({ text: 'Hi' })

    const body = JSON.parse(authFetchMock.mock.calls[0][1].body)
    expect(body.provider).toBe('edge')
    expect(body.speed).toBe('+0%')
  })

  it('ttsBlob: HTTP 非 200 → throw 解析后端 detail', async () => {
    authFetchMock.mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'TTS engine down' }),
    })
    const { ttsBlob } = usePractice()

    await expect(ttsBlob({ text: 'Hi' })).rejects.toThrow('TTS engine down')
  })

  it('ttsBlob: HTTP 非 200 且 body 不是 JSON → 兜底 "TTS 失败"', async () => {
    authFetchMock.mockResolvedValue({
      ok: false,
      json: async () => { throw new Error('not json') },
    })
    const { ttsBlob } = usePractice()

    await expect(ttsBlob({ text: 'Hi' })).rejects.toThrow('TTS 失败')
  })

  it('listDue: GET /practice/due?limit=20 默认 + 自定义 limit + 返回 JSON', async () => {
    const payload = { cards: [{ id: 1 }, { id: 2 }] }
    authFetchMock.mockResolvedValue({
      ok: true,
      json: async () => payload,
    })
    const { listDue } = usePractice()

    const out = await listDue()
    expect(authFetchMock).toHaveBeenLastCalledWith('/practice/due?limit=20')
    expect(out).toEqual(payload)

    await listDue(5)
    expect(authFetchMock).toHaveBeenLastCalledWith('/practice/due?limit=5')
  })

  it('listSources: GET /practice/subtitles?limit=10 → 返回 JSON / throw on !ok', async () => {
    const payload = { items: [{ id: 'src1' }] }
    authFetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => payload,
    })
    const { listSources } = usePractice()
    const out = await listSources()
    expect(authFetchMock).toHaveBeenCalledWith('/practice/subtitles?limit=10')
    expect(out).toEqual(payload)

    authFetchMock.mockResolvedValueOnce({ ok: false })
    await expect(listSources()).rejects.toThrow('加载历史失败')
  })

  it('getEawEpisode: slug 经过 URI 编码 + 返回 JSON', async () => {
    const payload = { slug: 'episode with spaces', segments: [] }
    authFetchMock.mockResolvedValue({ ok: true, json: async () => payload })
    const { getEawEpisode } = usePractice()

    const out = await getEawEpisode('episode with spaces')

    expect(authFetchMock).toHaveBeenCalledWith(
      '/bbc-eaw/episodes/episode%20with%20spaces',
    )
    expect(out).toEqual(payload)
  })

  // ── codex review (#32) 补三个之前完全没测的方法 ───────────────

  it('importSubtitles: POST /practice/subtitles 透传 url + cookies + 返回 JSON', async () => {
    const payload = { title: 'demo', segments: [{ content: 'hi' }] }
    authFetchJsonMock.mockResolvedValue(payload)
    const { importSubtitles } = usePractice()

    const out = await importSubtitles({
      url: 'https://b23.tv/abc',
      cookies: 'SESSDATA=xxx',
    })

    expect(authFetchJsonMock).toHaveBeenCalledWith(
      '/practice/subtitles',
      { url: 'https://b23.tv/abc', cookies: 'SESSDATA=xxx' },
    )
    expect(out).toEqual(payload)
  })

  it('getSource: GET /practice/subtitles/{id} → 返回 JSON / throw on !ok', async () => {
    const payload = { id: 42, segments: [] }
    authFetchMock.mockResolvedValueOnce({ ok: true, json: async () => payload })
    const { getSource } = usePractice()
    const out = await getSource(42)
    expect(authFetchMock).toHaveBeenCalledWith('/practice/subtitles/42')
    expect(out).toEqual(payload)

    authFetchMock.mockResolvedValueOnce({ ok: false })
    await expect(getSource(42)).rejects.toThrow('加载失败')
  })

  it('listEawEpisodes: GET /bbc-eaw/episodes?limit=100 默认 + 返回 JSON / throw on !ok', async () => {
    const payload = { episodes: [{ slug: 'ep1' }, { slug: 'ep2' }] }
    authFetchMock.mockResolvedValueOnce({ ok: true, json: async () => payload })
    const { listEawEpisodes } = usePractice()
    const out = await listEawEpisodes()
    expect(authFetchMock).toHaveBeenCalledWith('/bbc-eaw/episodes?limit=100')
    expect(out).toEqual(payload)

    authFetchMock.mockResolvedValueOnce({ ok: false })
    await expect(listEawEpisodes()).rejects.toThrow('加载 BBC EAW 失败')
  })
})
