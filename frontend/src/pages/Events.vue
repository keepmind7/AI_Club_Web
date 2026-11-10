<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import StatusBadge from '../components/StatusBadge.vue'
import { attendanceMark, dayNum, monthHeading, regStatus, seats, time, weekday } from '../format'
import type { AttendanceMark, EventSummary, MyAttendance } from '../types'

const route = useRoute()
const router = useRouter()
// 탭은 주소(?past=1)에 둔다. 상세에서 뒤로 오면 보던 탭이 그대로다.
const past = computed(() => route.query.past === '1')
const events = ref<EventSummary[]>([])
const marks = ref(new Map<number, AttendanceMark>())
const loading = ref(true)
const error = ref('')

watch(
  past,
  async (isPast, _, onCleanup) => {
    if (route.path !== '/events') return // 상세로 떠나는 중에 주소가 바뀌어도 다시 받지 않는다
    // 탭을 다시 바꾸면 이전 요청의 응답은 버린다.
    let stale = false
    onCleanup(() => (stale = true))
    loading.value = true
    error.value = ''
    try {
      const [list, att] = await Promise.all([
        api<EventSummary[]>(isPast ? '/api/events?past=1' : '/api/events'),
        isPast ? api<MyAttendance>('/api/me/attendance') : null, // 지난 모임 옆에 내 출석 표시
      ])
      if (stale) return
      events.value = list
      if (att) marks.value = new Map(att.records.map((r) => [r.event_id, r.attendance]))
    } catch (e) {
      if (!stale) error.value = (e as Error).message
    } finally {
      if (!stale) loading.value = false
    }
  },
  { immediate: true },
)

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

const tab = (on: boolean) =>
  `min-h-10 rounded-[9px] text-[15px] ${on ? 'bg-surface font-bold text-ink shadow-[0_1px_2px_rgba(20,20,19,0.12)]' : 'font-medium text-muted'}`
const markClass = { present: 'font-bold text-ok', absent: 'font-bold text-warn', unknown: 'text-muted' }
</script>

<template>
  <header class="flex shrink-0 flex-col gap-3 border-b border-line-soft px-5 pt-3.5 pb-3 lg:px-column lg:pt-9">
    <h1 class="text-2xl font-semibold text-brand">모임</h1>
    <div role="group" aria-label="모임 구분" class="grid max-w-[37rem] grid-cols-2 rounded-xl bg-sunk p-1">
      <button type="button" :aria-pressed="!past" :class="tab(!past)" @click="router.replace({ query: {} })">다가오는 모임</button>
      <button type="button" :aria-pressed="past" :class="tab(past)" @click="router.replace({ query: { past: '1' } })">지난 모임</button>
    </div>
  </header>

  <div class="flex w-full mx-auto max-w-2xl flex-col px-5 pt-2 pb-6 lg:px-10">
    <p v-if="loading" class="mt-4 text-muted">불러오는 중…</p>
    <p v-else-if="error" role="alert" class="mt-4 text-warn">{{ error }}</p>
    <p v-else-if="!events.length" class="mt-4 text-[15px] text-muted">{{ past ? '지난 모임이 없어요.' : '예정된 모임이 없어요.' }}</p>
    <template v-else>
      <section v-for="g in groups" :key="g.month">
        <h2 class="mt-4 mb-1.5 text-[13px] font-bold text-brand">{{ g.month }}</h2>
        <RouterLink v-for="e in g.items" :key="e.id" :to="`/events/${e.id}`"
          class="grid min-h-[76px] grid-cols-[52px_minmax(0,1fr)_auto] items-center gap-3.5 border-b border-line-soft py-2.5 text-ink">
          <span class="flex h-[52px] flex-col items-center justify-center rounded-xl" :class="past ? 'bg-sunk' : 'border border-line bg-surface'">
            <span class="text-lg leading-none font-bold">{{ dayNum(e.starts_at) }}</span>
            <span class="text-xs text-muted">{{ weekday(e.starts_at) }}</span>
          </span>
          <span class="flex min-w-0 flex-col gap-[3px]">
            <span class="text-base font-medium">{{ e.title }}</span>
            <span class="text-[13px] text-muted">{{ past ? `${e.place} · 확정 ${e.confirmed_count}명` : `${time(e.starts_at)} · ${e.place}` }}</span>
          </span>
          <template v-if="past">
            <span v-if="marks.get(e.id)" class="text-[13px]" :class="markClass[marks.get(e.id)!]">{{ attendanceMark[marks.get(e.id)!] }}</span>
            <span v-else class="text-[13px] text-muted">{{ e.my_status ? regStatus[e.my_status] : '신청 안 함' }}</span>
          </template>
          <StatusBadge v-else-if="e.my_status" :status="e.my_status" :position="e.my_waitlist_position" />
          <span v-else class="text-[13px] text-ink-2">{{ seats(e) }}</span>
        </RouterLink>
      </section>
      <p v-if="!past" class="mt-5 text-[13px] leading-relaxed text-muted">대기 n번은 자리가 나면 순서대로 확정돼요.</p>
    </template>
  </div>
</template>
