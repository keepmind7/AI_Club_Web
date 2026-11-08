<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '../api'
import { dateTime, regStatus, won } from '../format'
import type { EventSummary } from '../types'

const past = ref(false)
const events = ref<EventSummary[]>([])
const loading = ref(true)
const error = ref('')

watch(
  past,
  async (isPast) => {
    loading.value = true
    error.value = ''
    try {
      events.value = await api<EventSummary[]>(isPast ? '/api/events?past=1' : '/api/events')
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

const tabClass = (active: boolean) =>
  `min-h-11 flex-1 rounded px-3 ${active ? 'bg-blue-700 text-white' : 'bg-white border border-gray-300'}`
</script>

<template>
  <h1 class="mb-4 text-xl font-bold">모임</h1>
  <div class="mb-4 flex gap-2">
    <button type="button" :aria-pressed="!past" :class="tabClass(!past)" @click="past = false">예정 모임</button>
    <button type="button" :aria-pressed="past" :class="tabClass(past)" @click="past = true">지난 모임</button>
  </div>
  <p v-if="loading">불러오는 중…</p>
  <p v-else-if="error" role="alert" class="text-red-700">{{ error }}</p>
  <p v-else-if="!events.length" class="text-gray-600">모임이 없습니다.</p>
  <ul v-else class="divide-y divide-gray-200 rounded bg-white">
    <li v-for="e in events" :key="e.id">
      <RouterLink :to="`/events/${e.id}`" class="block min-h-11 px-3 py-3">
        <span class="flex justify-between gap-2">
          <span class="font-medium">{{ e.title }}</span>
          <span v-if="e.my_status" class="shrink-0 text-sm font-medium text-blue-700">{{ regStatus[e.my_status] }}</span>
        </span>
        <span class="block text-sm text-gray-600">{{ dateTime(e.starts_at) }} · {{ e.place }}</span>
        <span class="block text-sm text-gray-600">
          {{ e.capacity ? `확정 ${e.confirmed_count}/${e.capacity}명` : `확정 ${e.confirmed_count}명 (정원 없음)` }}
          <template v-if="e.waitlist_count"> · 대기 {{ e.waitlist_count }}명</template>
          · {{ e.fee ? `참가비 ${won(e.fee)}` : '무료' }}
        </span>
      </RouterLink>
    </li>
  </ul>
</template>
