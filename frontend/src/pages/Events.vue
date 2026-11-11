<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import StatusBadge from '../components/StatusBadge.vue'
import { attendanceMark, dayNum, headcount, month as monthLabel, monthHeading, over, shortDate, thisMonth, time, weekday } from '../format'
import type { EventSummary } from '../types'

// 위: 다가오는 모임
const events = ref<EventSummary[]>([])
const loading = ref(true)
const error = ref('')

api<EventSummary[]>('/api/events')
  .then((list) => (events.value = list))
  .catch((e: Error) => (error.value = e.message))
  .finally(() => (loading.value = false))

// 달별로 묶는다 (목록은 이미 시간순)
const groups = computed(() => {
  const out: { month: string; items: EventSummary[] }[] = []
  for (const e of events.value) {
    const m = monthHeading(e.starts_at)
    if (out.at(-1)?.month !== m) out.push({ month: m, items: [] })
    out.at(-1)!.items.push(e)
  }
  return out
})

// 아래: 지난 모임 달력. 달마다 ?month=로 그 달만 받는다.
// 보던 달·고른 날은 주소(?month=YYYY-MM&day=YYYY-MM-DD)에 둔다. 상세에서 돌아와도 그대로다.
const route = useRoute()
const router = useRouter()
const now = thisMonth()
// 형식이 틀리거나 이번 달보다 뒤면 이번 달
const month = computed(() => {
  const m = route.query.month
  return typeof m === 'string' && /^\d{4}-(0[1-9]|1[0-2])$/.test(m) && m >= '1900-01' && m <= now ? m : now
})
const past = ref<EventSummary[]>([])
const pastLoading = ref(true)
const pastError = ref('')

// 주소만 바꾼다 (기록을 쌓지 않음). 이번 달이면 month를 생략한다.
const go = (m: string, day = '') =>
  router.replace({ query: { ...(m !== now && { month: m }), ...(day && { day }) } })

const shift = (n: number) => {
  const d = new Date(Date.UTC(+month.value.slice(0, 4), +month.value.slice(5, 7) - 1 + n, 1))
  go(d.toISOString().slice(0, 7))
}

watch(
  month,
  async (m, _, onCleanup) => {
    if (route.path !== '/events') return // 상세로 떠나는 중에 주소가 바뀌어도 다시 받지 않는다
    // 달을 빨리 넘기면 늦게 온 이전 달 응답은 버린다.
    let stale = false
    onCleanup(() => (stale = true))
    pastLoading.value = true
    pastError.value = ''
    try {
      const list = await api<EventSummary[]>(`/api/events?month=${m}`)
      if (!stale) past.value = list
    } catch (e) {
      if (!stale) pastError.value = (e as Error).message
    } finally {
      if (!stale) pastLoading.value = false
    }
  },
  { immediate: true },
)

// 서버가 서울 시각으로 보낸 starts_at의 앞 10자로 날짜를 묶는다.
const byDay = computed(() => {
  const map = new Map<string, EventSummary[]>()
  for (const e of past.value) {
    const k = e.starts_at.slice(0, 10)
    map.set(k, [...(map.get(k) ?? []), e])
  }
  return map
})

// 달력 칸: 1일 앞의 빈칸(null) + 날짜
const cells = computed(() => {
  const y = +month.value.slice(0, 4)
  const m = +month.value.slice(5, 7)
  const lead = new Date(Date.UTC(y, m - 1, 1)).getUTCDay()
  const days = new Date(Date.UTC(y, m, 0)).getUTCDate()
  return [
    ...Array<null>(lead).fill(null),
    ...Array.from({ length: days }, (_, i) => {
      const key = `${month.value}-${String(i + 1).padStart(2, '0')}`
      const list = byDay.value.get(key)
      return { day: i + 1, key, has: !!list, present: !!list?.some((e) => e.my_attendance === 'present') }
    }),
  ]
})

// 고른 날: 그 달이 아니거나 모임 없는 날이면 무시
const picked = computed(() => {
  const d = route.query.day
  return typeof d === 'string' && d.startsWith(`${month.value}-`) && byDay.value.has(d) ? d : ''
})
const pickedEvents = computed(() => byDay.value.get(picked.value) ?? [])
const pickedIso = computed(() => `${picked.value}T12:00:00+09:00`)

const markClass = { present: 'font-bold text-ok', absent: 'font-bold text-warn', unknown: 'text-muted' }
const h2 = 'text-[19px] font-semibold text-brand'
const navBtn = 'flex size-11 items-center justify-center rounded-xl text-ink disabled:opacity-30'
</script>

<template>
  <header class="flex shrink-0 flex-col border-b border-line-soft px-5 pt-3.5 pb-3 lg:px-column lg:pt-9">
    <h1 class="text-2xl font-semibold text-brand">모임</h1>
  </header>

  <div class="flex w-full mx-auto max-w-2xl flex-col gap-8 px-5 pt-4 pb-6 lg:px-10">
    <section aria-labelledby="upcoming-title">
      <h2 id="upcoming-title" :class="h2">다가오는 모임</h2>
      <p v-if="loading" class="mt-3 text-muted">불러오는 중…</p>
      <p v-else-if="error" role="alert" class="mt-3 text-warn">{{ error }}</p>
      <p v-else-if="!events.length" class="mt-3 text-[15px] text-muted">예정된 모임이 없어요.</p>
      <template v-else>
        <section v-for="g in groups" :key="g.month">
          <h3 class="mt-4 mb-1.5 text-[13px] font-bold text-brand">{{ g.month }}</h3>
          <RouterLink v-for="e in g.items" :key="e.id" :to="`/events/${e.id}`"
            class="grid min-h-[76px] grid-cols-[52px_minmax(0,1fr)_auto] items-center gap-3.5 border-b border-line-soft py-2.5 text-ink">
            <span class="flex h-[52px] flex-col items-center justify-center rounded-xl border border-line bg-surface">
              <span class="text-lg leading-none font-bold">{{ dayNum(e.starts_at) }}</span>
              <span class="text-xs text-muted">{{ weekday(e.starts_at) }}</span>
            </span>
            <span class="flex min-w-0 flex-col gap-[3px]">
              <span class="text-base font-medium">{{ e.title }}</span>
              <span class="text-[13px] text-muted">{{ time(e.starts_at) }} · {{ e.place }}</span>
            </span>
            <span class="flex flex-col items-end gap-1">
              <StatusBadge v-if="e.my_status" />
              <span class="text-[13px]" :class="over(e) ? 'text-warn' : 'text-ink-2'">{{ headcount(e) }}</span>
            </span>
          </RouterLink>
        </section>
      </template>
    </section>

    <section aria-labelledby="past-title" class="flex flex-col gap-3">
      <h2 id="past-title" :class="h2">지난 모임</h2>
      <div class="rounded-2xl border border-line bg-surface p-3">
        <div class="flex items-center justify-between">
          <button type="button" :class="navBtn" aria-label="이전 달" @click="shift(-1)">
            <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 6-6 6 6 6" /></svg>
          </button>
          <h3 class="text-base font-semibold" aria-live="polite">{{ monthLabel(month) }}</h3>
          <button type="button" :class="navBtn" aria-label="다음 달" :disabled="month >= now" @click="shift(1)">
            <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6" /></svg>
          </button>
        </div>
        <div aria-hidden="true" class="mt-1 grid grid-cols-7 text-center text-xs text-muted">
          <span v-for="w in '일월화수목금토'" :key="w" class="py-1">{{ w }}</span>
        </div>
        <div class="grid grid-cols-7 text-center text-[15px] tabular-nums" :class="pastLoading && 'opacity-45'">
          <template v-for="(c, i) in cells" :key="c?.key ?? `lead-${i}`">
            <span v-if="!c" />
            <button v-else-if="c.has" type="button" :aria-pressed="picked === c.key"
              :aria-label="`${c.day}일, ${c.present ? '출석한 날' : '모임이 있던 날'}`"
              class="flex h-11 items-center justify-center rounded-xl" :class="picked === c.key && 'bg-accent-soft'"
              @click="go(month, picked === c.key ? '' : c.key)">
              <span class="flex size-9 items-center justify-center rounded-full border-2 border-accent"
                :class="c.present ? 'bg-accent font-bold text-white' : 'font-semibold text-accent-ink'">{{ c.day }}</span>
            </button>
            <span v-else class="flex h-11 items-center justify-center text-ink-2">{{ c.day }}</span>
          </template>
        </div>
        <ul class="mt-2 flex flex-wrap gap-x-4 gap-y-1 border-t border-line-soft px-1 pt-2.5 text-[13px] text-ink-2">
          <li class="flex items-center gap-1.5"><span aria-hidden="true" class="size-3.5 rounded-full border-2 border-accent" />모임이 있던 날</li>
          <li class="flex items-center gap-1.5"><span aria-hidden="true" class="size-3.5 rounded-full border-2 border-accent bg-accent" />출석한 날</li>
        </ul>
      </div>

      <p v-if="pastError" role="alert" class="text-warn">{{ pastError }}</p>
      <p v-else-if="pastLoading" class="text-muted">불러오는 중…</p>
      <p v-else-if="!past.length" class="text-[15px] text-muted">이 달에는 지난 모임이 없어요.</p>
      <p v-else-if="!picked" class="text-[15px] text-muted">표시된 날짜를 누르면 그날 모임을 볼 수 있어요.</p>
      <div v-else>
        <h3 class="mb-1 text-[13px] font-bold text-brand">{{ shortDate(pickedIso) }} {{ weekday(pickedIso) }}</h3>
        <div class="flex flex-col border-t border-line">
          <RouterLink v-for="e in pickedEvents" :key="e.id" :to="`/events/${e.id}`"
            class="flex min-h-[60px] items-center justify-between gap-3 border-b border-line-soft px-1 py-2 text-ink">
            <span class="flex min-w-0 flex-col gap-0.5">
              <span class="text-[15px] font-medium">{{ e.title }}</span>
              <span class="text-[13px] text-muted">{{ time(e.starts_at) }} · {{ e.place }}</span>
            </span>
            <span v-if="e.my_attendance" class="shrink-0 text-[13px]" :class="markClass[e.my_attendance]">{{ attendanceMark[e.my_attendance] }}</span>
            <span v-else class="shrink-0 text-[13px] text-muted">신청 안 함</span>
          </RouterLink>
        </div>
      </div>
    </section>
  </div>
</template>
