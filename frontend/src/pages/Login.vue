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

const input = 'h-12 rounded-xl border bg-surface px-3.5 text-base'
</script>

<template>
  <div class="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center px-6 py-8">
    <h1 class="mb-8 text-[40px] leading-tight font-semibold text-brand">Mythos</h1>
    <form class="flex flex-col gap-4" @submit.prevent="submit">
      <div class="flex flex-col gap-1.5">
        <label for="username" class="text-sm font-medium text-ink-2">아이디</label>
        <input id="username" v-model="username" required autocomplete="username" autocapitalize="none" :class="input" class="border-field" />
      </div>
      <div class="flex flex-col gap-1.5">
        <label for="password" class="text-sm font-medium text-ink-2">비밀번호</label>
        <input id="password" v-model="password" type="password" required autocomplete="current-password"
          :aria-describedby="error ? 'login-error' : undefined" :class="[input, error ? 'border-warn' : 'border-field']" />
        <p v-if="error" id="login-error" role="alert" class="text-sm text-warn">{{ error }}</p>
      </div>
      <button type="submit" :disabled="busy" class="mt-1 h-[50px] rounded-xl bg-accent text-base font-medium text-white disabled:opacity-45">
        {{ busy ? '로그인 중…' : '로그인' }}
      </button>
    </form>
    <p class="mt-6 text-sm text-muted">
      계정이 없나요?
      <RouterLink to="/signup" class="inline-flex min-h-11 items-center px-1 font-medium text-brand underline underline-offset-2">회원가입</RouterLink>
    </p>
    <p class="text-sm leading-relaxed text-muted">비밀번호를 잊었다면 운영진에게 문의해 주세요.</p>
  </div>
</template>
