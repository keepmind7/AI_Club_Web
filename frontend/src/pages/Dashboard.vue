<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '../api'
import { category, month, won } from '../format'
import type { Category, Dashboard } from '../types'

const data = ref<Dashboard | null>(null)
const error = ref('')
const loading = ref(true)
// 출석률 기간. 계약상 기간은 attendance에만 적용되므로 전체를 다시 받아도 다른 값은 그대로다.
const year = ref('')
const mon = ref('')
// shortcut: 최근 5년만 고를 수 있다. 더 오래 운영하면 장부·모임 연도에서 목록을 만든다.
const thisYear = new Date().getFullYear()
const years = Array.from({ length: 5 }, (_, i) => String(thisYear - i))

watch(
  [year, mon],
  async (_, __, onCleanup) => {
    // 기간을 다시 바꾸면 이전 요청의 응답은 버린다.
    let stale = false
    onCleanup(() => (stale = true))
    loading.value = true
    error.value = ''
    const q = year.value ? `?year=${year.value}${mon.value ? `&month=${mon.value}` : ''}` : ''
    try {
      const d = await api<Dashboard>('/api/dashboard' + q)
      if (!stale) data.value = d
    } catch (e) {
      if (!stale) error.value = (e as Error).message
    } finally {
      if (!stale) loading.value = false
    }
  },
  { immediate: true },
)

const categories = Object.keys(category) as Category[]
const th = 'px-3 py-2 text-left font-medium text-gray-600'
const td = 'px-3 py-2'
</script>

<template>
  <h1 class="mb-4 text-xl font-bold">운영 대시보드</h1>
  <p v-if="!data && error" role="alert" class="text-red-700">{{ error }}</p>
  <p v-else-if="!data">불러오는 중…</p>
  <div v-else class="space-y-6">
    <section class="rounded bg-white p-4">
      <h2 class="text-sm text-gray-600">계산 잔액</h2>
      <p class="text-2xl font-bold">{{ won(data.balance) }}</p>
      <p class="text-sm text-gray-600">이월 잔액 {{ won(data.carry_over) }} + 이월 기준일 다음 날부터의 거래. 모임통장 잔액과 비교해 확인하세요.</p>
    </section>

    <section>
      <h2 class="mb-2 font-bold">구분별 합계</h2>
      <p class="mb-2 text-sm text-gray-600">이월 기준일 다음 날부터 집계합니다.</p>
      <table class="w-full rounded bg-white text-sm">
        <tbody class="divide-y divide-gray-200">
          <tr v-for="c in categories" :key="c">
            <th scope="row" :class="th">{{ category[c] }}</th>
            <td :class="td" class="text-right">{{ won(data.totals[c]) }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section>
      <h2 class="mb-2 font-bold">월별 정산</h2>
      <p class="mb-2 text-sm text-gray-600">이월 기준일과 관계없이 전체 기간을 보여 줍니다.</p>
      <p v-if="!data.monthly.length" class="text-sm text-gray-600">거래가 없습니다.</p>
      <div v-else class="overflow-x-auto">
        <table class="w-full rounded bg-white text-sm">
          <thead><tr><th :class="th">월</th><th :class="th" class="text-right">수입</th><th :class="th" class="text-right">지출·환불</th><th :class="th" class="text-right">차액</th></tr></thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-for="m in data.monthly" :key="m.month">
              <td :class="td">{{ month(m.month) }}</td>
              <td :class="td" class="text-right">{{ won(m.income) }}</td>
              <td :class="td" class="text-right">{{ won(m.expense) }}</td>
              <td :class="td" class="text-right">{{ won(m.income - m.expense) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section>
      <h2 class="mb-2 font-bold">회비 미납자 ({{ data.unpaid_dues.length }}명)</h2>
      <p v-if="!data.unpaid_dues.length" class="text-sm text-gray-600">없습니다.</p>
      <ul v-else class="divide-y divide-gray-200 rounded bg-white text-sm">
        <li v-for="u in data.unpaid_dues" :key="u.member_id" class="px-3 py-2">
          <span class="font-medium">{{ u.name }}</span>
          <span class="block text-gray-600">{{ u.months.map(month).join(', ') }}</span>
        </li>
      </ul>
    </section>

    <section>
      <h2 class="mb-2 font-bold">참가비 미납 ({{ data.unpaid_event_fees.length }}건)</h2>
      <p v-if="!data.unpaid_event_fees.length" class="text-sm text-gray-600">없습니다.</p>
      <div v-else class="overflow-x-auto">
        <table class="w-full rounded bg-white text-sm">
          <thead><tr><th :class="th">모임</th><th :class="th">이름</th><th :class="th" class="text-right">참가비</th></tr></thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-for="u in data.unpaid_event_fees" :key="`${u.event_id}-${u.member_id}`">
              <td :class="td">{{ u.title }}</td><td :class="td">{{ u.name }}</td><td :class="td" class="text-right">{{ won(u.fee) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section>
      <h2 class="mb-2 font-bold">환불 필요 ({{ data.refunds_needed.length }}건)</h2>
      <p v-if="!data.refunds_needed.length" class="text-sm text-gray-600">없습니다.</p>
      <div v-else class="overflow-x-auto">
        <table class="w-full rounded bg-white text-sm">
          <thead><tr><th :class="th">모임</th><th :class="th">이름</th><th :class="th" class="text-right">환불액</th></tr></thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-for="r in data.refunds_needed" :key="`${r.event_id}-${r.member_id}`">
              <td :class="td">{{ r.title }}</td><td :class="td">{{ r.name }}</td><td :class="td" class="text-right">{{ won(r.amount) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section>
      <h2 class="mb-2 font-bold">출석률</h2>
      <div class="mb-2 flex gap-2">
        <div class="flex-1">
          <label for="att-year" class="mb-1 block text-sm text-gray-600">연도</label>
          <select id="att-year" v-model="year" @change="mon = ''" class="min-h-11 w-full rounded border border-gray-300 bg-white px-2">
            <option value="">전체 기간</option>
            <option v-for="y in years" :key="y" :value="y">{{ y }}년</option>
          </select>
        </div>
        <div class="flex-1">
          <label for="att-month" class="mb-1 block text-sm text-gray-600">월</label>
          <select id="att-month" v-model="mon" :disabled="!year" class="min-h-11 w-full rounded border border-gray-300 bg-white px-2 disabled:opacity-50">
            <option value="">연간</option>
            <option v-for="m in 12" :key="m" :value="String(m)">{{ m }}월</option>
          </select>
        </div>
      </div>
      <p v-if="loading">불러오는 중…</p>
      <p v-else-if="error" role="alert" class="text-red-700">{{ error }}</p>
      <p v-else-if="!data.attendance.length" class="text-sm text-gray-600">활동 회원이 없습니다.</p>
      <div v-else class="overflow-x-auto">
        <table class="w-full rounded bg-white text-sm">
          <thead><tr><th :class="th">이름</th><th :class="th" class="text-right">출석/대상</th><th :class="th" class="text-right">출석률</th></tr></thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-for="a in data.attendance" :key="a.member_id">
              <td :class="td">{{ a.name }}</td>
              <td :class="td" class="text-right">{{ a.present }}/{{ a.total }}</td>
              <td :class="td" class="text-right">{{ a.rate === null ? '-' : `${a.rate}%` }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
