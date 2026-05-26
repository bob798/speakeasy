/**
 * 译文区分词 · 纯函数
 *
 * 按 Unicode script 切分：
 * - word  英文词（含连字符 well-known / 缩略 don't）
 * - cjk   单个 CJK 字符（连续中文必须逐字 token，便于逐字交互）
 * - space 单个空白字符（含换行）
 * - punct 标点、数字、其它单字符
 *
 * 只有 word / cjk 可交互（挂事件、hover、click）；
 * space / punct 显式 interactive=false，便于事件委托快速过滤。
 *
 * @param {string} text
 * @returns {Array<{kind: 'word'|'cjk'|'space'|'punct', text: string, interactive: boolean, index: number}>}
 */
export function tokenize(text) {
  const tokens = []
  if (!text) return tokens

  const WORD_RE = /^[A-Za-z][A-Za-z'-]*/
  const CJK_RE = /[一-鿿㐀-䶿]/
  const SPACE_RE = /\s/

  let i = 0
  while (i < text.length) {
    const ch = text[i]

    if (SPACE_RE.test(ch)) {
      tokens.push({ kind: 'space', text: ch, interactive: false, index: tokens.length })
      i += 1
      continue
    }

    if (CJK_RE.test(ch)) {
      tokens.push({ kind: 'cjk', text: ch, interactive: true, index: tokens.length })
      i += 1
      continue
    }

    const m = text.slice(i).match(WORD_RE)
    if (m) {
      tokens.push({ kind: 'word', text: m[0], interactive: true, index: tokens.length })
      i += m[0].length
      continue
    }

    tokens.push({ kind: 'punct', text: ch, interactive: false, index: tokens.length })
    i += 1
  }

  return tokens
}
