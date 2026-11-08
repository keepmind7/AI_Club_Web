<script setup lang="ts">
import { computed } from 'vue'
import { useAuth } from './auth'

const auth = useAuth()
const showNav = computed(() => auth.user && !auth.user.must_change_password)
const links = [
  ['/', '홈'],
  ['/events', '모임'],
  ['/attendance', '출석'],
  ['/payments', '납부'],
  ['/announcements', '공지'],
  ['/me', '내 정보'],
]
const navClass = 'flex min-h-11 items-center rounded px-3 text-sm hover:bg-gray-100'
</script>

<template>
  <header v-if="showNav" class="border-b border-gray-200 bg-white">
    <nav aria-label="주 메뉴" class="mx-auto flex max-w-2xl flex-wrap gap-1 px-2 py-1">
      <RouterLink v-for="[to, label] in links" :key="to" :to="to" :class="navClass" exact-active-class="font-bold text-blue-700">
        {{ label }}
      </RouterLink>
      <template v-if="auth.user?.is_staff">
        <RouterLink to="/dashboard" :class="navClass" exact-active-class="font-bold text-blue-700">운영 대시보드</RouterLink>
        <a href="/club-admin/" :class="navClass">관리자 화면</a>
      </template>
    </nav>
  </header>
  <main class="mx-auto max-w-2xl p-4">
    <RouterView />
  </main>
</template>
