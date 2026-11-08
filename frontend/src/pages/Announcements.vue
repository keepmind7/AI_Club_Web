<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'
import { date } from '../format'
import type { Announcement } from '../types'

const items = ref<Announcement[] | null>(null)
const error = ref('')

api<Announcement[]>('/api/announcements')
  .then((d) => (items.value = d))
  .catch((e: Error) => (error.value = e.message))
</script>

<template>
  <h1 class="mb-4 text-xl font-bold">공지사항</h1>
  <p v-if="error" role="alert" class="text-red-700">{{ error }}</p>
  <p v-else-if="!items">불러오는 중…</p>
  <p v-else-if="!items.length" class="text-gray-600">공지가 없습니다.</p>
  <div v-else class="divide-y divide-gray-200 rounded bg-white">
    <details v-for="n in items" :key="n.id" class="px-3">
      <summary class="flex min-h-11 cursor-pointer items-center justify-between gap-2 py-2">
        <span class="font-medium">{{ n.title }}</span>
        <span class="shrink-0 text-sm text-gray-600">{{ date(n.created_at) }}</span>
      </summary>
      <p class="whitespace-pre-line pb-3">{{ n.body }}</p>
    </details>
  </div>
</template>
