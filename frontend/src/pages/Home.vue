<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '../api'
import { useAuth } from '../auth'
import { dateTime, regStatus } from '../format'
import type { Announcement, EventSummary, PostSummary } from '../types'

const auth = useAuth()
const events = ref<EventSummary[]>([])
const notices = ref<Announcement[]>([])
const posts = ref<PostSummary[]>([])
const loading = ref(true)
const error = ref('')

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
</script>

<template>
  <h1 class="mb-4 text-xl font-bold">{{ auth.user?.name }}님, 안녕하세요</h1>
  <p v-if="loading">불러오는 중…</p>
  <p v-else-if="error" role="alert" class="text-red-700">{{ error }}</p>
  <div v-else class="space-y-6">
    <section>
      <h2 class="mb-2 font-bold">최근 공지</h2>
      <p v-if="!notices.length" class="text-sm text-gray-600">공지가 없습니다.</p>
      <ul v-else class="divide-y divide-gray-200 rounded bg-white">
        <li v-for="n in notices.slice(0, 3)" :key="n.id">
          <RouterLink to="/announcements" class="flex min-h-11 items-center px-3">{{ n.title }}</RouterLink>
        </li>
      </ul>
    </section>

    <section>
      <h2 class="mb-2 font-bold">다가오는 모임</h2>
      <p v-if="!events.length" class="text-sm text-gray-600">예정된 모임이 없습니다.</p>
      <ul v-else class="divide-y divide-gray-200 rounded bg-white">
        <li v-for="e in events.slice(0, 3)" :key="e.id">
          <RouterLink :to="`/events/${e.id}`" class="block min-h-11 px-3 py-2">
            <span class="font-medium">{{ e.title }}</span>
            <span class="block text-sm text-gray-600">{{ dateTime(e.starts_at) }} · {{ e.place }}</span>
          </RouterLink>
        </li>
      </ul>
    </section>

    <section>
      <h2 class="mb-2 font-bold">내 신청 현황</h2>
      <p v-if="!mine.length" class="text-sm text-gray-600">신청한 모임이 없습니다.</p>
      <ul v-else class="divide-y divide-gray-200 rounded bg-white">
        <li v-for="e in mine" :key="e.id">
          <RouterLink :to="`/events/${e.id}`" class="flex min-h-11 items-center justify-between gap-2 px-3 py-2">
            <span>{{ e.title }} <span class="block text-sm text-gray-600">{{ dateTime(e.starts_at) }}</span></span>
            <span class="shrink-0 text-sm font-medium">{{ regStatus[e.my_status!] }}</span>
          </RouterLink>
        </li>
      </ul>
    </section>

    <section>
      <h2 class="mb-2 font-bold">게시판</h2>
      <p v-if="!posts.length" class="text-sm text-gray-600">아직 글이 없습니다.</p>
      <ul v-else class="divide-y divide-gray-200 rounded bg-white">
        <li v-for="p in posts.slice(0, 3)" :key="p.id">
          <RouterLink :to="`/board/${p.id}`" class="block min-h-11 px-3 py-2">
            <span class="font-medium">{{ p.title }}</span>
            <span v-if="p.comment_count" class="ml-1 text-sm text-blue-700">[{{ p.comment_count }}]</span>
            <span class="block text-sm text-gray-600">{{ p.author }} · {{ dateTime(p.created_at) }}</span>
          </RouterLink>
        </li>
      </ul>
      <RouterLink to="/board" class="mt-2 inline-flex min-h-11 items-center text-sm text-blue-700 underline">게시판 전체 보기</RouterLink>
    </section>
  </div>
</template>
