<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { dateTime } from '../format'
import type { Comment, PostDetail } from '../types'

const props = defineProps<{ id: string }>()
const router = useRouter()
const post = ref<PostDetail | null>(null)
const loading = ref(true)
const error = ref('')
const actionError = ref('')
const busy = ref(false)
const comment = ref('')

api<PostDetail>(`/api/posts/${props.id}`)
  .then((d) => (post.value = d))
  .catch((e: Error) => (error.value = e.message))
  .finally(() => (loading.value = false))

// 텍스트를 URL로 나눈다. 캡처 그룹으로 split하므로 홀수 번째가 링크다. v-html을 쓰지 않아 XSS가 없다.
// ponytail: 링크 바로 뒤에 붙은 문장부호(마침표, 괄호)도 링크에 포함된다. 문제가 되면 정규식에서 끝 문자를 제외한다.
const parts = (text: string) => text.split(/(https?:\/\/[^\s]+)/)

// auto_now_add와 auto_now가 따로 찍혀 생성 직후에도 몇 ms 차이가 날 수 있어 1초 넘게 차이 날 때만 수정으로 본다.
const edited = (p: PostDetail) => new Date(p.updated_at).getTime() - new Date(p.created_at).getTime() > 1000

async function run(fn: () => Promise<void>) {
  busy.value = true
  actionError.value = ''
  try {
    await fn()
  } catch (e) {
    actionError.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

function removePost() {
  if (!confirm('글을 삭제할까요? 댓글도 함께 삭제됩니다.')) return
  run(async () => {
    await api(`/api/posts/${props.id}/delete`, 'POST')
    router.replace('/board')
  })
}

function addComment() {
  run(async () => {
    post.value = await api<PostDetail>(`/api/posts/${props.id}/comments`, 'POST', { body: comment.value })
    comment.value = ''
  })
}

function removeComment(c: Comment) {
  if (!confirm('댓글을 삭제할까요?')) return
  run(async () => {
    await api(`/api/comments/${c.id}/delete`, 'POST')
    const p = post.value!
    p.comments = p.comments.filter((x) => x.id !== c.id)
    p.comment_count = p.comments.length
  })
}
</script>

<template>
  <RouterLink to="/board" class="mb-2 inline-flex min-h-11 items-center text-sm text-blue-700">← 게시판</RouterLink>
  <p v-if="loading">불러오는 중…</p>
  <p v-else-if="error" role="alert" class="text-red-700">{{ error }}</p>
  <article v-else-if="post" class="space-y-4">
    <header>
      <h1 class="text-xl font-bold break-words">{{ post.title }}</h1>
      <p class="text-sm text-gray-600">
        {{ post.author }} · {{ dateTime(post.created_at) }}<template v-if="edited(post)"> · 수정됨</template>
      </p>
    </header>

    <p class="whitespace-pre-wrap break-words rounded bg-white p-3"><template v-for="(t, i) in parts(post.body)" :key="i"><a v-if="i % 2" :href="t" target="_blank" rel="noopener noreferrer" class="text-blue-700 underline">{{ t }}</a><template v-else>{{ t }}</template></template></p>

    <div v-if="post.can_edit || post.can_delete" class="flex gap-2">
      <RouterLink v-if="post.can_edit" :to="`/board/${post.id}/edit`"
        class="flex min-h-11 items-center rounded border border-gray-300 bg-white px-4 text-sm">수정</RouterLink>
      <button v-if="post.can_delete" type="button" :disabled="busy" @click="removePost"
        class="min-h-11 rounded border border-red-700 px-4 text-sm text-red-700 disabled:opacity-50">삭제</button>
    </div>
    <p v-if="actionError" role="alert" class="text-sm text-red-700">{{ actionError }}</p>

    <section>
      <h2 class="mb-2 font-bold">댓글 {{ post.comments.length }}개</h2>
      <ul v-if="post.comments.length" class="mb-3 divide-y divide-gray-200 rounded bg-white">
        <li v-for="c in post.comments" :key="c.id" class="px-3 py-2">
          <div class="flex items-center justify-between gap-2">
            <span class="text-sm text-gray-600">{{ c.author }} · {{ dateTime(c.created_at) }}</span>
            <button v-if="c.can_delete" type="button" :disabled="busy" @click="removeComment(c)"
              class="min-h-11 min-w-11 shrink-0 text-sm text-red-700 disabled:opacity-50" :aria-label="`${c.author}의 댓글 삭제`">삭제</button>
          </div>
          <p class="whitespace-pre-wrap break-words"><template v-for="(t, i) in parts(c.body)" :key="i"><a v-if="i % 2" :href="t" target="_blank" rel="noopener noreferrer" class="text-blue-700 underline">{{ t }}</a><template v-else>{{ t }}</template></template></p>
        </li>
      </ul>
      <form class="space-y-2" @submit.prevent="addComment">
        <label for="comment" class="block text-sm font-medium">댓글 쓰기</label>
        <textarea id="comment" v-model="comment" required maxlength="1000" rows="3"
          class="w-full rounded border border-gray-300 bg-white p-3"></textarea>
        <button type="submit" :disabled="busy" class="min-h-11 w-full rounded bg-blue-700 font-medium text-white disabled:opacity-50">
          {{ busy ? '처리 중…' : '등록' }}
        </button>
      </form>
    </section>
  </article>
</template>
