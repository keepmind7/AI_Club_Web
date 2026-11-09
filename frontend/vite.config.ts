import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// 8000번을 다른 프로그램이 쓰면 DJANGO_URL=http://127.0.0.1:8001 npm run dev
const django = process.env.DJANGO_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    allowedHosts: ['.trycloudflare.com'], // 휴대폰 테스트용 Cloudflare 임시 터널 허용 (개발 서버 전용)
    proxy: { '/api': django, '/club-admin': django, '/static': django },
  },
})
