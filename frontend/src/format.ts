import type { AttendanceMark, Category, RegStatus } from './types'

const dateTimeFmt = new Intl.DateTimeFormat('ko-KR', {
  month: 'long', day: 'numeric', weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: 'Asia/Seoul',
})
const dateFmt = new Intl.DateTimeFormat('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'Asia/Seoul' })

/** 10000 → "10,000원" */
export const won = (n: number) => `${n.toLocaleString('ko-KR')}원`

/** ISO 일시 → "11월 20일 (금) 19:00" */
export const dateTime = (iso: string) => dateTimeFmt.format(new Date(iso))

/** "2026-11-03" 또는 ISO 일시 → "2026년 11월 3일" */
export const date = (s: string) => dateFmt.format(new Date(s.length === 10 ? `${s}T00:00:00+09:00` : s))

/** "2026-11" → "2026년 11월" */
export const month = (m: string) => `${m.slice(0, 4)}년 ${Number(m.slice(5, 7))}월`

export const regStatus: Record<RegStatus, string> = { confirmed: '확정', waitlisted: '대기' }
export const attendanceMark: Record<AttendanceMark, string> = { unknown: '미확인', present: '출석', absent: '결석' }
export const category: Record<Category, string> = {
  dues: '회비', event_fee: '참가비', other_income: '기타 수입', expense: '지출', refund: '환불',
}
