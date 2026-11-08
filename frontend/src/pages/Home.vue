<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '../api'
import { useAuth } from '../auth'
import { dateTime, month, regStatus, won } from '../format'
import type { Announcement, EventSummary, MyPayments } from '../types'

const auth = useAuth()
const events = ref<EventSummary[]>([])
const notices = ref<Announcement[]>([])
const payments = ref<MyPayments | null>(null)
const loading = ref(true)
const error = ref('')

const mine = computed(() => events.value.filter((e) => e.my_status))
const unpaidDues = computed(() => payments.value?.dues.filter((d) => !d.paid) ?? [])
const unpaidFees = computed(() => payments.value?.event_fees.filter((f) => !f.paid) ?? [])

Promise.all([
  api<EventSummary[]>('/api/events'),
  api<Announcement[]>('/api/announcements'),
  api<MyPayments>('/api/me/payments'),
])
  .then(([e, a, p]) => {
    events.value = e
    notices.value = a
    payments.value = p
  })
  .catch((e: Error) => (error.value = e.message))
  .finally(() => (loading.value = false))
</script>

<template>
  <h1 class="mb-4 text-xl font-bold">{{ auth.user?.name }}님, 안녕하세요</h1>
  <p v-if="loading">불러오는 중…</p>
  <p v-else-if="error" role="alert" class="text-red-700">{{ error }}</p>
  <div v-else class="space-y-6">
    <section>
      <h2 class="mb-2 font-bold">최근 공지</h2>
      <p v-if="!notices.length" class="text-sm text-gray-600">공지가 없습니다.</p>
      <ul v-else class="divide-y divide-gray-200 rounded bg-white">
        <li v-for="n in notices.slice(0, 3)" :key="n.id">
          <RouterLink to="/announcements" class="flex min-h-11 items-center px-3">{{ n.title }}</RouterLink>
        </li>
      </ul>
    </section>

    <section>
      <h2 class="mb-2 font-bold">다가오는 모임</h2>
      <p v-if="!events.length" class="text-sm text-gray-600">예정된 모임이 없습니다.</p>
      <ul v-else class="divide-y divide-gray-200 rounded bg-white">
        <li v-for="e in events.slice(0, 3)" :key="e.id">
          <RouterLink :to="`/events/${e.id}`" class="block min-h-11 px-3 py-2">
            <span class="font-medium">{{ e.title }}</span>
            <span class="block text-sm text-gray-600">{{ dateTime(e.starts_at) }} · {{ e.place }}</span>
          </RouterLink>
        </li>
      </ul>
    </section>

    <section>
      <h2 class="mb-2 font-bold">내 신청 현황</h2>
      <p v-if="!mine.length" class="text-sm text-gray-600">신청한 모임이 없습니다.</p>
      <ul v-else class="divide-y divide-gray-200 rounded bg-white">
        <li v-for="e in mine" :key="e.id">
          <RouterLink :to="`/events/${e.id}`" class="flex min-h-11 items-center justify-between gap-2 px-3 py-2">
            <span>{{ e.title }} <span class="block text-sm text-gray-600">{{ dateTime(e.starts_at) }}</span></span>
            <span class="shrink-0 text-sm font-medium">{{ regStatus[e.my_status!] }}</span>
          </RouterLink>
        </li>
      </ul>
    </section>

    <section>
      <h2 class="mb-2 font-bold">내 미납 내역</h2>
      <p v-if="!unpaidDues.length && !unpaidFees.length" class="text-sm text-gray-600">미납 내역이 없습니다.</p>
      <ul v-else class="divide-y divide-gray-200 rounded bg-white">
        <li v-for="d in unpaidDues" :key="d.month" class="flex min-h-11 items-center justify-between px-3">
          <span>{{ month(d.month) }} 회비</span><span>{{ won(payments!.monthly_dues) }}</span>
        </li>
        <li v-for="f in unpaidFees" :key="f.event_id" class="flex min-h-11 items-center justify-between px-3">
          <span>{{ f.title }} 참가비</span><span>{{ won(f.fee) }}</span>
        </li>
      </ul>
      <RouterLink to="/payments" class="mt-2 inline-flex min-h-11 items-center text-sm text-blue-700 underline">납부 내역 전체 보기</RouterLink>
    </section>
  </div>
</template>
