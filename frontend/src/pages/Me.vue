<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../auth'
import { date } from '../format'

const auth = useAuth()
const router = useRouter()
const error = ref('')
const busy = ref(false)

async function logout() {
  busy.value = true
  error.value = ''
  try {
    await auth.logout()
    router.push('/login')
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <h1 class="mb-4 text-xl font-bold">내 정보</h1>
  <dl v-if="auth.user" class="divide-y divide-gray-200 rounded bg-white">
    <div class="flex min-h-11 items-center justify-between px-3"><dt class="text-gray-600">이름</dt><dd>{{ auth.user.name }}</dd></div>
    <div class="flex min-h-11 items-center justify-between px-3"><dt class="text-gray-600">아이디</dt><dd>{{ auth.user.username }}</dd></div>
    <div class="flex min-h-11 items-center justify-between px-3"><dt class="text-gray-600">연락처</dt><dd>{{ auth.user.phone || '-' }}</dd></div>
    <div class="flex min-h-11 items-center justify-between px-3"><dt class="text-gray-600">가입일</dt><dd>{{ auth.user.joined_on ? date(auth.user.joined_on) : '-' }}</dd></div>
    <div class="flex min-h-11 items-center justify-between px-3"><dt class="text-gray-600">구분</dt><dd>{{ auth.user.is_staff ? '운영진' : '회원' }}</dd></div>
  </dl>
  <div class="mt-6 space-y-3">
    <RouterLink to="/password" class="flex min-h-11 items-center justify-center rounded border border-gray-300 bg-white">비밀번호 변경</RouterLink>
    <button type="button" :disabled="busy" @click="logout" class="min-h-11 w-full rounded bg-gray-800 font-medium text-white disabled:opacity-50">
      {{ busy ? '로그아웃 중…' : '로그아웃' }}
    </button>
    <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
  </div>
</template>
