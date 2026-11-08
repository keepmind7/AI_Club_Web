<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { useAuth } from '../auth'
import type { User } from '../types'

const auth = useAuth()
const router = useRouter()
const reason = useRoute().query.reason
const username = ref('')
const password = ref('')
const error = ref(typeof reason === 'string' ? reason : '')
const busy = ref(false)

async function submit() {
  busy.value = true
  error.value = ''
  try {
    auth.user = await api<User>('/api/auth/login', 'POST', { username: username.value, password: password.value })
    router.push(auth.user.must_change_password ? '/password' : '/')
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <h1 class="mt-8 mb-6 text-2xl font-bold">Club Manager 로그인</h1>
  <form class="space-y-4" @submit.prevent="submit">
    <div>
      <label for="username" class="mb-1 block text-sm font-medium">아이디</label>
      <input id="username" v-model="username" required autocomplete="username" autocapitalize="none"
        class="min-h-11 w-full rounded border border-gray-300 bg-white px-3" />
    </div>
    <div>
      <label for="password" class="mb-1 block text-sm font-medium">비밀번호</label>
      <input id="password" v-model="password" type="password" required autocomplete="current-password"
        class="min-h-11 w-full rounded border border-gray-300 bg-white px-3" />
    </div>
    <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
    <button type="submit" :disabled="busy" class="min-h-11 w-full rounded bg-blue-700 font-medium text-white disabled:opacity-50">
      {{ busy ? '로그인 중…' : '로그인' }}
    </button>
  </form>
  <p class="mt-6 text-sm text-gray-600">계정 발급과 비밀번호 초기화는 운영진에게 문의하세요.</p>
</template>
