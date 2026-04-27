import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import { fileURLToPath, URL } from 'node:url'

// FastAPI 后端开发服务器
// 用 127.0.0.1 而不是 localhost：避免 Node 20+ 把 localhost 优先解析为 IPv6 (::1)
// 而 uvicorn 默认只绑 IPv4，导致 ECONNREFUSED ::1:8000
const BACKEND = 'http://127.0.0.1:8000'

// dev 时需要代理到 FastAPI 的路径前缀（13 类 API）
const API_PREFIXES = [
  '/chat',
  '/stt',
  '/tts',
  '/history',
  '/sessions',
  '/review',
  '/memory',
  '/practice',
  '/translate',
  '/auth',
  '/ask',
  '/settings',
  '/health',
  '/debug',
  '/static/audio_cache',
  '/static/tts_cache',
  '/legacy',
]

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'apple-touch-icon.png'],
      manifest: {
        name: 'Speakeasy',
        short_name: 'Speakeasy',
        description: 'AI 陪伴式英语私教 - 越聊越懂你',
        theme_color: '#3d6b4f',
        background_color: '#ffffff',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        icons: [
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable',
          },
        ],
      },
      workbox: {
        // API 请求不走 Service Worker 缓存
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [
          /^\/legacy\//,
          /^\/chat/,
          /^\/stt/,
          /^\/tts/,
          /^\/history/,
          /^\/sessions/,
          /^\/review\//,
          /^\/memory\//,
          /^\/practice\//,
          /^\/translate\//,
          /^\/auth\//,
          /^\/ask\//,
          /^\/settings\//,
          /^\/health/,
          /^\/debug\//,
          /^\/static\/(audio|tts)_cache\//,
        ],
        runtimeCaching: [],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      API_PREFIXES.map((prefix) => [prefix, { target: BACKEND, changeOrigin: true }])
    ),
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        // 资源分拆以配合 300KB gzip 预算
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: [],
  },
})
