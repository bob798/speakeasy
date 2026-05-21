import { describe, it, expect } from 'vitest'
import { tokenize } from '../tokenize.js'

describe('tokenize — edge cases', () => {
  it('emoji — "Hello 👋 world" → emoji surrogate halves are non-interactive punct tokens', () => {
    // The tokenizer iterates by JS code unit (text[i]), so a 2-code-unit emoji
    // like 👋 (U+1F44B) is split into two surrogate halves, each becoming a
    // separate non-interactive punct token.
    const tokens = tokenize('Hello 👋 world')
    // Positions: Hello(word) ' '(space) \uD83D(punct) \uDC4B(punct) ' '(space) world(word)
    expect(tokens).toHaveLength(6)
    const surrogates = tokens.filter((t) => t.kind === 'punct')
    expect(surrogates).toHaveLength(2)
    surrogates.forEach((t) => {
      expect(t.interactive).toBe(false)
    })
  })

  it('consecutive punctuation — "Hello!!!" → 3 separate punct tokens', () => {
    const tokens = tokenize('Hello!!!')
    const excls = tokens.filter((t) => t.text === '!')
    expect(excls).toHaveLength(3)
    excls.forEach((t) => {
      expect(t.kind).toBe('punct')
      expect(t.interactive).toBe(false)
    })
  })

  it('number-only — "123" → 3 non-interactive punct tokens (digits)', () => {
    const tokens = tokenize('123')
    expect(tokens).toHaveLength(3)
    tokens.forEach((t) => {
      expect(t.kind).toBe('punct')
      expect(t.interactive).toBe(false)
    })
  })

  it('mixed numbers and words — "abc123def" → "abc" word + "1","2","3" puncts + "def" word', () => {
    const tokens = tokenize('abc123def')
    expect(tokens).toHaveLength(5)
    expect(tokens[0]).toMatchObject({ kind: 'word', text: 'abc', interactive: true })
    expect(tokens[1]).toMatchObject({ kind: 'punct', text: '1', interactive: false })
    expect(tokens[2]).toMatchObject({ kind: 'punct', text: '2', interactive: false })
    expect(tokens[3]).toMatchObject({ kind: 'punct', text: '3', interactive: false })
    expect(tokens[4]).toMatchObject({ kind: 'word', text: 'def', interactive: true })
  })

  it("trailing apostrophe — \"don't'\" → single word token \"don't'\" (greedy match)", () => {
    const tokens = tokenize("don't'")
    expect(tokens).toHaveLength(1)
    expect(tokens[0]).toMatchObject({ kind: 'word', text: "don't'", interactive: true })
  })

  it('all CJK — "你好世界" → 4 interactive tokens, each single char', () => {
    const tokens = tokenize('你好世界')
    expect(tokens).toHaveLength(4)
    ;['你', '好', '世', '界'].forEach((ch, i) => {
      expect(tokens[i]).toMatchObject({ kind: 'cjk', text: ch, interactive: true })
    })
  })

  it('CJK with punctuation — "你好！世界。" → 6 tokens (你 好 ！ 世 界 。)', () => {
    const tokens = tokenize('你好！世界。')
    expect(tokens).toHaveLength(6)
    expect(tokens[0]).toMatchObject({ kind: 'cjk', text: '你', interactive: true })
    expect(tokens[1]).toMatchObject({ kind: 'cjk', text: '好', interactive: true })
    expect(tokens[2]).toMatchObject({ kind: 'punct', text: '！', interactive: false })
    expect(tokens[3]).toMatchObject({ kind: 'cjk', text: '世', interactive: true })
    expect(tokens[4]).toMatchObject({ kind: 'cjk', text: '界', interactive: true })
    expect(tokens[5]).toMatchObject({ kind: 'punct', text: '。', interactive: false })
  })

  it('newlines — "hello\\nworld" → "hello" word + "\\n" space + "world" word', () => {
    const tokens = tokenize('hello\nworld')
    expect(tokens).toHaveLength(3)
    expect(tokens[0]).toMatchObject({ kind: 'word', text: 'hello', interactive: true })
    expect(tokens[1]).toMatchObject({ kind: 'space', text: '\n', interactive: false })
    expect(tokens[2]).toMatchObject({ kind: 'word', text: 'world', interactive: true })
  })

  it('tab character — "hello\\tworld" → tab is space token', () => {
    const tokens = tokenize('hello\tworld')
    expect(tokens).toHaveLength(3)
    expect(tokens[1]).toMatchObject({ kind: 'space', text: '\t', interactive: false })
  })

  it('very long word — "supercalifragilisticexpialidocious" → single word token', () => {
    const word = 'supercalifragilisticexpialidocious'
    const tokens = tokenize(word)
    expect(tokens).toHaveLength(1)
    expect(tokens[0]).toMatchObject({ kind: 'word', text: word, interactive: true })
  })
})
