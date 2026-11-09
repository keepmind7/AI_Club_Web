<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import type { PostDetail } from '../types'

// id가 있으면 수정(/board/:id/edit), 없으면 새 글(/board/new)
const props = defineProps<{ id?: string }>()
const router = useRouter()
const title = ref('')
const body = ref('')
const loading = ref(!!props.id)
const ready = ref(!props.id) // 수정 권한이 확인된 뒤에만 폼을 보인다 (api 헬퍼는 403이면 로그인 화면으로 보낸다)
const error = ref('')
const busy = ref(false)

if (props.id) {
  api<PostDetail>(`/api/posts/${props.id}`)
    .then((p) => {
      if (!p.can_edit) throw new Error('작성자만 수정할 수 있습니다.')
      title.value = p.title
      body.value = p.body
      ready.value = true
    })
    .catch((e: Error) => (error.value = e.message))
    .finally(() => (loading.value = false))
}

async function submit() {
  busy.value = true
  error.value = ''
  try {
    const path = props.id ? `/api/posts/${props.id}/edit` : '/api/posts'
    const p = await api<PostDetail>(path, 'POST', { title: title.value, body: body.value })
    router.replace(`/board/${p.id}`)
  } catch (e) {
    error.value = (e as Error).message
    busy.value = false
  }
}
</script>

<template>
  <RouterLink :to="id ? `/board/${id}` : '/board'" class="mb-2 inline-flex min-h-11 items-center text-sm text-blue-700">← 돌아가기</RouterLink>
  <h1 class="mb-4 text-xl font-bold">{{ id ? '글 수정' : '글쓰기' }}</h1>
  <p v-if="loading">불러오는 중…</p>
  <form v-else-if="ready" class="space-y-4" @submit.prevent="submit">
    <div>
      <label for="title" class="mb-1 block text-sm font-medium">제목</label>
      <input id="title" v-model="title" required maxlength="100"
        class="min-h-11 w-full rounded border border-gray-300 bg-white px-3" />
    </div>
    <div>
      <label for="body" class="mb-1 block text-sm font-medium">본문</label>
      <textarea id="body" v-model="body" required maxlength="5000" rows="10"
        class="w-full rounded border border-gray-300 bg-white p-3"></textarea>
      <p class="text-right text-xs text-gray-600">{{ body.length }}/5000</p>
    </div>
    <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
    <button type="submit" :disabled="busy" class="min-h-11 w-full rounded bg-blue-700 font-medium text-white disabled:opacity-50">
      {{ busy ? '저장 중…' : '저장' }}
    </button>
  </form>
  <p v-else role="alert" class="text-red-700">{{ error }}</p>
</template>
