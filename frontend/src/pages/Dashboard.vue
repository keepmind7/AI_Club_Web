<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import BackHeader from '../components/BackHeader.vue'
import { category, month, won } from '../format'
import type { Category, Dashboard } from '../types'

const route = useRoute()
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
    const first = !data.value
    const q = year.value ? `?year=${year.value}${mon.value ? `&month=${mon.value}` : ''}` : ''
    try {
      const d = await api<Dashboard>('/api/dashboard' + q)
      if (stale) return
      data.value = d
      // 운영 탭의 "회비 미납" 등에서 #구역으로 왔으면 그리고 나서 그 구역으로 내려간다.
      if (first && route.hash) nextTick(() => document.querySelector(route.hash)?.scrollIntoView())
    } catch (e) {
      if (!stale) error.value = (e as Error).message
    } finally {
      if (!stale) loading.value = false
    }
  },
  { immediate: true },
)

const categories = Object.keys(category) as Category[]
const h2 = 'text-xl font-semibold text-brand'
const table = 'w-full border-collapse text-[15px] tabular-nums'
const th = 'border-b border-line py-2.5 pr-3 text-left text-sm font-medium text-muted last:pr-0'
const td = 'border-b border-line-soft py-[11px] pr-3 last:pr-0'
const select = 'min-h-11 min-w-[120px] rounded-[10px] border border-field bg-surface px-2.5 text-[15px] disabled:opacity-45'
</script>

<template>
  <BackHeader to="/staff" label="운영" wide />
  <div class="flex w-full mx-auto max-w-[1080px] flex-col gap-9 px-5 pt-6 pb-14 lg:px-10 lg:pt-8">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <h1 class="text-[28px] font-semibold text-brand lg:text-[30px]">운영 대시보드</h1>
      <a href="/club-admin/club/transaction/add/" class="inline-flex min-h-11 items-center rounded-[10px] bg-accent px-[18px] text-[15px] font-medium text-white">장부 입력</a>
    </div>

    <p v-if="!data && error" role="alert" class="text-warn">{{ error }}</p>
    <p v-else-if="!data" class="text-muted">불러오는 중…</p>
    <template v-else>
      <section aria-labelledby="ledger" class="flex flex-col gap-2 border-b border-line pb-7">
        <h2 id="ledger" class="text-[22px] font-semibold text-brand">장부 잔액 <span class="tabular-nums">{{ won(data.balance) }}</span></h2>
        <p class="text-[15px] leading-relaxed text-ink-2">이월 {{ won(data.carry_over) }}에 이월 기준일 다음 날부터의 거래를 더한 금액이에요.</p>
      </section>

      <section id="unpaid-dues" aria-labelledby="dues-title" class="flex scroll-mt-4 flex-col gap-2.5">
        <h2 id="dues-title" :class="h2">회비 미납 <span :class="data.unpaid_dues.length ? 'text-warn' : 'text-muted'">{{ data.unpaid_dues.length }}명</span></h2>
        <p class="text-sm text-muted">지난달까지 기준이에요.</p>
        <p v-if="!data.unpaid_dues.length" class="text-[15px] text-muted">없어요.</p>
        <ul v-else class="border-t border-line text-[15px]">
          <li v-for="u in data.unpaid_dues" :key="u.member_id" class="flex flex-wrap justify-between gap-x-3 border-b border-line-soft py-[11px]">
            <span class="font-medium">{{ u.name }}</span>
            <span class="text-ink-2">{{ u.months.map(month).join(', ') }}</span>
          </li>
        </ul>
      </section>

      <div class="flex flex-wrap gap-x-10 gap-y-7">
        <section aria-labelledby="monthly" class="flex min-w-0 flex-[999_1_520px] flex-col gap-2.5">
          <h2 id="monthly" :class="h2">월별 정산</h2>
          <p class="text-sm text-muted">전체 기간</p>
          <p v-if="!data.monthly.length" class="text-[15px] text-muted">거래가 없어요.</p>
          <div v-else class="overflow-x-auto">
            <table :class="table">
              <thead><tr><th :class="th">월</th><th :class="th" class="text-right">들어온 돈</th><th :class="th" class="text-right">나간 돈</th><th :class="th" class="text-right">차액</th></tr></thead>
              <tbody>
                <tr v-for="m in data.monthly" :key="m.month">
                  <td :class="td">{{ month(m.month) }}</td>
                  <td :class="td" class="text-right">{{ won(m.income) }}</td>
                  <td :class="td" class="text-right">{{ won(m.expense) }}</td>
                  <td :class="[td, m.income < m.expense && 'text-warn']" class="text-right font-medium">
                    {{ m.income < m.expense ? `${won(m.expense - m.income)} 적자` : won(m.income - m.expense) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section aria-labelledby="totals" class="flex min-w-0 flex-[1_1_280px] flex-col gap-2.5">
          <h2 id="totals" :class="h2">구분별 합계</h2>
          <p class="text-sm text-muted">이월 기준일 다음 날부터</p>
          <table :class="table">
            <tbody>
              <tr v-for="c in categories" :key="c">
                <th scope="row" :class="td" class="text-left font-normal">{{ category[c] }}</th>
                <td :class="td" class="text-right">{{ won(data.totals[c]) }}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>

      <section aria-labelledby="att-title" class="flex flex-col gap-3">
        <div class="flex flex-wrap items-end justify-between gap-3">
          <h2 id="att-title" :class="h2">출석률</h2>
          <div class="flex flex-wrap gap-2">
            <div class="flex flex-col gap-1">
              <label for="att-year" class="text-sm text-muted">연도</label>
              <select id="att-year" v-model="year" :class="select" @change="mon = ''">
                <option value="">전체 기간</option>
                <option v-for="y in years" :key="y" :value="y">{{ y }}년</option>
              </select>
            </div>
            <div class="flex flex-col gap-1">
              <label for="att-month" class="text-sm text-muted">월</label>
              <select id="att-month" v-model="mon" :disabled="!year" :class="select">
                <option value="">1년 전체</option>
                <option v-for="m in 12" :key="m" :value="String(m)">{{ m }}월</option>
              </select>
            </div>
          </div>
        </div>
        <p v-if="loading" class="text-muted">불러오는 중…</p>
        <p v-else-if="error" role="alert" class="text-warn">{{ error }}</p>
        <p v-else-if="!data.attendance.length" class="text-[15px] text-muted">활동 회원이 없어요.</p>
        <div v-else class="overflow-x-auto">
          <table :class="table">
            <thead><tr><th :class="th">회원</th><th :class="th" class="text-right">출석한 모임</th><th :class="th" class="text-right">출석률</th></tr></thead>
            <tbody>
              <tr v-for="a in data.attendance" :key="a.member_id">
                <td :class="td">{{ a.name }}</td>
                <td :class="td" class="text-right">{{ a.total }}번 중 {{ a.present }}번</td>
                <td :class="td" class="text-right font-medium">{{ a.rate === null ? '-' : `${a.rate}%` }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>
