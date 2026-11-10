<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import BackHeader from '../components/BackHeader.vue'
import BottomSheet from '../components/BottomSheet.vue'
import { ago, dateTimeShort } from '../format'
import type { Comment, PostDetail } from '../types'

const props = defineProps<{ id: string }>()
const router = useRouter()
const post = ref<PostDetail | null>(null)
const loading = ref(true)
const error = ref('')
const actionError = ref('')
const busy = ref(false)
const comment = ref('')
// 삭제 확인 시트: 글 삭제면 'post', 댓글 삭제면 그 댓글
const confirming = ref<'post' | Comment | null>(null)

api<PostDetail>(`/api/posts/${props.id}`)
  .then((d) => (post.value = d))
  .catch((e: Error) => (error.value = e.message))
  .finally(() => (loading.value = false))

// 텍스트를 URL로 나눈다. 캡처 그룹으로 split하므로 홀수 번째가 링크다. v-html을 쓰지 않아 XSS가 없다.
// ponytail: 링크 바로 뒤에 붙은 문장부호(마침표, 괄호)도 링크에 포함된다. 문제가 되면 정규식에서 끝 문자를 제외한다.
const parts = (text: string) => text.split(/(https?:\/\/[^\s]+)/)

// 새 글은 updated_at이 created_at과 같고, 작성자가 고칠 때만 바뀐다.
const edited = (p: PostDetail) => Date.parse(p.updated_at) !== Date.parse(p.created_at)

async function run(fn: () => Promise<void>) {
  busy.value = true
  actionError.value = ''
  try {
    await fn()
  } catch (e) {
    actionError.value = (e as Error).message
  } finally {
    busy.value = false
    confirming.value = null
  }
}

function remove() {
  const target = confirming.value
  if (target === 'post') {
    run(async () => {
      await api(`/api/posts/${props.id}/delete`, 'POST')
      router.replace('/news?tab=board')
    })
  } else if (target) {
    run(async () => {
      await api(`/api/comments/${target.id}/delete`, 'POST')
      const p = post.value!
      p.comments = p.comments.filter((x) => x.id !== target.id)
      p.comment_count = p.comments.length
    })
  }
}

function addComment() {
  if (!comment.value.trim()) return
  run(async () => {
    post.value = await api<PostDetail>(`/api/posts/${props.id}/comments`, 'POST', { body: comment.value })
    comment.value = ''
  })
}

const textBtn = 'min-h-11 min-w-11 px-1.5 text-[13px] text-muted underline disabled:opacity-45'
</script>

<template>
  <BackHeader to="/news?tab=board" label="게시판">
    <div v-if="post && (post.can_edit || post.can_delete)" class="ml-auto flex items-center gap-1">
      <RouterLink v-if="post.can_edit" :to="`/board/${post.id}/edit`" class="flex min-h-11 items-center px-3 text-[15px] text-ink-2">수정</RouterLink>
      <button v-if="post.can_delete" type="button" :disabled="busy" class="min-h-11 px-3 text-[15px] text-warn disabled:opacity-45" @click="confirming = 'post'">삭제</button>
    </div>
  </BackHeader>
  <p v-if="loading" class="px-5 py-5 text-muted lg:px-10">불러오는 중…</p>
  <p v-else-if="error" role="alert" class="px-5 py-5 text-warn lg:px-10">{{ error }}</p>
  <template v-else-if="post">
    <div class="flex w-full mx-auto max-w-2xl flex-1 flex-col">
      <article class="flex flex-col gap-3.5 px-5 pt-5 pb-6 lg:px-10">
        <h1 class="text-[23px] leading-snug font-semibold text-brand break-words">{{ post.title }}</h1>
        <p class="text-[13px] text-muted">
          {{ post.author }} · {{ dateTimeShort(post.created_at) }}<template v-if="edited(post)"> · 수정됨</template>
        </p>
        <p class="text-base leading-[1.75] whitespace-pre-wrap break-words"><template v-for="(t, i) in parts(post.body)" :key="i"><a v-if="i % 2" :href="t" target="_blank" rel="noopener noreferrer" class="underline">{{ t }}</a><template v-else>{{ t }}</template></template></p>
      </article>
      <div aria-hidden="true" class="h-2 bg-sunk lg:mx-10"></div>

      <section aria-labelledby="c-title" class="flex flex-col px-5 pt-[18px] pb-3 lg:px-10">
        <h2 id="c-title" class="mb-1.5 text-[15px] font-bold text-brand">댓글 {{ post.comments.length }}</h2>
        <p v-if="!post.comments.length" class="py-3 text-sm text-muted">첫 댓글을 남겨 보세요.</p>
        <ul>
          <li v-for="c in post.comments" :key="c.id" class="flex flex-col gap-1 border-b border-line-soft py-3">
            <span class="flex min-h-6 items-center justify-between gap-2 text-[13px]">
              <span><b class="font-bold">{{ c.author }}</b> <span class="text-muted">· {{ ago(c.created_at) }}</span></span>
              <button v-if="c.can_delete" type="button" :disabled="busy" :class="textBtn" class="-my-2.5"
                :aria-label="`${c.author}의 댓글 삭제`" @click="confirming = c">삭제</button>
            </span>
            <span class="text-[15px] leading-relaxed whitespace-pre-wrap break-words"><template v-for="(t, i) in parts(c.body)" :key="i"><a v-if="i % 2" :href="t" target="_blank" rel="noopener noreferrer" class="underline">{{ t }}</a><template v-else>{{ t }}</template></template></span>
          </li>
        </ul>
      </section>
    </div>

    <form class="sticky bottom-0 z-10 border-t border-line bg-surface px-3 pt-2.5 pb-[max(22px,env(safe-area-inset-bottom))] lg:px-0 lg:pb-4" @submit.prevent="addComment">
      <p v-if="actionError" role="alert" class="mb-2 mx-auto max-w-2xl px-1 text-sm text-warn lg:px-10">{{ actionError }}</p>
      <div class="flex mx-auto max-w-2xl items-end gap-2 lg:px-10">
        <label for="comment" class="sr-only">댓글</label>
        <textarea id="comment" v-model="comment" rows="1" maxlength="1000" placeholder="댓글을 남겨 주세요"
          class="max-h-[120px] min-h-11 flex-1 resize-none rounded-[22px] border border-field bg-bg px-3.5 py-[11px] text-[15px] leading-snug placeholder:text-muted [field-sizing:content]"></textarea>
        <button type="submit" :disabled="busy || !comment.trim()"
          class="min-h-11 shrink-0 rounded-[22px] bg-accent px-[18px] text-[15px] font-bold text-white disabled:cursor-not-allowed disabled:opacity-45">
          {{ busy ? '등록 중…' : '등록' }}
        </button>
      </div>
    </form>

    <BottomSheet v-if="confirming" :title="confirming === 'post' ? '글을 삭제할까요?' : '댓글을 삭제할까요?'" action="삭제하기" :busy="busy"
      @close="confirming = null" @confirm="remove">
      {{ confirming === 'post' ? '댓글도 함께 삭제돼요. 되돌릴 수 없어요.' : '삭제한 댓글은 되돌릴 수 없어요.' }}
    </BottomSheet>
  </template>
</template>
