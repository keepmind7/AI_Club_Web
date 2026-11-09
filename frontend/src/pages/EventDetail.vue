<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '../api'
import { useAuth } from '../auth'
import BackHeader from '../components/BackHeader.vue'
import BottomSheet from '../components/BottomSheet.vue'
import { cancelNote, dateTime, dDay, headcount, isFull, seats, waitNote } from '../format'
import type { EventDetail } from '../types'

const props = defineProps<{ id: string }>()
const me = useAuth().user?.name
const ev = ref<EventDetail | null>(null)
const loading = ref(true)
const error = ref('')
const actionError = ref('')
const busy = ref(false)
const sheet = ref(false)

const started = computed(() => !!ev.value && new Date(ev.value.starts_at) <= new Date())

api<EventDetail>(`/api/events/${props.id}`)
  .then((d) => (ev.value = d))
  .catch((e: Error) => (error.value = e.message))
  .finally(() => (loading.value = false))

async function act(action: 'register' | 'cancel') {
  busy.value = true
  actionError.value = ''
  try {
    // 응답으로 받은 상세로 바로 바꾼다 (다시 불러오지 않음)
    ev.value = await api<EventDetail>(`/api/events/${props.id}/${action}`, 'POST')
  } catch (e) {
    actionError.value = (e as Error).message
  } finally {
    busy.value = false
    sheet.value = false
  }
}
</script>

<template>
  <BackHeader to="/events" label="모임" />
  <p v-if="loading" class="px-5 py-5 text-muted lg:px-10">불러오는 중…</p>
  <p v-else-if="error" role="alert" class="px-5 py-5 text-warn lg:px-10">{{ error }}</p>
  <template v-else-if="ev">
    <article class="flex w-full max-w-2xl flex-1 flex-col gap-[22px] px-5 pt-5 pb-6 lg:px-10 lg:pt-8">
      <div class="flex flex-col gap-1.5">
        <span class="text-[13px] font-bold" :class="started ? 'text-muted' : 'text-accent-ink'">{{ started ? '지난 모임' : dDay(ev.starts_at) }}</span>
        <h1 class="text-[27px] leading-tight font-semibold text-brand break-words">{{ ev.title }}</h1>
      </div>

      <dl class="grid grid-cols-[56px_minmax(0,1fr)] gap-x-3 gap-y-2.5 rounded-[14px] border border-line-soft bg-surface p-4 text-[15px]">
        <dt class="text-muted">일시</dt><dd>{{ dateTime(ev.starts_at) }}</dd>
        <dt class="text-muted">장소</dt><dd>{{ ev.place }}</dd>
        <dt class="text-muted">인원</dt><dd>{{ headcount(ev) }}</dd>
      </dl>

      <p v-if="ev.description" class="text-[15px] leading-[1.75] whitespace-pre-line break-words text-ink-2">{{ ev.description }}</p>

      <section aria-labelledby="who" class="flex flex-col gap-2.5">
        <h2 id="who" class="text-[15px] font-bold text-brand">신청자 <span class="font-normal text-muted">{{ ev.attendees.length }}명</span></h2>
        <p v-if="!ev.attendees.length" class="text-sm text-muted">아직 신청한 사람이 없어요.</p>
        <ul v-else class="flex flex-wrap gap-1.5">
          <li v-for="(a, i) in ev.attendees" :key="i" class="rounded-full px-3 py-1.5 text-sm"
            :class="a.name === me && a.status === ev.my_status ? (a.status === 'confirmed' ? 'bg-ok-soft font-bold text-ok' : 'bg-warn-soft font-bold text-warn')
              : a.status === 'waitlisted' ? 'border border-dashed border-field bg-surface text-ink-2' : 'border border-line-soft bg-surface'">
            {{ a.name }}<template v-if="a.status === 'waitlisted'"> · 대기</template>
          </li>
        </ul>
      </section>
    </article>

    <!-- 하단 고정 신청 바. 참가비 금액은 보여 주지 않는다 (사용자 요구). -->
    <div class="sticky bottom-0 z-10 border-t border-line bg-surface px-5 pt-3 pb-[max(24px,env(safe-area-inset-bottom))] lg:px-0 lg:pb-5">
      <div class="flex max-w-2xl flex-col gap-2 lg:px-10" aria-live="polite">
        <p v-if="actionError" role="alert" class="text-sm text-warn">{{ actionError }}</p>
        <p v-if="started" class="flex min-h-12 items-center text-[15px] text-muted">이미 시작한 모임이라 신청·취소할 수 없어요.</p>
        <div v-else-if="!ev.my_status" class="flex items-center gap-3.5">
          <span class="flex flex-1 flex-col gap-px">
            <span class="text-base font-bold">{{ seats(ev) }}</span>
            <span v-if="isFull(ev)" class="text-[13px] text-muted">지금 신청하면 대기 {{ ev.waitlist_count + 1 }}번이에요. {{ waitNote }}</span>
          </span>
          <button type="button" :disabled="busy" @click="act('register')"
            class="min-h-[52px] shrink-0 rounded-xl bg-accent px-7 text-base font-bold text-white disabled:opacity-45">
            {{ busy ? '신청 중…' : isFull(ev) ? '대기 신청' : '참석 신청' }}
          </button>
        </div>
        <div v-else class="flex items-center gap-3.5">
          <span class="flex flex-1 flex-col gap-px">
            <template v-if="ev.my_status === 'confirmed'">
              <span class="text-base font-bold text-ok">참석 확정</span>
              <span v-if="ev.fee" class="text-[13px] text-muted">참가비는 모임 전까지 모임통장으로 입금해 주세요.</span>
            </template>
            <template v-else>
              <span class="text-base font-bold text-warn">대기 {{ ev.my_waitlist_position }}번</span>
              <span class="text-[13px] text-muted">{{ waitNote }}</span>
            </template>
          </span>
          <button type="button" @click="sheet = true"
            class="min-h-12 shrink-0 rounded-xl border border-field bg-surface px-[18px] text-[15px] font-medium">신청 취소</button>
        </div>
      </div>
    </div>

    <BottomSheet v-if="sheet" title="신청을 취소할까요?" action="취소하기" :busy="busy" @close="sheet = false" @confirm="act('cancel')">
      {{ cancelNote(ev) }}
    </BottomSheet>
  </template>
</template>
