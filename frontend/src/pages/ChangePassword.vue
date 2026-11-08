<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useAuth } from '../auth'

const auth = useAuth()
const router = useRouter()
const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  if (newPassword.value !== confirmPassword.value) {
    error.value = '새 비밀번호와 확인이 다릅니다.'
    return
  }
  busy.value = true
  try {
    await api('/api/auth/password', 'POST', { old_password: oldPassword.value, new_password: newPassword.value })
    if (auth.user) auth.user.must_change_password = false
    router.push('/')
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <h1 class="mb-2 text-xl font-bold">비밀번호 변경</h1>
  <p v-if="auth.user?.must_change_password" class="mb-4 text-sm text-gray-700">
    임시 비밀번호로 로그인했습니다. 새 비밀번호로 바꿔야 이용할 수 있습니다.
  </p>
  <form class="space-y-4" @submit.prevent="submit">
    <div>
      <label for="old" class="mb-1 block text-sm font-medium">현재 비밀번호</label>
      <input id="old" v-model="oldPassword" type="password" required autocomplete="current-password"
        class="min-h-11 w-full rounded border border-gray-300 bg-white px-3" />
    </div>
    <div>
      <label for="new" class="mb-1 block text-sm font-medium">새 비밀번호</label>
      <input id="new" v-model="newPassword" type="password" required autocomplete="new-password"
        class="min-h-11 w-full rounded border border-gray-300 bg-white px-3" />
    </div>
    <div>
      <label for="confirm" class="mb-1 block text-sm font-medium">새 비밀번호 확인</label>
      <input id="confirm" v-model="confirmPassword" type="password" required autocomplete="new-password"
        class="min-h-11 w-full rounded border border-gray-300 bg-white px-3" />
    </div>
    <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
    <button type="submit" :disabled="busy" class="min-h-11 w-full rounded bg-blue-700 font-medium text-white disabled:opacity-50">
      {{ busy ? '변경 중…' : '변경' }}
    </button>
  </form>
</template>
