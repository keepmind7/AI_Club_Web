import { ref } from 'vue'

// 화면 아래 잠깐 뜨는 알림 한 줄. App.vue가 그리고, 화면을 옮겨도 남는다(비밀번호 변경 → 홈).
export const toast = ref('')
let timer = 0

export function showToast(text: string) {
  toast.value = text
  clearTimeout(timer)
  timer = window.setTimeout(() => (toast.value = ''), 1800)
}
