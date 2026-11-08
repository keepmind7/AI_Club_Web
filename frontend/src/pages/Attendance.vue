<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'
import { attendanceMark, dateTime } from '../format'
import type { MyAttendance } from '../types'

const data = ref<MyAttendance | null>(null)
const error = ref('')

api<MyAttendance>('/api/me/attendance')
  .then((d) => (data.value = d))
  .catch((e: Error) => (error.value = e.message))
</script>

<template>
  <h1 class="mb-4 text-xl font-bold">나의 출석 기록</h1>
  <p v-if="error" role="alert" class="text-red-700">{{ error }}</p>
  <p v-else-if="!data">불러오는 중…</p>
  <div v-else class="space-y-4">
    <dl class="grid grid-cols-4 gap-2 text-center">
      <div class="rounded bg-white p-2"><dt class="text-sm text-gray-600">출석률</dt><dd class="text-lg font-bold">{{ data.rate === null ? '-' : `${data.rate}%` }}</dd></div>
      <div class="rounded bg-white p-2"><dt class="text-sm text-gray-600">대상</dt><dd class="text-lg font-bold">{{ data.total }}</dd></div>
      <div class="rounded bg-white p-2"><dt class="text-sm text-gray-600">출석</dt><dd class="text-lg font-bold">{{ data.present }}</dd></div>
      <div class="rounded bg-white p-2"><dt class="text-sm text-gray-600">결석</dt><dd class="text-lg font-bold">{{ data.absent }}</dd></div>
    </dl>
    <p v-if="!data.records.length" class="text-gray-600">출석 기록이 없습니다.</p>
    <ul v-else class="divide-y divide-gray-200 rounded bg-white">
      <li v-for="r in data.records" :key="r.event_id">
        <RouterLink :to="`/events/${r.event_id}`" class="flex min-h-11 items-center justify-between gap-2 px-3 py-2">
          <span>{{ r.title }} <span class="block text-sm text-gray-600">{{ dateTime(r.starts_at) }}</span></span>
          <span class="shrink-0 text-sm font-medium">{{ attendanceMark[r.attendance] }}</span>
        </RouterLink>
      </li>
    </ul>
  </div>
</template>
