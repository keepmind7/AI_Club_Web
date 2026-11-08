<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '../api'
import { dateTime, regStatus, won } from '../format'
import type { EventDetail } from '../types'

const props = defineProps<{ id: string }>()
const ev = ref<EventDetail | null>(null)
const loading = ref(true)
const error = ref('')
const actionError = ref('')
const busy = ref(false)

const started = computed(() => !!ev.value && new Date(ev.value.starts_at) <= new Date())

api<EventDetail>(`/api/events/${props.id}`)
  .then((d) => (ev.value = d))
  .catch((e: Error) => (error.value = e.message))
  .finally(() => (loading.value = false))

async function act(action: 'register' | 'cancel') {
  if (action === 'cancel' && !confirm('참석을 취소할까요? 확정 자리는 대기자에게 넘어갑니다.')) return
  busy.value = true
  actionError.value = ''
  try {
    // 응답으로 받은 상세로 바로 바꾼다 (다시 불러오지 않음)
    ev.value = await api<EventDetail>(`/api/events/${props.id}/${action}`, 'POST')
  } catch (e) {
    actionError.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <RouterLink to="/events" class="mb-2 inline-flex min-h-11 items-center text-sm text-blue-700">← 모임 목록</RouterLink>
  <p v-if="loading">불러오는 중…</p>
  <p v-else-if="error" role="alert" class="text-red-700">{{ error }}</p>
  <article v-else-if="ev" class="space-y-4">
    <header>
      <h1 class="text-xl font-bold">{{ ev.title }}</h1>
      <p class="text-gray-700">{{ dateTime(ev.starts_at) }}</p>
      <p class="text-gray-700">{{ ev.place }}</p>
      <p class="text-gray-700">
        {{ ev.capacity ? `확정 ${ev.confirmed_count}/${ev.capacity}명` : `확정 ${ev.confirmed_count}명 (정원 없음)` }}
        <template v-if="ev.waitlist_count"> · 대기 {{ ev.waitlist_count }}명</template>
        · {{ ev.fee ? `참가비 ${won(ev.fee)}` : '무료' }}
      </p>
    </header>

    <p v-if="ev.description" class="whitespace-pre-line rounded bg-white p-3">{{ ev.description }}</p>

    <section class="rounded bg-white p-3" aria-live="polite">
      <p v-if="ev.my_status === 'confirmed'" class="font-medium">참석 확정되었습니다.</p>
      <p v-else-if="ev.my_status === 'waitlisted'" class="font-medium">대기 {{ ev.my_waitlist_position }}번입니다. 확정자가 취소하면 순서대로 확정됩니다.</p>
      <p v-else class="text-gray-700">신청하지 않았습니다.</p>
      <p v-if="ev.my_status === 'confirmed' && ev.fee" class="mt-2 rounded bg-yellow-50 p-2 text-sm">
        모임통장으로 참가비 {{ won(ev.fee) }}을 이체해 주세요.
      </p>
      <p v-if="started" class="mt-2 text-sm text-gray-600">이미 시작한 모임이라 신청·취소할 수 없습니다.</p>
      <template v-else>
        <button v-if="ev.my_status" type="button" :disabled="busy" @click="act('cancel')"
          class="mt-3 min-h-11 w-full rounded border border-red-700 font-medium text-red-700 disabled:opacity-50">
          {{ busy ? '처리 중…' : '참석 취소' }}
        </button>
        <button v-else type="button" :disabled="busy" @click="act('register')"
          class="mt-3 min-h-11 w-full rounded bg-blue-700 font-medium text-white disabled:opacity-50">
          {{ busy ? '처리 중…' : ev.capacity && ev.confirmed_count >= ev.capacity ? '대기 신청' : '참석 신청' }}
        </button>
      </template>
      <p v-if="actionError" role="alert" class="mt-2 text-sm text-red-700">{{ actionError }}</p>
    </section>

    <section>
      <h2 class="mb-2 font-bold">참석자 ({{ ev.attendees.length }}명)</h2>
      <p v-if="!ev.attendees.length" class="text-sm text-gray-600">아직 신청자가 없습니다.</p>
      <ol v-else class="divide-y divide-gray-200 rounded bg-white">
        <li v-for="(a, i) in ev.attendees" :key="i" class="flex min-h-11 items-center justify-between px-3">
          <span>{{ a.name }}</span>
          <span class="text-sm text-gray-600">{{ regStatus[a.status] }}</span>
        </li>
      </ol>
    </section>
  </article>
</template>
