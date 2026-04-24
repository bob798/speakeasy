/**
 * usePractice · 发音练习 API 操作集合
 * 封装 /practice/* 的网络调用 · 不持有 state（state 在 practiceStore）
 */

import { useAuthFetch } from './useAuthFetch'
import { API } from '@/config'

export function usePractice() {
  const { authFetch, authFetchJson } = useAuthFetch()

  /**
   * 提取字幕 or 手动文本 or 音频转写
   * @param {{ url?: string, text?: string, cookies?: string }} payload
   */
  async function importSubtitles(payload) {
    return authFetchJson(`${API.PRACTICE}/subtitles`, payload)
  }

  /**
   * 列出历史字幕源（最近 N 条）
   */
  async function listSources(limit = 10) {
    const resp = await authFetch(`${API.PRACTICE}/subtitles?limit=${limit}`)
    if (!resp.ok) throw new Error('加载历史失败')
    return resp.json()
  }

  /**
   * 加载特定历史字幕源详情
   */
  async function getSource(sourceId) {
    const resp = await authFetch(`${API.PRACTICE}/subtitles/${sourceId}`)
    if (!resp.ok) throw new Error('加载失败')
    return resp.json()
  }

  /**
   * 批量创建发音卡片
   * @param {{ source_id, items: Array<{ text, context, segIdx }> }} payload
   */
  async function createCards(payload) {
    return authFetchJson(`${API.PRACTICE}/cards`, payload)
  }

  /**
   * FSRS 评分
   * @param {number} cardId
   * @param {'again'|'hard'|'good'|'easy'} rating
   */
  async function rateCard(cardId, rating) {
    return authFetchJson(`${API.PRACTICE}/cards/${cardId}/review`, { rating })
  }

  /**
   * TTS 特化 · /practice/tts 支持 provider/speed 参数（edge/doubao + 速度）
   * 返回 mp3 Blob
   */
  async function ttsBlob({ text, provider = 'edge', speed = '+0%' }) {
    const resp = await authFetch(`${API.PRACTICE}/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, provider, speed }),
    })
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}))
      throw new Error(data.detail || data.error || 'TTS 失败')
    }
    return resp.blob()
  }

  /**
   * 到期复习卡列表
   */
  async function listDue(limit = 20) {
    const resp = await authFetch(`${API.PRACTICE}/due?limit=${limit}`)
    if (!resp.ok) throw new Error('加载到期卡失败')
    return resp.json()
  }

  return {
    importSubtitles,
    listSources,
    getSource,
    createCards,
    rateCard,
    ttsBlob,
    listDue,
  }
}
