import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from './api'
import type { User } from './types'

export const useAuth = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const loaded = ref(false)

  // 앱 시작 시 한 번. 이 호출이 csrftoken 쿠키도 받아 온다.
  // 실패는 "로그인 안 됨"으로 본다. 휴면·탈퇴 403은 api()가 로그아웃하고 안내 문구와 함께 /login으로 보낸다.
  async function load() {
    user.value = await api<User>('/api/auth/me').catch(() => null)
    loaded.value = true
  }

  async function logout() {
    await api('/api/auth/logout', 'POST')
    user.value = null
  }

  return { user, loaded, load, logout }
})
