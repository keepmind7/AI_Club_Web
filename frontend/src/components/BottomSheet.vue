<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, useId } from 'vue'

// 확인용 하단 시트. 네이티브 <dialog>의 showModal()이 포커스 가두기, Esc 닫기, 닫은 뒤 포커스 복귀를 맡는다.
// 열고 닫기는 부모가 v-if로 한다.
defineProps<{ title: string; action: string; busy?: boolean }>()
const emit = defineEmits<{ confirm: []; close: [] }>()
const dlg = ref<HTMLDialogElement>()
const titleId = useId()

onMounted(() => dlg.value?.showModal())
onBeforeUnmount(() => dlg.value?.close())
</script>

<template>
  <dialog ref="dlg" :aria-labelledby="titleId" @cancel.prevent="emit('close')" @click.self="emit('close')"
    class="m-0 mx-auto mt-auto w-full max-w-lg rounded-t-[20px] bg-surface p-0 text-ink backdrop:bg-ink/40">
    <div class="flex flex-col gap-3.5 px-5 pt-[22px] pb-[max(28px,env(safe-area-inset-bottom))]">
      <h2 :id="titleId" class="text-lg font-bold text-brand">{{ title }}</h2>
      <p class="text-[15px] leading-relaxed text-ink-2"><slot /></p>
      <div class="grid grid-cols-2 gap-2">
        <button type="button" autofocus class="min-h-[50px] rounded-xl border border-field bg-surface text-[15px] font-medium" @click="emit('close')">
          그대로 두기
        </button>
        <button type="button" :disabled="busy" class="min-h-[50px] rounded-xl bg-warn text-[15px] font-bold text-white disabled:opacity-45" @click="emit('confirm')">
          {{ busy ? '처리 중…' : action }}
        </button>
      </div>
    </div>
  </dialog>
</template>
