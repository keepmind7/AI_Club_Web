<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'
import { useAuth } from '../auth'
import type { SharedAccount } from '../types'

const isStaff = useAuth().user?.is_staff
const items = ref<SharedAccount[] | null>(null)
const error = ref('')
// 마지막으로 누른 복사 버튼(`${id}-email` 등)과 결과 문구. 잠시 뒤 지운다.
const status = ref({ key: '', text: '' })
let timer = 0

api<SharedAccount[]>('/api/shared-accounts')
  .then((d) => (items.value = d))
  .catch((e: Error) => (error.value = e.message))

async function copy(key: string, value: string) {
  try {
    // HTTP(비보안) 접속에서는 navigator.clipboard가 없어 실패로 처리된다.
    await navigator.clipboard.writeText(value)
    status.value = { key, text: '복사했습니다' }
  } catch {
    status.value = { key, text: '복사하지 못했습니다' }
  }
  clearTimeout(timer)
  timer = window.setTimeout(() => (status.value = { key: '', text: '' }), 2000)
}

const btn = 'min-h-11 min-w-11 shrink-0 rounded border border-gray-300 bg-white px-3 text-sm hover:bg-gray-100'
</script>

<template>
  <h1 class="mb-4 text-xl font-bold">
    공유 계정
    <span v-if="isStaff && items" class="text-sm font-normal text-gray-600">전체 {{ items.length }}개</span>
  </h1>
  <p v-if="isStaff" class="mb-4 text-sm">
    <a href="/club-admin/club/sharedaccount/" class="text-blue-700 underline">등록·수정은 관리자 화면에서</a>
  </p>
  <p v-if="error" role="alert" class="text-red-700">{{ error }}</p>
  <p v-else-if="!items">불러오는 중…</p>
  <p v-else-if="!items.length" class="text-gray-600">
    <template v-if="isStaff">
      등록된 공유 계정이 없습니다. <a href="/club-admin/" class="text-blue-700 underline">관리자 화면</a>에서 등록하세요.
    </template>
    <template v-else>배정된 공유 계정이 없습니다. 운영진에게 문의하세요.</template>
  </p>
  <ul v-else class="space-y-4">
    <li v-for="a in items" :key="a.id" class="space-y-2 rounded bg-white p-3">
      <div v-for="f in (['email', 'password'] as const)" :key="f" class="flex items-center gap-2">
        <span class="w-16 shrink-0 text-sm text-gray-600">{{ f === 'email' ? '이메일' : '비밀번호' }}</span>
        <span class="min-w-0 flex-1 break-all font-medium">{{ f === 'email' ? a.email : '********' }}</span>
        <span aria-live="polite" class="shrink-0 text-sm text-gray-600">{{ status.key === `${a.id}-${f}` ? status.text : '' }}</span>
        <button type="button" :class="btn" :aria-label="f === 'email' ? '이메일 복사' : '비밀번호 복사'" @click="copy(`${a.id}-${f}`, a[f])">
          복사
        </button>
      </div>
      <p v-if="a.memo" class="whitespace-pre-line text-sm">{{ a.memo }}</p>
      <div>
        <h2 class="text-sm text-gray-600">같이 쓰는 사람</h2>
        <p v-if="!a.members.length" class="text-sm text-gray-600">배정된 회원이 없습니다.</p>
        <ul v-else class="list-disc pl-5">
          <li v-for="(m, i) in a.members" :key="i">{{ m.name }}</li>
        </ul>
      </div>
    </li>
  </ul>
</template>
