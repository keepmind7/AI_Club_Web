import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const django = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    allowedHosts: ['.trycloudflare.com'], // 휴대폰 테스트용 Cloudflare 임시 터널 허용 (개발 서버 전용)
    proxy: { '/api': django, '/club-admin': django, '/static': django },
  },
})
