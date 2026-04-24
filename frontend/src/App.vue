<script setup>
// 根组件 · Phase 0 骨架
// Phase 2 起补 keep-alive 策略（Chat / Practice 保活；Memory / Translate / Review / Login 不保活）
</script>

<template>
  <router-view v-slot="{ Component }">
    <component :is="Component" />
  </router-view>
</template>

<style>
/* 全局样式由 tokens.css / reset.css 提供 */
</style>
