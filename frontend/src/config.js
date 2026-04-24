/**
 * 前端常量配置 · 替代 static/js/config.js
 * Pass 3 B4 single source of truth
 */

export const API = {
  BASE: '',
  CHAT_STREAM: '/chat/stream',
  CHAT_SUMMARY: '/chat/summary',
  STT: '/stt',
  TTS: '/tts',
  HISTORY: '/history',
  SESSIONS: '/sessions',
  REVIEW: '/review',
  MEMORY: '/memory',
  PRACTICE: '/practice',
  TRANSLATE: '/translate',
  AUTH: '/auth',
  ASK: '/ask',
  SETTINGS: '/settings',
  HEALTH: '/health',
  DEBUG: '/debug/status',
}

export const CHAT = {
  HISTORY_PAGE_SIZE: 20,
  CONTEXT_TAIL_SIZE: 10, // 最近 N 轮带给后端做上下文
}
