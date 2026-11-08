<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'
import { category, date, dateTime, month, won } from '../format'
import type { MyPayments } from '../types'

const data = ref<MyPayments | null>(null)
const error = ref('')

api<MyPayments>('/api/me/payments')
  .then((d) => (data.value = d))
  .catch((e: Error) => (error.value = e.message))

const paidClass = (paid: boolean) => `shrink-0 text-sm font-medium ${paid ? 'text-green-700' : 'text-red-700'}`
</script>

<template>
  <h1 class="mb-4 text-xl font-bold">나의 납부 내역</h1>
  <p v-if="error" role="alert" class="text-red-700">{{ error }}</p>
  <p v-else-if="!data">불러오는 중…</p>
  <div v-else class="space-y-6">
    <section>
      <h2 class="mb-2 font-bold">월 회비<template v-if="data.monthly_dues"> ({{ won(data.monthly_dues) }})</template></h2>
      <p v-if="!data.dues.length" class="text-sm text-gray-600">{{ data.monthly_dues ? '회비 내역이 없습니다.' : '월 회비를 걷지 않습니다.' }}</p>
      <ul v-else class="divide-y divide-gray-200 rounded bg-white">
        <li v-for="d in data.dues" :key="d.month" class="flex min-h-11 items-center justify-between px-3">
          <span>{{ month(d.month) }}</span><span :class="paidClass(d.paid)">{{ d.paid ? '납부' : '미납' }}</span>
        </li>
      </ul>
    </section>

    <section>
      <h2 class="mb-2 font-bold">참가비</h2>
      <p v-if="!data.event_fees.length" class="text-sm text-gray-600">참가비 내역이 없습니다.</p>
      <ul v-else class="divide-y divide-gray-200 rounded bg-white">
        <li v-for="f in data.event_fees" :key="f.event_id" class="flex min-h-11 items-center justify-between gap-2 px-3 py-2">
          <span>{{ f.title }} <span class="block text-sm text-gray-600">{{ dateTime(f.starts_at) }} · {{ won(f.fee) }}</span></span>
          <span :class="paidClass(f.paid)">{{ f.paid ? '납부' : '미납' }}</span>
        </li>
      </ul>
    </section>

    <section>
      <h2 class="mb-2 font-bold">거래 기록</h2>
      <p v-if="!data.transactions.length" class="text-sm text-gray-600">거래 기록이 없습니다.</p>
      <ul v-else class="divide-y divide-gray-200 rounded bg-white">
        <li v-for="(t, i) in data.transactions" :key="i" class="flex min-h-11 items-center justify-between gap-2 px-3 py-2">
          <span>{{ category[t.category] }} <span class="block text-sm text-gray-600">{{ date(t.date) }}<template v-if="t.memo"> · {{ t.memo }}</template></span></span>
          <span class="shrink-0">{{ won(t.amount) }}</span>
        </li>
      </ul>
    </section>
  </div>
</template>
