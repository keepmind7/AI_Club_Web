<script setup lang="ts">
// 하위 화면 위쪽의 "‹ 돌아갈 곳" 줄
defineProps<{ to: string; label: string; wide?: boolean }>()
</script>

<template>
  <!-- 안쪽 줄은 본문 칸(max-w-2xl)에 맞춘다: PC에서 오른쪽 버튼이 화면 끝으로 가지 않게 -->
  <header class="h-14 shrink-0 border-b border-line-soft">
    <div :class="wide ? 'max-w-[1080px]' : 'max-w-2xl'" class="mx-auto flex h-full w-full items-center pr-5 pl-2 lg:pr-10 lg:pl-8">
    <RouterLink :to="to" class="flex min-h-11 items-center gap-0.5 px-2 text-[15px] text-ink">
      <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 6-6 6 6 6" /></svg>
      <span>{{ label }}</span>
    </RouterLink>
    <slot />
    </div>
  </header>
</template>
