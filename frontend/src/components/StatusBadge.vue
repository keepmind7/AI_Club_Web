<script setup lang="ts">
import type { RegStatus } from '../types'

// 확정(초록) / 대기 n번(주황). 순번이 없으면(null) "대기"만.
defineProps<{ status: RegStatus; position?: number | null }>()
</script>

<template>
  <span class="shrink-0 rounded-full px-2.5 py-1 text-[13px] font-bold"
    :class="status === 'confirmed' ? 'bg-ok-soft text-ok' : 'bg-warn-soft text-warn'">
    {{ status === 'confirmed' ? '확정' : position ? `대기 ${position}번` : '대기' }}
  </span>
</template>
