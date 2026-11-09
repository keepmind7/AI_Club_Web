<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'
import { passwordError, passwordHint } from '../format'

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const name = ref('')
const phone = ref('')
const email = ref('')
const error = ref('')
const done = ref('')
const busy = ref(false)

// 마지막 중복 확인 결과. 아이디를 바꾸면 username이 달라져 다시 확인해야 한다.
const checked = ref<{ username: string; available: boolean; detail: string } | null>(null)
const checking = ref(false)
const current = () => (checked.value?.username === username.value.trim() ? checked.value : null)

async function checkUsername() {
  const u = username.value.trim()
  error.value = ''
  checking.value = true
  try {
    const r = await api<{ available: boolean; detail: string }>('/api/auth/username-check?username=' + encodeURIComponent(u))
    checked.value = { username: u, ...r }
  } catch (e) {
    checked.value = { username: u, available: false, detail: (e as Error).message }
  } finally {
    checking.value = false
  }
}

async function submit() {
  const c = current()
  error.value = !c ? '아이디 중복 확인을 해 주세요.'
    : !c.available ? c.detail
    : password.value !== confirmPassword.value ? '비밀번호가 서로 달라요. 다시 확인해 주세요.'
    : passwordError(password.value)
  if (error.value) return
  busy.value = true
  try {
    const res = await api<{ detail: string }>('/api/auth/signup', 'POST', {
      username: username.value, password: password.value, name: name.value, phone: phone.value, email: email.value,
    })
    done.value = res.detail
  } catch (e) {
    error.value = (e as Error).message
    // 확인 뒤 다른 사람이 먼저 가입한 경우: 초록 "쓸 수 있는 아이디예요."를 지우고 다시 확인하게 한다.
    if (error.value === '이미 쓰고 있는 아이디예요.') checked.value = null
  } finally {
    busy.value = false
  }
}

const field = 'flex flex-col gap-1.5'
const label = 'text-sm font-medium text-ink-2'
const input = 'h-12 rounded-xl border border-field bg-surface px-3.5 text-base'
const button = 'mt-1 flex h-[50px] items-center justify-center rounded-xl bg-accent text-base font-medium text-white disabled:opacity-45'
</script>

<template>
  <div class="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-6 px-6 py-8">
    <h1 class="text-[26px] font-semibold text-brand">{{ done ? '가입 신청 완료' : '회원가입' }}</h1>

    <template v-if="done">
      <p role="status" class="text-[15px] leading-relaxed text-ink-2">{{ done }}</p>
      <RouterLink to="/login" :class="button">로그인 화면으로</RouterLink>
    </template>

    <template v-else>
      <form class="flex flex-col gap-4" @submit.prevent="submit">
        <div :class="field">
          <label for="username" :class="label">아이디</label>
          <div class="flex gap-2">
            <input id="username" v-model="username" required maxlength="150" autocomplete="username" autocapitalize="none" spellcheck="false"
              aria-describedby="username-check" :class="input" class="min-w-0 flex-1" />
            <button type="button" :disabled="checking || !username.trim()" @click="checkUsername"
              class="h-12 shrink-0 rounded-xl border border-field bg-surface px-4 text-[15px] font-medium text-brand disabled:opacity-45">
              {{ checking ? '확인 중…' : '중복 확인' }}
            </button>
          </div>
          <p id="username-check" aria-live="polite" class="text-[13px]" :class="current()?.available ? 'text-ok' : 'text-warn'">{{ current()?.detail }}</p>
        </div>
        <div :class="field">
          <label for="password" :class="label">비밀번호</label>
          <input id="password" v-model="password" type="password" required autocomplete="new-password" aria-describedby="password-hint" :class="input" />
          <p id="password-hint" class="text-[13px] text-muted">{{ passwordHint }}</p>
        </div>
        <div :class="field">
          <label for="confirm" :class="label">비밀번호 확인</label>
          <input id="confirm" v-model="confirmPassword" type="password" required autocomplete="new-password" :class="input" />
        </div>
        <div :class="field">
          <label for="name" :class="label">이름</label>
          <input id="name" v-model="name" required maxlength="50" autocomplete="name" :class="input" />
        </div>
        <div :class="field">
          <label for="phone" :class="label">연락처</label>
          <input id="phone" v-model="phone" type="tel" inputmode="tel" required maxlength="20" autocomplete="tel" placeholder="010-1234-5678" :class="input" />
        </div>
        <div :class="field">
          <label for="email" :class="label">이메일</label>
          <input id="email" v-model="email" type="email" required maxlength="254" autocomplete="email" autocapitalize="none" spellcheck="false" :class="input" />
        </div>
        <p v-if="error" role="alert" class="text-sm text-warn">{{ error }}</p>
        <button type="submit" :disabled="busy" :class="button">{{ busy ? '보내는 중…' : '가입 신청하기' }}</button>
      </form>
      <p class="text-sm text-muted">
        이미 계정이 있나요?
        <RouterLink to="/login" class="inline-flex min-h-11 items-center px-1 font-medium text-brand underline underline-offset-2">로그인</RouterLink>
      </p>
    </template>
  </div>
</template>
