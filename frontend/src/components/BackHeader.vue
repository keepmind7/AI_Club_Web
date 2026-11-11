<script setup lang="ts">
// 하위 화면 위쪽의 "‹ 돌아갈 곳" 줄
import { useRouter } from 'vue-router'

const props = defineProps<{ to: string; label: string; wide?: boolean }>()
const router = useRouter()

// 바로 앞 화면이 돌아갈 곳이면 뒤로 가기로 돌아간다: 보던 스크롤 위치가 그대로다 (모임 달력, 게시판 목록).
// 주소로 바로 들어왔거나 다른 화면에서 왔으면 원래대로 그 주소로 이동한다.
function go(e: MouseEvent, navigate: (e: MouseEvent) => unknown) {
  if (window.history.state?.back === props.to && !(e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) && e.button === 0) {
    e.preventDefault()
    router.back()
  } else {
    navigate(e)
  }
}
</script>

<template>
  <!-- 안쪽 줄은 본문 칸(max-w-2xl)에 맞춘다: PC에서 오른쪽 버튼이 화면 끝으로 가지 않게 -->
  <header class="h-14 shrink-0 border-b border-line-soft">
    <div :class="wide ? 'max-w-[1080px]' : 'max-w-2xl'" class="mx-auto flex h-full w-full items-center pr-5 pl-2 lg:pr-10 lg:pl-8">
    <RouterLink v-slot="{ href, navigate }" :to="to" custom>
      <a :href="href" class="flex min-h-11 items-center gap-0.5 px-2 text-[15px] text-ink" @click="go($event, navigate)">
        <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 6-6 6 6 6" /></svg>
        <span>{{ label }}</span>
      </a>
    </RouterLink>
    <slot />
    </div>
  </header>
</template>
