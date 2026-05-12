import { ref, onMounted, onUnmounted } from 'vue'

/**
 * 响应式 isMobile · 基于 matchMedia('(max-width: 767px)')
 * 与 spec 的 < 768px 断点对齐
 *
 * @returns {Object} { isMobile }
 * @property {import('vue').Ref<boolean>} isMobile - 是否为移动设备尺寸
 */
export function useBreakpoint() {
  const isMobile = ref(false)
  let mq = null

  const onChange = (e) => {
    isMobile.value = e.matches
  }

  onMounted(() => {
    mq = window.matchMedia('(max-width: 767px)')
    isMobile.value = mq.matches
    mq.addEventListener('change', onChange)
  })

  onUnmounted(() => {
    if (mq) {
      mq.removeEventListener('change', onChange)
    }
  })

  return { isMobile }
}
