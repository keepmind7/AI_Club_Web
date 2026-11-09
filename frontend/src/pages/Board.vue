<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'
import { dateTime } from '../format'
import type { PostSummary } from '../types'

const posts = ref<PostSummary[]>([])
const loading = ref(true)
const error = ref('')

api<PostSummary[]>('/api/posts')
  .then((d) => (posts.value = d))
  .catch((e: Error) => (error.value = e.message))
  .finally(() => (loading.value = false))
</script>

<template>
  <div class="mb-4 flex items-center justify-between">
    <h1 class="text-xl font-bold">게시판</h1>
    <RouterLink to="/board/new" class="flex min-h-11 items-center rounded bg-blue-700 px-4 font-medium text-white">글쓰기</RouterLink>
  </div>
  <p v-if="loading">불러오는 중…</p>
  <p v-else-if="error" role="alert" class="text-red-700">{{ error }}</p>
  <p v-else-if="!posts.length" class="text-sm text-gray-600">아직 글이 없습니다. 첫 글을 써 보세요.</p>
  <ul v-else class="divide-y divide-gray-200 rounded bg-white">
    <li v-for="p in posts" :key="p.id">
      <RouterLink :to="`/board/${p.id}`" class="block min-h-11 px-3 py-2">
        <span class="font-medium">{{ p.title }}</span>
        <span v-if="p.comment_count" class="ml-1 text-sm text-blue-700">[{{ p.comment_count }}]</span>
        <span class="block text-sm text-gray-600">{{ p.author }} · {{ dateTime(p.created_at) }}</span>
      </RouterLink>
    </li>
  </ul>
</template>
