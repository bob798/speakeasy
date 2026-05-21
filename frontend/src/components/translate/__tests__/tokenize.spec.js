import { describe, it, expect } from 'vitest'
import { tokenize } from '../tokenize'

describe('tokenize', () => {
  it('empty string returns empty array', () => {
    expect(tokenize('')).toEqual([])
  })

  it('pure English sentence produces correct word/space/punct tokens', () => {
    const tokens = tokenize('Hello world')
    expect(tokens).toHaveLength(3)
    expect(tokens[0]).toMatchObject({ kind: 'word', text: 'Hello', interactive: true })
    expect(tokens[1]).toMatchObject({ kind: 'space', text: ' ', interactive: false })
    expect(tokens[2]).toMatchObject({ kind: 'word', text: 'world', interactive: true })
  })

  it('CJK per-character: "你好世界" produces 4 separate CJK tokens', () => {
    const tokens = tokenize('你好世界')
    expect(tokens).toHaveLength(4)
    const chars = ['你', '好', '世', '界']
    chars.forEach((ch, i) => {
      expect(tokens[i]).toMatchObject({ kind: 'cjk', text: ch, interactive: true, index: i })
    })
  })

  it('English contraction "don\'t" is a single word token', () => {
    const tokens = tokenize("don't")
    expect(tokens).toHaveLength(1)
    expect(tokens[0]).toMatchObject({ kind: 'word', text: "don't", interactive: true })
  })

  it('hyphenated word "well-known" is a single word token', () => {
    const tokens = tokenize('well-known')
    expect(tokens).toHaveLength(1)
    expect(tokens[0]).toMatchObject({ kind: 'word', text: 'well-known', interactive: true })
  })

  it('punctuation tokens are not interactive: "Hello, world!"', () => {
    const tokens = tokenize('Hello, world!')
    const comma = tokens.find((t) => t.text === ',')
    const excl = tokens.find((t) => t.text === '!')
    expect(comma).toBeDefined()
    expect(comma.interactive).toBe(false)
    expect(excl).toBeDefined()
    expect(excl.interactive).toBe(false)
  })

  it('mixed CJK + English "Hello 世界 test" produces correct token types', () => {
    const tokens = tokenize('Hello 世界 test')
    // Hello(word) ' '(space) 世(cjk) 界(cjk) ' '(space) test(word)
    expect(tokens).toHaveLength(6)
    expect(tokens[0]).toMatchObject({ kind: 'word', text: 'Hello' })
    expect(tokens[1]).toMatchObject({ kind: 'space', text: ' ' })
    expect(tokens[2]).toMatchObject({ kind: 'cjk', text: '世' })
    expect(tokens[3]).toMatchObject({ kind: 'cjk', text: '界' })
    expect(tokens[4]).toMatchObject({ kind: 'space', text: ' ' })
    expect(tokens[5]).toMatchObject({ kind: 'word', text: 'test' })
  })

  it('numbers are not interactive: "abc 123 def" → 1, 2, 3 are punct tokens', () => {
    const tokens = tokenize('abc 123 def')
    // abc(word) ' '(space) 1(punct) 2(punct) 3(punct) ' '(space) def(word)
    const digitTokens = tokens.filter((t) => /\d/.test(t.text))
    expect(digitTokens.length).toBe(3)
    digitTokens.forEach((t) => {
      expect(t.kind).toBe('punct')
      expect(t.interactive).toBe(false)
    })
  })

  it('all interactive tokens have interactive: true', () => {
    const tokens = tokenize('Hello 世界 don\'t well-known, 123!')
    const interactive = tokens.filter((t) => t.interactive)
    interactive.forEach((t) => {
      expect(t.interactive).toBe(true)
      expect(['word', 'cjk']).toContain(t.kind)
    })
  })

  it('whitespace preserved: spaces and newlines become space tokens', () => {
    const tokens = tokenize('a b\nc')
    const spaceTokens = tokens.filter((t) => t.kind === 'space')
    expect(spaceTokens).toHaveLength(2)
    expect(spaceTokens[0].text).toBe(' ')
    expect(spaceTokens[1].text).toBe('\n')
    spaceTokens.forEach((t) => {
      expect(t.interactive).toBe(false)
    })
  })

  it('index values are sequential starting from 0', () => {
    const tokens = tokenize('Hi 你')
    tokens.forEach((t, i) => {
      expect(t.index).toBe(i)
    })
  })
})
