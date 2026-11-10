<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '../api'
import BottomSheet from '../components/BottomSheet.vue'
import Chevron from '../components/Chevron.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { ago, dateTime, dDay, headcount, over, today } from '../format'
import type { Announcement, EventDetail, EventSummary, PostSummary } from '../types'

const events = ref<EventSummary[]>([])
const notices = ref<Announcement[]>([])
const posts = ref<PostSummary[]>([])
const loading = ref(true)
const error = ref('')
const busy = ref(false)
const actionError = ref('')
const sheet = ref(false)

const next = computed(() => events.value[0])
const mine = computed(() => events.value.filter((e) => e.my_status))

Promise.all([
  api<EventSummary[]>('/api/events'),
  api<Announcement[]>('/api/announcements'),
  api<PostSummary[]>('/api/posts'), // ponytail: 최근 3개만 쓰지만 계약에 개수 제한이 없어 전체를 받는다. 글이 많아지면 ?limit을 계약에 추가
])
  .then(([e, a, p]) => {
    events.value = e
    notices.value = a
    posts.value = p
  })
  .catch((e: Error) => (error.value = e.message))
  .finally(() => (loading.value = false))

async function act(action: 'register' | 'cancel') {
  busy.value = true
  actionError.value = ''
  try {
    events.value[0] = await api<EventDetail>(`/api/events/${next.value!.id}/${action}`, 'POST')
  } catch (e) {
    actionError.value = (e as Error).message
  } finally {
    busy.value = false
    sheet.value = false
  }
}

const h2 = 'text-[19px] font-semibold text-brand lg:text-xl'
const row = 'flex min-h-[60px] items-center justify-between gap-3 border-b border-line-soft px-1 py-2 text-ink'
</script>

<template>
  <header class="flex h-14 shrink-0 items-center justify-between border-b border-line-soft px-5 lg:hidden">
    <span class="text-[21px] font-semibold tracking-tight text-brand">Mythos</span>
    <span class="text-[13px] text-muted">{{ today() }}</span>
  </header>

  <div class="flex w-full mx-auto max-w-[1080px] flex-col gap-7 px-5 pt-4 pb-7 lg:px-10 lg:pt-9 lg:pb-12">
    <p v-if="loading" class="text-muted">불러오는 중…</p>
    <p v-else-if="error" role="alert" class="text-warn">{{ error }}</p>
    <template v-else>
      <RouterLink v-if="notices.length" to="/news?tab=notice"
        class="flex min-h-14 items-center gap-3 rounded-xl border border-line-soft bg-surface px-3.5 py-2.5 text-ink">
        <span class="shrink-0 rounded-md bg-accent-soft px-2 py-[3px] text-xs font-bold text-accent-ink">공지</span>
        <span class="flex min-w-0 flex-1 flex-col gap-0.5 lg:flex-row lg:items-center lg:justify-between lg:gap-3">
          <span class="truncate text-[15px] font-medium">{{ notices[0]!.title }}</span>
          <span class="shrink-0 text-xs text-muted lg:text-[13px]">
            {{ ago(notices[0]!.created_at) }}<template v-if="notices.length > 1"> · 공지 {{ notices.length - 1 }}개 더</template>
          </span>
        </span>
        <Chevron />
      </RouterLink>

      <div class="grid items-start gap-7 lg:grid-cols-2">
        <div class="flex flex-col gap-7">
          <section aria-labelledby="next-title" class="flex flex-col gap-3">
            <div class="flex items-baseline justify-between">
              <h2 id="next-title" :class="h2">다가오는 모임</h2>
              <RouterLink to="/events" class="flex min-h-11 items-center text-sm font-medium">전체 보기</RouterLink>
            </div>
            <p v-if="!next" class="text-[15px] text-muted">예정된 모임이 없어요.</p>
            <template v-else>
              <article class="flex flex-col gap-3.5 rounded-2xl border border-line bg-surface p-[18px] lg:p-[22px]">
                <div class="flex flex-col gap-1">
                  <span class="text-[13px] font-bold text-accent-ink">{{ dDay(next.starts_at) }}</span>
                  <RouterLink :to="`/events/${next.id}`" class="text-[22px] leading-snug font-semibold text-ink lg:text-2xl">{{ next.title }}</RouterLink>
                </div>
                <dl class="grid grid-cols-[44px_minmax(0,1fr)] gap-x-2.5 gap-y-1.5 text-[15px]">
                  <dt class="text-muted">일시</dt><dd>{{ dateTime(next.starts_at) }}</dd>
                  <dt class="text-muted">장소</dt><dd>{{ next.place }}</dd>
                  <dt class="text-muted">인원</dt>
                  <dd :class="{ 'text-warn': over(next) }">{{ headcount(next) }}</dd>
                </dl>
                <div aria-live="polite">
                  <button v-if="!next.my_status" type="button" :disabled="busy" @click="act('register')"
                    class="min-h-12 w-full rounded-xl bg-accent text-base font-bold text-white disabled:opacity-45 lg:w-auto lg:px-7">
                    {{ busy ? '신청 중…' : '참석 신청' }}
                  </button>
                  <div v-else class="flex min-h-12 items-center justify-between gap-3 rounded-xl bg-ok-soft pr-1.5 pl-3.5 text-ok">
                    <span class="text-[15px] font-bold">신청했어요</span>
                    <button type="button" class="min-h-11 px-3 text-sm text-ink-2 underline" @click="sheet = true">신청 취소</button>
                  </div>
                  <p v-if="actionError" role="alert" class="mt-2 text-sm text-warn">{{ actionError }}</p>
                </div>
              </article>

              <RouterLink v-for="e in events.slice(1, 3)" :key="e.id" :to="`/events/${e.id}`" :class="row">
                <span class="flex min-w-0 flex-col gap-0.5">
                  <span class="text-[15px] font-medium">{{ e.title }}</span>
                  <span class="text-[13px] text-muted">{{ dateTime(e.starts_at) }} · {{ e.place }}</span>
                </span>
                <span class="flex shrink-0 flex-col items-end gap-1">
                  <StatusBadge v-if="e.my_status" />
                  <span class="text-[13px]" :class="over(e) ? 'text-warn' : 'text-muted'">{{ headcount(e) }}</span>
                </span>
              </RouterLink>
            </template>
          </section>

          <section aria-labelledby="mine-title" class="flex flex-col gap-2">
            <h2 id="mine-title" :class="h2">내 신청</h2>
            <p v-if="!mine.length" class="text-[15px] text-muted">신청한 모임이 없어요.</p>
            <div v-else class="flex flex-col border-t border-line">
              <RouterLink v-for="e in mine" :key="e.id" :to="`/events/${e.id}`" :class="row">
                <span class="flex min-w-0 flex-col gap-0.5">
                  <span class="text-[15px] font-medium">{{ e.title }}</span>
                  <span class="text-[13px] text-muted">{{ dateTime(e.starts_at) }}</span>
                </span>
                <StatusBadge />
              </RouterLink>
            </div>
          </section>
        </div>

        <section aria-labelledby="board-title" class="flex flex-col gap-2">
          <div class="flex items-baseline justify-between lg:items-center">
            <h2 id="board-title" :class="h2">게시판</h2>
            <RouterLink to="/news?tab=board" class="flex min-h-11 items-center text-sm font-medium lg:hidden">전체 보기</RouterLink>
            <RouterLink to="/board/new" class="hidden min-h-10 items-center rounded-full border border-field px-3.5 text-sm font-medium text-ink lg:flex">글쓰기</RouterLink>
          </div>
          <p v-if="!posts.length" class="text-[15px] text-muted">아직 글이 없어요.</p>
          <div v-else class="flex flex-col border-t border-line">
            <RouterLink v-for="p in posts.slice(0, 3)" :key="p.id" :to="`/board/${p.id}`"
              class="flex min-h-[60px] flex-col justify-center gap-[3px] border-b border-line-soft px-1 py-2 text-ink lg:py-3.5">
              <span class="text-[15px] font-medium lg:text-base">{{ p.title }}</span>
              <span v-if="p.excerpt" class="hidden text-sm leading-normal text-ink-2 lg:line-clamp-2">{{ p.excerpt }}</span>
              <span class="text-[13px] text-muted">{{ p.author }} · {{ ago(p.created_at) }}<template v-if="p.comment_count"> · 댓글 {{ p.comment_count }}</template></span>
            </RouterLink>
            <RouterLink to="/news?tab=board" class="hidden min-h-12 items-center px-1 text-sm font-medium lg:flex">게시판 전체 보기</RouterLink>
          </div>
        </section>
      </div>
    </template>
  </div>

  <BottomSheet v-if="sheet && next" title="신청을 취소할까요?" action="취소하기" :busy="busy" @close="sheet = false" @confirm="act('cancel')">
    다시 신청할 수 있어요.
  </BottomSheet>
</template>
