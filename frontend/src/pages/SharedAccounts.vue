<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'
import { useAuth } from '../auth'
import BackHeader from '../components/BackHeader.vue'
import { emailChunks } from '../format'
import { showToast } from '../toast'
import type { SharedAccount } from '../types'

const user = useAuth().user!
const items = ref<SharedAccount[] | null>(null)
const error = ref('')

api<SharedAccount[]>('/api/shared-accounts')
  .then((d) => (items.value = d))
  .catch((e: Error) => (error.value = e.message))

async function copy(what: '이메일을' | '비밀번호를', value: string) {
  try {
    // HTTP(비보안) 접속에서는 navigator.clipboard가 없어 실패로 처리된다.
    await navigator.clipboard.writeText(value)
    showToast(`${what} 복사했어요`)
  } catch {
    showToast(`${what} 복사하지 못했어요`)
  }
}

const row = 'grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-t border-line-soft first:border-t-0 py-3.5 pr-3 pl-4'
</script>

<template>
  <BackHeader to="/me" label="내 정보" />
  <div class="flex w-full max-w-2xl flex-col gap-[22px] px-5 pt-[22px] pb-28 lg:px-10">
    <div class="flex flex-col gap-1.5">
      <h1 class="text-[26px] font-semibold text-brand">공유 계정</h1>
      <p v-if="user.is_staff" class="text-sm leading-relaxed text-muted">
        운영진이라 전체 {{ items?.length ?? '' }}개가 보여요.
        <a href="/club-admin/club/sharedaccount/" class="underline">관리자 화면에서 관리하기</a>
      </p>
    </div>

    <p v-if="error" role="alert" class="text-warn">{{ error }}</p>
    <p v-else-if="!items" class="text-muted">불러오는 중…</p>
    <p v-else-if="!items.length" class="text-[15px] text-muted">
      {{ user.is_staff ? '등록된 공유 계정이 없어요. 관리자 화면에서 등록해 주세요.' : '배정된 공유 계정이 없어요. 필요하면 운영진에게 문의해 주세요.' }}
    </p>
    <template v-else>
      <!-- 계정 하나 = 카드 하나: 메모, 이메일, 비밀번호, 같이 쓰는 사람 -->
      <article v-for="a in items" :key="a.id" :aria-label="a.email" class="flex flex-col rounded-2xl border border-line bg-surface">
        <p v-if="a.memo" class="px-4 pt-3.5 pb-3 text-sm leading-relaxed whitespace-pre-line text-ink-2">{{ a.memo }}</p>
        <div :class="row">
          <span class="flex min-w-0 flex-col gap-[3px]">
            <span class="text-[13px] text-muted">이메일</span>
            <span class="text-[17px] font-medium break-words"><template v-for="(c, i) in emailChunks(a.email)" :key="i">{{ c }}<wbr /></template></span>
          </span>
          <button type="button" :aria-label="`${a.email} 이메일 복사`" class="min-h-11 rounded-[10px] border border-field bg-surface px-4 text-[15px] font-medium" @click="copy('이메일을', a.email)">복사</button>
        </div>
        <div :class="row">
          <span class="flex flex-col gap-[3px]">
            <span class="text-[13px] text-muted">비밀번호</span>
            <span role="img" aria-label="비밀번호 가려짐" class="text-[13px] leading-[26px] tracking-[0.25em]">●●●●●●●●</span>
          </span>
          <button type="button" :aria-label="`${a.email} 비밀번호 복사`" class="min-h-11 rounded-[10px] bg-accent px-4 text-[15px] font-bold text-white" @click="copy('비밀번호를', a.password)">복사</button>
        </div>
        <section class="flex flex-col gap-2.5 border-t border-line-soft px-4 pt-3.5 pb-4">
          <h2 class="text-[13px] font-bold text-brand">같이 쓰는 사람 <span class="font-normal text-muted">{{ a.members.length }}명</span></h2>
          <p v-if="!a.members.length" class="text-sm text-muted">배정된 회원이 없어요. 관리자 화면에서 배정해 주세요.</p>
          <ul v-else class="flex flex-wrap gap-1.5">
            <li v-for="(m, i) in a.members" :key="i" class="rounded-full px-3 py-1.5 text-sm"
              :class="m.name === user.name ? 'bg-ok-soft font-bold text-ok' : 'border border-line bg-surface'">
              {{ m.name }}<template v-if="m.name === user.name"> (나)</template>
            </li>
          </ul>
        </section>
      </article>

      <p class="rounded-xl bg-sunk px-4 py-3.5 text-[13px] leading-[1.7] text-ink-2">
        비밀번호는 여기서만 복사하고 다른 곳에 옮겨 적지 말아 주세요. 바뀌면 운영진이 이 화면에 새로 올려요.
      </p>
    </template>
  </div>
</template>
