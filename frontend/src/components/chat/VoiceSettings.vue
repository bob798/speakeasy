<script setup>
/**
 * VoiceSettings · V0.9 语音设置抽屉
 * 控制：自动朗读 · Hands-free · TTS provider · 语速
 */
import { useChatStore } from '@/stores/chat'

const open = defineModel('open', { type: Boolean, default: false })
const chat = useChatStore()

function close() {
  open.value = false
}
</script>

<template>
  <Transition name="drawer">
    <div v-if="open" class="overlay" @click.self="close">
      <aside class="sheet">
        <header>
          <h3>语音设置</h3>
          <button class="close" @click="close" aria-label="关闭">×</button>
        </header>

        <section class="group">
          <label class="row">
            <div class="text">
              <div class="title">自动朗读</div>
              <div class="desc">Alex 的回复自动朗读</div>
            </div>
            <input
              type="checkbox"
              class="switch"
              :checked="chat.autoPlay"
              @change="chat.toggleAutoPlay()"
            />
          </label>

          <label class="row">
            <div class="text">
              <div class="title">Hands-free 循环</div>
              <div class="desc">
                Alex 说完自动打开麦 · 说完自动发送 · 免手全程对话
              </div>
            </div>
            <input
              type="checkbox"
              class="switch"
              :checked="chat.handsFree"
              @change="chat.toggleHandsFree()"
            />
          </label>
        </section>

        <section class="group">
          <h4>朗读引擎</h4>
          <div class="seg">
            <button
              v-for="p in ['edge', 'doubao']"
              :key="p"
              class="seg-btn"
              :class="{ active: chat.ttsProvider === p }"
              @click="chat.ttsProvider = p"
            >
              {{ p === 'edge' ? 'Edge' : '豆包' }}
            </button>
          </div>
        </section>

        <section class="group">
          <h4>语速</h4>
          <div class="seg">
            <button
              v-for="s in ['-40%', '-20%', '+0%', '+20%']"
              :key="s"
              class="seg-btn"
              :class="{ active: chat.ttsSpeed === s }"
              @click="chat.ttsSpeed = s"
            >
              {{ s === '+0%' ? '标准' : s }}
            </button>
          </div>
        </section>

        <p class="footer-hint">
          设置对 Chat 页 TTS 生效 · Practice 页有独立设置
        </p>
      </aside>
    </div>
  </Transition>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: var(--z-drawer);
  display: flex;
  justify-content: flex-end;
  align-items: flex-end;
}
.sheet {
  width: 100%;
  max-width: 420px;
  max-height: 88vh;
  background: var(--bg-elevated);
  border-top-left-radius: var(--radius-lg);
  border-top-right-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  padding-bottom: var(--safe-bottom);
  overflow-y: auto;
}
@media (min-width: 768px) {
  .overlay {
    align-items: center;
    justify-content: center;
  }
  .sheet {
    border-radius: var(--radius-lg);
    max-height: 80vh;
  }
}
header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: var(--bg-elevated);
}
h3 {
  margin: 0;
  font-size: 16px;
  color: var(--accent);
}
.close {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 22px;
  color: var(--text-3);
}
.group {
  padding: var(--space-4);
  border-bottom: 1px solid var(--border);
}
.group h4 {
  margin: 0 0 var(--space-3);
  font-size: 12px;
  color: var(--text-3);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) 0;
  gap: var(--space-4);
}
.text {
  flex: 1;
  min-width: 0;
}
.text .title {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-1);
}
.text .desc {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.4;
}
.switch {
  appearance: none;
  -webkit-appearance: none;
  width: 44px;
  height: 26px;
  border-radius: 999px;
  background: var(--border);
  position: relative;
  flex-shrink: 0;
  transition: background var(--duration) var(--ease);
  cursor: pointer;
}
.switch::before {
  content: '';
  position: absolute;
  left: 3px;
  top: 3px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: white;
  transition: transform var(--duration) var(--ease);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}
.switch:checked {
  background: var(--accent);
}
.switch:checked::before {
  transform: translateX(18px);
}
.seg {
  display: flex;
  gap: var(--space-1);
  background: var(--bg);
  padding: 3px;
  border-radius: var(--radius-sm);
}
.seg-btn {
  flex: 1;
  padding: var(--space-2);
  font-size: 13px;
  color: var(--text-2);
  border-radius: calc(var(--radius-sm) - 3px);
}
.seg-btn.active {
  background: var(--bg-elevated);
  color: var(--accent);
  font-weight: 500;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.footer-hint {
  padding: var(--space-3) var(--space-4);
  font-size: 12px;
  color: var(--text-3);
  text-align: center;
}

.drawer-enter-active,
.drawer-leave-active {
  transition: opacity var(--duration) var(--ease);
}
.drawer-enter-active > .sheet,
.drawer-leave-active > .sheet {
  transition: transform var(--duration) var(--ease);
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from > .sheet,
.drawer-leave-to > .sheet {
  transform: translateY(100%);
}
</style>
