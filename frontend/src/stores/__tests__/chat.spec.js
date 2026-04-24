/**
 * chatStore 单测 · 消息 CRUD + session lifecycle
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useChatStore } from '../chat'

describe('chatStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('初始化 · 新 session + 空消息列表', () => {
    const s = useChatStore()
    expect(s.sessionId).toMatch(/^s-/)
    expect(s.messages).toEqual([])
    expect(s.roundCount).toBe(0)
    expect(s.userMessageCount).toBe(0)
  })

  it('addMessage 返回 id · 后续 patchMessage 可更新', () => {
    const s = useChatStore()
    const id = s.addMessage({ role: 'assistant', content: '', streaming: true })
    expect(id).toMatch(/^m-/)
    s.patchMessage(id, { content: 'hi', streaming: false })
    expect(s.messages[0].content).toBe('hi')
    expect(s.messages[0].streaming).toBe(false)
  })

  it('removeMessage 清除指定 id', () => {
    const s = useChatStore()
    const id1 = s.addMessage({ role: 'user', content: 'a' })
    s.addMessage({ role: 'assistant', content: 'b' })
    s.removeMessage(id1)
    expect(s.messages).toHaveLength(1)
    expect(s.messages[0].content).toBe('b')
  })

  it('newSession 重置 id + messages', () => {
    const s = useChatStore()
    const oldId = s.sessionId
    s.addMessage({ role: 'user', content: 'hi' })
    s.newSession()
    expect(s.sessionId).not.toBe(oldId)
    expect(s.messages).toEqual([])
  })

  it('loadSession 设置 sid + 填充消息', () => {
    const s = useChatStore()
    s.loadSession('s-abc', [
      { role: 'user', content: 'q' },
      { role: 'assistant', content: 'a' },
    ])
    expect(s.sessionId).toBe('s-abc')
    expect(s.messages).toHaveLength(2)
    expect(s.roundCount).toBe(1)
    expect(s.userMessageCount).toBe(1)
  })

  it('toggleAutoPlay 切换布尔', () => {
    const s = useChatStore()
    expect(s.autoPlay).toBe(false)
    s.toggleAutoPlay()
    expect(s.autoPlay).toBe(true)
    s.toggleAutoPlay()
    expect(s.autoPlay).toBe(false)
  })
})
