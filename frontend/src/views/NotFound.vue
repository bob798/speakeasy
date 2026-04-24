<script setup>
import { RouterLink } from 'vue-router'
</script>

<template>
  <main class="nf">
    <h1>404</h1>
    <p>这个路径不存在</p>
    <RouterLink to="/">返回首页</RouterLink>
  </main>
</template>

<style scoped>
.nf {
  padding: var(--space-6);
  max-width: 480px;
  margin: 0 auto;
  text-align: center;
}
h1 {
  font-size: 64px;
  margin: 0;
  color: var(--accent);
}
</style>
