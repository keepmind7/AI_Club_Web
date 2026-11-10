<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import Chevron from '../components/Chevron.vue'
import { ago, shortDate } from '../format'
import type { Announcement, PostSummary } from '../types'

const route = useRoute()
const router = useRouter()
// 탭은 주소에 둔다: /news(?tab=board) 게시판, /news?tab=notice 공지
const notice = computed(() => route.query.tab === 'notice')
const notices = ref<Announcement[]>([])
const posts = ref<PostSummary[]>([])
const loading = ref(true)
const error = ref('')

// 공지 탭에 개수를 보여 주려고 두 목록을 함께 받는다.
Promise.all([api<Announcement[]>('/api/announcements'), api<PostSummary[]>('/api/posts')])
  .then(([a, p]) => {
    notices.value = a
    posts.value = p
  })
  .catch((e: Error) => (error.value = e.message))
  .finally(() => (loading.value = false))

const tab = (on: boolean) =>
  `min-h-10 rounded-[9px] text-[15px] ${on ? 'bg-surface font-bold text-ink shadow-[0_1px_2px_rgba(20,20,19,0.12)]' : 'font-medium text-muted'}`
</script>

<template>
  <header class="flex shrink-0 flex-col gap-3 border-b border-line-soft px-5 pt-3.5 pb-3 lg:px-column lg:pt-9">
    <div class="flex max-w-[37rem] items-center justify-between">
      <h1 class="text-2xl font-semibold text-brand">소식</h1>
      <RouterLink v-if="!notice" to="/board/new"
        class="flex min-h-11 items-center gap-1.5 rounded-full bg-accent px-4 text-[15px] font-bold text-white">
        <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 5v14M5 12h14" /></svg>
        <span>글쓰기</span>
      </RouterLink>
    </div>
    <div role="group" aria-label="소식 구분" class="grid max-w-[37rem] grid-cols-2 rounded-xl bg-sunk p-1">
      <button type="button" :aria-pressed="notice" :class="tab(notice)" @click="router.replace({ query: { tab: 'notice' } })">
        공지 <span v-if="notices.length" class="text-xs">{{ notices.length }}</span>
      </button>
      <button type="button" :aria-pressed="!notice" :class="tab(!notice)" @click="router.replace({ query: { tab: 'board' } })">게시판</button>
    </div>
  </header>

  <div class="w-full mx-auto max-w-2xl px-5 pt-1 pb-6 lg:px-10">
    <p v-if="loading" class="mt-4 text-muted">불러오는 중…</p>
    <p v-else-if="error" role="alert" class="mt-4 text-warn">{{ error }}</p>
    <template v-else-if="notice">
      <p v-if="!notices.length" class="mt-4 text-[15px] text-muted">아직 공지가 없어요.</p>
      <ul v-else>
        <li v-for="(n, i) in notices" :key="n.id" class="border-b border-line-soft">
          <details :open="i === 0" class="group py-3.5">
            <summary class="flex min-h-11 list-none items-center gap-3">
              <span class="flex min-w-0 flex-1 flex-col gap-1">
                <span class="text-base font-medium break-words group-open:font-bold">{{ n.title }}</span>
                <span class="text-[13px] text-muted">운영진 · {{ shortDate(n.created_at) }}</span>
              </span>
              <Chevron class="transition-transform group-open:rotate-90 motion-reduce:transition-none" />
            </summary>
            <p class="mt-2.5 text-[15px] leading-[1.7] whitespace-pre-line break-words text-ink-2">{{ n.body }}</p>
          </details>
        </li>
      </ul>
    </template>
    <template v-else>
      <p v-if="!posts.length" class="mt-4 text-[15px] text-muted">아직 글이 없어요. 첫 글을 써 보세요.</p>
      <ul v-else>
        <li v-for="p in posts" :key="p.id" class="border-b border-line-soft">
          <RouterLink :to="`/board/${p.id}`" class="flex flex-col gap-1 py-3.5 text-ink">
            <span class="text-base font-medium break-words">{{ p.title }}</span>
            <span v-if="p.excerpt" class="line-clamp-2 text-sm leading-normal break-words text-ink-2">{{ p.excerpt }}</span>
            <span class="text-[13px] text-muted">{{ p.author }} · {{ ago(p.created_at) }}<template v-if="p.comment_count"> · 댓글 {{ p.comment_count }}</template></span>
          </RouterLink>
        </li>
      </ul>
    </template>
  </div>
</template>
