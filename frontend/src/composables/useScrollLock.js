import { watch, onBeforeUnmount } from 'vue'

let _count = 0

/**
 * 弹窗/抽屉打开时锁定 body 滚动，关闭时恢复。
 * 支持多层叠加（引用计数），最后一个关闭时才解锁。
 *
 * @param {import('vue').Ref<boolean>} isOpen - 控制开关的 ref
 */
export function useScrollLock(isOpen) {
  let locked = false

  function lock() {
    if (locked) return
    locked = true
    _count++
    if (_count === 1) {
      const scrollY = window.scrollY
      document.body.style.position = 'fixed'
      document.body.style.top = `-${scrollY}px`
      document.body.style.left = '0'
      document.body.style.right = '0'
      document.body.style.overflow = 'hidden'
      document.body.dataset.scrollLockY = String(scrollY)
    }
  }

  function unlock() {
    if (!locked) return
    locked = false
    _count--
    if (_count <= 0) {
      _count = 0
      const scrollY = parseInt(document.body.dataset.scrollLockY || '0', 10)
      document.body.style.position = ''
      document.body.style.top = ''
      document.body.style.left = ''
      document.body.style.right = ''
      document.body.style.overflow = ''
      delete document.body.dataset.scrollLockY
      window.scrollTo(0, scrollY)
    }
  }

  watch(isOpen, (v) => {
    if (v) lock()
    else unlock()
  }, { immediate: true })

  onBeforeUnmount(() => {
    unlock()
  })
}
