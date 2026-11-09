<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'
import BackHeader from '../components/BackHeader.vue'
import { attendanceMark, dateTime } from '../format'
import type { MyAttendance } from '../types'

const data = ref<MyAttendance | null>(null)
const error = ref('')

api<MyAttendance>('/api/me/attendance')
  .then((d) => (data.value = d))
  .catch((e: Error) => (error.value = e.message))

const markClass = { present: 'font-bold text-ok', absent: 'font-bold text-warn', unknown: 'text-muted' }
</script>

<template>
  <BackHeader to="/me" label="내 정보" />
  <div class="flex w-full max-w-2xl flex-col gap-6 px-5 pt-[22px] pb-7 lg:px-10">
    <h1 class="text-[26px] font-semibold text-brand">출석</h1>
    <p v-if="error" role="alert" class="text-warn">{{ error }}</p>
    <p v-else-if="!data" class="text-muted">불러오는 중…</p>
    <template v-else>
      <section v-if="data.total" class="flex flex-col gap-1.5 rounded-2xl border border-line bg-surface p-[18px]">
        <h2 class="text-[13px] font-bold text-brand">출석률</h2>
        <span class="text-[30px] font-semibold tabular-nums">{{ data.rate === null ? '-' : `${data.rate}%` }}</span>
        <span class="text-sm text-ink-2">확정된 모임 {{ data.total }}번 중 {{ data.present }}번 출석, {{ data.absent }}번 결석</span>
      </section>
      <p v-if="!data.records.length" class="text-[15px] text-muted">아직 출석 기록이 없어요.</p>
      <div v-else class="flex flex-col border-t border-line">
        <RouterLink v-for="r in data.records" :key="r.event_id" :to="`/events/${r.event_id}`"
          class="flex min-h-[60px] items-center justify-between gap-3 border-b border-line-soft px-1 py-2 text-ink">
          <span class="flex min-w-0 flex-col gap-0.5">
            <span class="text-[15px] font-medium">{{ r.title }}</span>
            <span class="text-[13px] text-muted">{{ dateTime(r.starts_at) }}</span>
          </span>
          <span class="shrink-0 text-[13px]" :class="markClass[r.attendance]">{{ attendanceMark[r.attendance] }}</span>
        </RouterLink>
      </div>
    </template>
  </div>
</template>
