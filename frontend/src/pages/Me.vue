<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useAuth } from '../auth'
import Chevron from '../components/Chevron.vue'
import { emailChunks, month, thisMonth, withParticle } from '../format'
import type { MyAttendance, MyPayments, SharedAccount } from '../types'

const auth = useAuth()
const user = auth.user!
const router = useRouter()
const att = ref<MyAttendance | null>(null)
const pay = ref<MyPayments | null>(null)
const shared = ref<SharedAccount[] | null>(null)
const error = ref('')
const busy = ref(false)

// 요약 줄에 쓸 숫자. 하나가 실패해도 메뉴는 그대로 쓸 수 있게 각자 받는다.
const load = <T,>(path: string, target: { value: T | null }) =>
  api<T>(path).then((d) => (target.value = d)).catch((e: Error) => (error.value = e.message))
load('/api/me/attendance', att)
load('/api/me/payments', pay)
load('/api/shared-accounts', shared)

// 납부 배지. 운영 대시보드처럼 회비 미납은 지난달까지만 센다(이번 달은 아직 납부 기간).
const payBadge = computed(() => {
  if (!pay.value) return null
  const now = thisMonth()
  const late = pay.value.dues.filter((d) => !d.paid && d.month < now).length
  const fees = pay.value.event_fees.filter((f) => !f.paid).length
  if (late) return { text: `회비 ${late}개월 미납`, cls: 'bg-warn-soft font-bold text-warn' }
  if (fees) return { text: `참가비 ${fees}건 미납`, cls: 'bg-warn-soft font-bold text-warn' }
  if (pay.value.dues.some((d) => !d.paid)) return { text: '이번 달 회비 납부 전', cls: 'text-muted' }
  if (pay.value.dues.length || pay.value.event_fees.length) return { text: '모두 냈어요', cls: 'bg-ok-soft font-bold text-ok' }
  return null
})
const others = (a: SharedAccount) => a.members.map((m) => m.name).filter((n) => n !== user.name)

async function logout() {
  busy.value = true
  error.value = ''
  try {
    await auth.logout()
    router.push('/login')
  } catch (e) {
    error.value = (e as Error).message
    busy.value = false
  }
}

const h2 = 'mb-0.5 text-[13px] font-bold text-brand'
const card = 'flex flex-col rounded-[14px] border border-line-soft bg-surface'
const row = 'grid min-h-[68px] grid-cols-[minmax(0,1fr)_auto_18px] items-center gap-2.5 pr-3.5 pl-4 text-ink'
</script>

<template>
  <header class="flex shrink-0 flex-col gap-1 border-b border-line-soft px-5 pt-[22px] pb-[18px] lg:px-10 lg:pt-9">
    <h1 class="text-[26px] font-semibold text-brand">{{ user.name }}</h1>
    <p class="text-sm text-muted">
      아이디 {{ user.username }}<template v-if="user.joined_on"> · {{ month(user.joined_on.slice(0, 7)) }} 가입</template><template v-if="user.is_staff"> · 운영진</template>
    </p>
  </header>

  <div class="flex w-full max-w-2xl flex-col gap-[26px] px-5 pt-[18px] pb-7 lg:px-10">
    <p v-if="error" role="alert" class="text-sm text-warn">{{ error }}</p>

    <section aria-labelledby="rec" class="flex flex-col gap-2">
      <h2 id="rec" :class="h2">내 기록</h2>
      <div :class="card">
        <RouterLink to="/attendance" :class="row" class="border-b border-line-soft">
          <span class="flex flex-col gap-0.5">
            <span class="text-base font-medium">출석</span>
            <span class="text-[13px] text-muted">{{ !att ? '불러오는 중…' : att.total ? `확정된 모임 ${att.total}번 중 ${att.present}번 출석` : '아직 출석 기록이 없어요' }}</span>
          </span>
          <span class="text-[17px] font-bold tabular-nums">{{ att?.rate == null ? '' : `${att.rate}%` }}</span>
          <Chevron />
        </RouterLink>
        <RouterLink to="/payments" :class="row">
          <span class="flex flex-col gap-0.5">
            <span class="text-base font-medium">납부</span>
            <span class="text-[13px] text-muted">회비 · 참가비 · 거래 내역</span>
          </span>
          <span v-if="payBadge" class="rounded-full px-2.5 py-1 text-[13px]" :class="payBadge.cls">{{ payBadge.text }}</span>
          <span v-else />
          <Chevron />
        </RouterLink>
      </div>
    </section>

    <section aria-labelledby="share" class="flex flex-col gap-2">
      <h2 id="share" :class="h2">공유 계정</h2>
      <RouterLink to="/shared-accounts"
        class="grid min-h-[72px] rounded-[14px] border border-line-soft bg-surface grid-cols-[minmax(0,1fr)_18px] items-center gap-2.5 py-2.5 pr-3.5 pl-4 text-ink">
        <span class="flex min-w-0 flex-col gap-[3px]">
          <template v-if="!shared"><span class="text-base font-medium">공유 계정</span></template>
          <template v-else-if="user.is_staff">
            <span class="text-base font-medium">전체 공유 계정</span>
            <span class="text-[13px] text-muted">{{ shared.length }}개 등록됨</span>
          </template>
          <template v-else-if="shared[0]">
            <span class="text-base font-medium break-words"><template v-for="(c, i) in emailChunks(shared[0].email)" :key="i">{{ c }}<wbr /></template></span>
            <span class="text-[13px] text-muted">{{ others(shared[0]).length ? `${withParticle(others(shared[0]).join(', '))} 함께 써요` : '혼자 써요' }}</span>
          </template>
          <template v-else>
            <span class="text-base font-medium">배정된 계정이 없어요</span>
            <span class="text-[13px] text-muted">필요하면 운영진에게 문의해 주세요</span>
          </template>
        </span>
        <Chevron />
      </RouterLink>
    </section>

    <section aria-labelledby="acct" class="flex flex-col gap-2">
      <h2 id="acct" :class="h2">계정</h2>
      <div :class="card">
        <RouterLink to="/password" class="grid min-h-14 grid-cols-[minmax(0,1fr)_18px] items-center gap-2.5 border-b border-line-soft pr-3.5 pl-4 text-base text-ink">
          <span>비밀번호 변경</span>
          <Chevron />
        </RouterLink>
        <div class="grid grid-cols-[64px_minmax(0,1fr)] gap-x-2.5 px-4 py-3.5 text-[15px]">
          <span class="text-muted">연락처</span><span>{{ user.phone || '등록 안 됨' }}</span>
        </div>
      </div>
      <p class="text-[13px] leading-relaxed text-muted">연락처가 바뀌면 운영진에게 문의해 주세요.</p>
    </section>

    <button type="button" :disabled="busy" class="min-h-11 self-start px-1 text-[15px] text-ink-2 underline disabled:opacity-45" @click="logout">
      {{ busy ? '로그아웃 중…' : '로그아웃' }}
    </button>
  </div>
</template>
