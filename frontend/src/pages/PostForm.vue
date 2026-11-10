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
      if (!p.can_edit) throw new Error('작성자만 수정할 수 있어요.')
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
  <form class="flex flex-1 flex-col" @submit.prevent="submit">
    <header class="h-14 shrink-0 border-b border-line-soft">
      <div class="grid h-full mx-auto max-w-2xl grid-cols-[80px_minmax(0,1fr)_80px] items-center pr-5 pl-2 lg:pr-10 lg:pl-8">
        <RouterLink :to="id ? `/board/${id}` : '/news?tab=board'" class="flex min-h-11 items-center px-2 text-[15px] text-ink-2">취소</RouterLink>
        <h1 class="text-center text-[17px] font-bold text-brand">{{ id ? '글 수정' : '글쓰기' }}</h1>
        <button v-if="ready" type="submit" :disabled="busy || !title.trim() || !body.trim()"
          class="min-h-11 justify-self-end rounded-full bg-accent px-4 text-[15px] font-bold text-white disabled:cursor-not-allowed disabled:opacity-45">
          {{ busy ? '저장 중…' : id ? '저장' : '등록' }}
        </button>
      </div>
    </header>

    <p v-if="loading" class="px-5 py-5 text-muted lg:px-10">불러오는 중…</p>
    <template v-else-if="ready">
      <div class="flex w-full mx-auto max-w-2xl flex-1 flex-col px-5 pt-2 pb-4 lg:px-10">
        <p v-if="error" role="alert" class="mt-2 text-sm text-warn">{{ error }}</p>
        <label for="title" class="sr-only">제목</label>
        <input id="title" v-model="title" required maxlength="100" placeholder="제목" autocomplete="off"
          class="min-h-14 border-b border-line bg-transparent text-[21px] font-semibold placeholder:text-muted focus:border-accent focus-visible:outline-offset-0" />
        <label for="body" class="sr-only">본문</label>
        <textarea id="body" v-model="body" required maxlength="5000" placeholder="동아리 사람들과 나누고 싶은 이야기를 적어 주세요."
          class="mt-3.5 min-h-[50dvh] flex-1 resize-none bg-transparent text-base leading-[1.75] placeholder:text-muted focus-visible:outline-offset-0"></textarea>
      </div>
      <footer class="sticky bottom-0 border-t border-line-soft bg-bg px-5 pt-3 pb-[max(22px,env(safe-area-inset-bottom))] text-[13px] text-muted lg:px-0 lg:pb-4">
        <div class="flex mx-auto max-w-2xl items-center justify-between gap-3 lg:px-10">
          <span>사진은 올릴 수 없어요. 링크는 글에서 눌러 열 수 있어요.</span>
          <span class="shrink-0 tabular-nums">{{ body.length }} / 5000</span>
        </div>
      </footer>
    </template>
    <p v-else role="alert" class="px-5 py-5 text-warn lg:px-10">{{ error }}</p>
  </form>
</template>
