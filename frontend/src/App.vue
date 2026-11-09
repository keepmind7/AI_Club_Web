<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuth } from './auth'
import { toast } from './toast'

const auth = useAuth()
const route = useRoute()
const showNav = computed(() => auth.user && !auth.user.must_change_password && !route.meta.public)
// 아이콘은 시안의 선 아이콘 그대로 (path d 값)
const tabs = computed(() => [
  { key: 'home', to: '/', label: '홈', icon: 'M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z' },
  { key: 'events', to: '/events', label: '모임', icon: 'M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zM16 3v4M8 3v4M3 10h18' },
  { key: 'news', to: '/news', label: '소식', icon: 'M4 5h16v11H8l-4 4zM8 9h8M8 12h5' },
  { key: 'me', to: '/me', label: '내 정보', icon: 'M12 4a4 4 0 1 1 0 8 4 4 0 0 1 0-8zM4 21c1.5-4 4.5-6 8-6s6.5 2 8 6' },
  ...(auth.user?.is_staff
    ? [{ key: 'staff', to: '/staff', label: '운영', icon: 'M6 4h12a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM9 4V3h6v1M8 10h8M8 14h8M8 18h5' }]
    : []),
])
</script>

<template>
  <div class="flex min-h-dvh flex-col lg:flex-row">
    <!-- 휴대폰: 아래 고정 탭바 / 넓은 화면(1024px~): 왼쪽 세로 메뉴 -->
    <nav v-if="showNav" aria-label="주 메뉴"
      class="sticky bottom-0 z-20 order-last grid border-t border-line bg-surface px-1 pt-1 pb-[max(8px,env(safe-area-inset-bottom))]
        lg:top-0 lg:bottom-auto lg:order-first lg:flex lg:h-dvh lg:w-[220px] lg:shrink-0 lg:flex-col lg:gap-1 lg:border-t-0 lg:border-r lg:border-line-soft lg:bg-bg lg:px-4 lg:py-7"
      :class="[tabs.length === 5 ? 'grid-cols-5' : 'grid-cols-4', route.meta.ownBar && 'max-lg:hidden']">
      <span class="hidden px-3 pb-[22px] text-2xl font-semibold text-brand lg:block">Mythos</span>
      <RouterLink v-for="t in tabs" :key="t.key" :to="t.to" :aria-current="route.meta.tab === t.key ? 'page' : undefined"
        class="flex min-h-[54px] flex-col items-center justify-center gap-[3px] text-xs text-muted
          lg:min-h-11 lg:flex-row lg:justify-start lg:gap-3 lg:rounded-[10px] lg:px-3 lg:text-[15px] lg:text-ink-2
          aria-[current=page]:font-bold aria-[current=page]:text-accent lg:aria-[current=page]:bg-accent-soft lg:aria-[current=page]:text-accent-ink">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"
          class="size-6 lg:size-5" :stroke-width="route.meta.tab === t.key ? 2 : 1.75"><path :d="t.icon" /></svg>
        <span>{{ t.label }}</span>
      </RouterLink>
    </nav>
    <main class="flex min-w-0 flex-1 flex-col">
      <RouterView />
    </main>
  </div>
  <!-- 알림 토스트: 화면 위에 떠서 레이아웃을 밀지 않는다. 알림 영역은 늘 있어야 화면 낭독기가 읽는다. -->
  <div role="status" aria-live="polite"
    class="pointer-events-none fixed inset-x-5 bottom-[calc(96px+env(safe-area-inset-bottom))] z-30 flex justify-center lg:bottom-8 lg:left-[260px]">
    <p v-if="toast" class="flex min-h-12 w-full max-w-md items-center justify-center rounded-xl bg-ink px-4 text-center text-[15px] font-medium text-white">{{ toast }}</p>
  </div>
</template>
