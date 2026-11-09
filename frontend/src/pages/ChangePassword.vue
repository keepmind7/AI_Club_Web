<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useAuth } from '../auth'
import BackHeader from '../components/BackHeader.vue'
import { passwordError, passwordHint } from '../format'
import { showToast } from '../toast'

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
    error.value = '새 비밀번호가 서로 달라요. 다시 확인해 주세요.'
    return
  }
  error.value = passwordError(newPassword.value)
  if (error.value) return
  busy.value = true
  try {
    await api('/api/auth/password', 'POST', { old_password: oldPassword.value, new_password: newPassword.value })
    if (auth.user) auth.user.must_change_password = false
    showToast('비밀번호를 바꿨어요')
    router.push('/')
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

const field = 'flex flex-col gap-1.5'
const label = 'text-sm font-medium text-ink-2'
const input = 'h-12 rounded-xl border border-field bg-surface px-3.5 text-base'
</script>

<template>
  <BackHeader v-if="!auth.user?.must_change_password" to="/me" label="내 정보" />
  <div class="flex w-full max-w-sm flex-col gap-6 px-5 pt-[22px] pb-7 lg:px-10"
    :class="auth.user?.must_change_password && 'mx-auto flex-1 justify-center'">
    <div class="flex flex-col gap-1.5">
      <h1 class="text-[26px] font-semibold text-brand">비밀번호 변경</h1>
      <p v-if="auth.user?.must_change_password" class="text-[15px] leading-relaxed text-ink-2">
        임시 비밀번호로 로그인했어요. 새 비밀번호로 바꿔야 이용할 수 있어요.
      </p>
    </div>
    <form class="flex flex-col gap-4" @submit.prevent="submit">
      <div :class="field">
        <label for="old" :class="label">현재 비밀번호</label>
        <input id="old" v-model="oldPassword" type="password" required autocomplete="current-password" :class="input" />
      </div>
      <div :class="field">
        <label for="new" :class="label">새 비밀번호</label>
        <input id="new" v-model="newPassword" type="password" required autocomplete="new-password" aria-describedby="password-hint" :class="input" />
        <p id="password-hint" class="text-[13px] text-muted">{{ passwordHint }}</p>
      </div>
      <div :class="field">
        <label for="confirm" :class="label">새 비밀번호 확인</label>
        <input id="confirm" v-model="confirmPassword" type="password" required autocomplete="new-password" :class="input" />
      </div>
      <p v-if="error" role="alert" class="text-sm text-warn">{{ error }}</p>
      <button type="submit" :disabled="busy" class="mt-1 h-[50px] rounded-xl bg-accent text-base font-medium text-white disabled:opacity-45">
        {{ busy ? '바꾸는 중…' : '비밀번호 바꾸기' }}
      </button>
    </form>
  </div>
</template>
