<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'
import BackHeader from '../components/BackHeader.vue'
import { category, date, dateTime, month, thisMonth, won } from '../format'
import type { MyPayments } from '../types'

const data = ref<MyPayments | null>(null)
const error = ref('')

api<MyPayments>('/api/me/payments')
  .then((d) => (data.value = d))
  .catch((e: Error) => (error.value = e.message))

const h2 = 'text-[19px] font-semibold text-brand'
const th = 'border-b border-line py-2 text-left text-[13px] font-medium text-muted'
const td = 'border-b border-line-soft py-3'
const paid = (p: boolean) => (p ? 'font-bold text-ok' : 'font-bold text-warn')
// 이번 달 회비는 아직 납부 기간이라 '미납'(경고) 대신 '납부 전'(회색). 내 정보 배지·대시보드와 같은 기준.
const now = thisMonth()
const duesState = (d: MyPayments['dues'][number]) => {
  if (d.paid) return { text: '납부', cls: paid(true) }
  if (d.month === now) return { text: '납부 전', cls: 'text-muted' }
  return { text: '미납', cls: paid(false) }
}
</script>

<template>
  <BackHeader to="/me" label="내 정보" />
  <div class="flex w-full max-w-2xl flex-col gap-7 px-5 pt-[22px] pb-7 lg:px-10">
    <h1 class="text-[26px] font-semibold text-brand">납부 내역</h1>
    <p v-if="error" role="alert" class="text-warn">{{ error }}</p>
    <p v-else-if="!data" class="text-muted">불러오는 중…</p>
    <template v-else>
      <section class="flex flex-col gap-2">
        <h2 :class="h2">회비</h2>
        <p class="text-[15px] leading-relaxed text-ink-2">
          {{ data.monthly_dues ? `월 회비는 ${won(data.monthly_dues)}이에요.` : '월 회비를 걷지 않아요.' }}
        </p>
        <table v-if="data.dues.length" class="w-full border-collapse text-[15px]">
          <thead><tr><th scope="col" :class="th">월</th><th scope="col" :class="th" class="text-right">상태</th></tr></thead>
          <tbody>
            <tr v-for="d in data.dues" :key="d.month">
              <td :class="td">{{ month(d.month) }}</td>
              <td :class="[td, duesState(d).cls]" class="text-right">{{ duesState(d).text }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="flex flex-col gap-2">
        <h2 :class="h2">참가비</h2>
        <p v-if="!data.event_fees.length" class="text-[15px] text-muted">참가비 내역이 없어요.</p>
        <table v-else class="w-full border-collapse text-[15px]">
          <thead><tr><th scope="col" :class="th">모임</th><th scope="col" :class="th" class="text-right">금액</th><th scope="col" :class="th" class="w-16 text-right">상태</th></tr></thead>
          <tbody>
            <tr v-for="f in data.event_fees" :key="f.event_id">
              <td :class="td">{{ f.title }}<span class="block text-[13px] text-muted">{{ dateTime(f.starts_at) }}</span></td>
              <td :class="td" class="text-right tabular-nums">{{ won(f.fee) }}</td>
              <td :class="[td, paid(f.paid)]" class="text-right">{{ f.paid ? '납부' : '미납' }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="flex flex-col gap-2">
        <h2 :class="h2">장부에 적힌 내 거래</h2>
        <p v-if="!data.transactions.length" class="text-[15px] text-muted">장부에 적힌 내 거래가 아직 없어요.</p>
        <table v-else class="w-full border-collapse text-[15px]">
          <thead><tr><th scope="col" :class="th">날짜</th><th scope="col" :class="th">내용</th><th scope="col" :class="th" class="text-right">금액</th></tr></thead>
          <tbody>
            <tr v-for="(t, i) in data.transactions" :key="i">
              <td :class="td" class="pr-3 whitespace-nowrap text-muted tabular-nums">{{ date(t.date) }}</td>
              <td :class="td">{{ category[t.category] }}<span v-if="t.memo" class="block text-[13px] text-muted">{{ t.memo }}</span></td>
              <td :class="td" class="text-right tabular-nums">{{ won(t.amount) }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </div>
</template>
