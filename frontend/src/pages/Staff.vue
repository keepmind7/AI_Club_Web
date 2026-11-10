<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'
import Chevron from '../components/Chevron.vue'
import { won } from '../format'
import type { Dashboard } from '../types'

const data = ref<Dashboard | null>(null)
const error = ref('')

api<Dashboard>('/api/dashboard')
  .then((d) => (data.value = d))
  .catch((e: Error) => (error.value = e.message))

// 관리자 화면 주소: backend/config/urls.py의 club-admin/ + 앱(club, auth) + 모델 이름
const admin = [
  { href: '/club-admin/club/transaction/add/', title: '장부 입력', sub: '하루 마감' },
  { href: '/club-admin/club/event/', title: '모임 · 출석', sub: '등록, 출석 체크' },
  { href: '/club-admin/club/announcement/add/', title: '공지 쓰기', sub: '소식 탭에 보여요' },
  { href: '/club-admin/auth/user/', title: '회원 · 계정', sub: '발급, 비밀번호 초기화' },
  { href: '/club-admin/club/sharedaccount/', title: '공유 계정', sub: '등록, 회원 배정' },
  { href: '/club-admin/club/post/', title: '게시판 관리', sub: '글 · 댓글 삭제' },
]
</script>

<template>
  <header class="flex shrink-0 flex-col gap-1 border-b border-line-soft px-5 pt-[18px] pb-3.5 lg:px-column lg:pt-9">
    <h1 class="text-2xl font-semibold text-brand">운영</h1>
    <p class="text-[13px] text-muted">운영진에게만 보이는 메뉴예요</p>
  </header>

  <div class="flex w-full mx-auto max-w-2xl flex-col gap-6 px-5 pt-[18px] pb-6 lg:px-10">
    <p v-if="error" role="alert" class="text-warn">{{ error }}</p>
    <p v-else-if="!data" class="text-muted">불러오는 중…</p>
    <template v-else>
      <a v-if="data.pending_signups > 0" href="/club-admin/club/member/?status__exact=pending"
        class="flex min-h-[60px] items-center justify-between gap-2.5 rounded-[14px] bg-accent px-4 text-white">
        <span class="text-base font-bold">가입 승인 대기 {{ data.pending_signups }}명</span>
        <span class="text-sm">승인하기</span>
      </a>
      <section aria-labelledby="bal" class="flex flex-col gap-1.5 rounded-2xl border border-line bg-surface p-[18px]">
        <h2 id="bal" class="text-[13px] font-bold text-brand">장부 잔액</h2>
        <span class="text-[30px] font-semibold tabular-nums">{{ won(data.balance) }}</span>
        <span class="text-[13px] leading-relaxed text-muted">모임통장 잔액과 같으면 하루 마감 끝이에요. 다르면 빠진 거래를 장부에 넣어 주세요.</span>
      </section>

      <section aria-labelledby="todo" class="flex flex-col gap-2">
        <h2 id="todo" class="mb-0.5 text-[13px] font-bold text-brand">확인할 것</h2>
        <div class="flex flex-col rounded-[14px] border border-line-soft bg-surface">
          <RouterLink v-for="r in [
              { to: '/dashboard#unpaid-dues', label: '회비 미납', n: `${data.unpaid_dues.length}명`, on: data.unpaid_dues.length },
              { to: '/dashboard#unpaid-fees', label: '참가비 미납', n: `${data.unpaid_event_fees.length}건`, on: data.unpaid_event_fees.length },
              { to: '/dashboard#refunds', label: '환불할 것', n: `${data.refunds_needed.length}건`, on: data.refunds_needed.length },
            ]" :key="r.to" :to="r.to"
            class="grid min-h-[60px] grid-cols-[minmax(0,1fr)_auto_18px] items-center gap-2.5 border-b border-line-soft pr-3.5 pl-4 text-ink">
            <span class="text-base">{{ r.label }}</span>
            <span class="text-[15px] font-bold" :class="r.on ? 'text-warn' : 'text-muted'">{{ r.n }}</span>
            <Chevron />
          </RouterLink>
          <RouterLink to="/dashboard" class="flex min-h-[52px] items-center justify-center text-[15px] font-medium">운영 대시보드 전체 보기</RouterLink>
        </div>
      </section>
    </template>

    <section aria-labelledby="admin" class="flex flex-col gap-2">
      <h2 id="admin" class="mb-0.5 text-[13px] font-bold text-brand">관리자 화면에서 하기</h2>
      <div class="grid grid-cols-2 gap-2">
        <a v-for="(l, i) in admin" :key="l.href" :href="l.href"
          class="flex min-h-[68px] flex-col justify-center gap-0.5 rounded-xl px-3.5"
          :class="i === 0 ? 'bg-accent text-white' : 'border border-line bg-surface text-ink'">
          <span class="text-[15px] font-bold">{{ l.title }}</span>
          <span class="text-xs" :class="i === 0 ? 'text-white' : 'text-muted'">{{ l.sub }}</span>
        </a>
      </div>
    </section>
  </div>
</template>
