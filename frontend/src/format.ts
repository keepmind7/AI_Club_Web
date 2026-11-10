import type { AttendanceMark, Category, EventSummary } from './types'

const tz = 'Asia/Seoul'
const fmt = (o: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('ko-KR', { timeZone: tz, ...o })
const dateTimeFmt = fmt({ month: 'long', day: 'numeric', weekday: 'short', hour: 'numeric', minute: '2-digit' })
const shortFmt = fmt({ month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit' })
const shortYearFmt = fmt({ year: 'numeric', month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit' })
const dayFmt = fmt({ month: 'long', day: 'numeric', weekday: 'short' })
const mdFmt = fmt({ month: 'long', day: 'numeric' })
const timeFmt = fmt({ hour: 'numeric', minute: '2-digit' })
const weekdayFmt = fmt({ weekday: 'long' })
const dateFmt = fmt({ year: 'numeric', month: 'long', day: 'numeric' })
const keyFmt = new Intl.DateTimeFormat('en-CA', { timeZone: tz }) // "2026-11-14"

/** 서울 날짜 "YYYY-MM-DD" */
const dayKey = (d: Date | string) => keyFmt.format(new Date(d))
/** 서울 달력 기준 며칠 차이 (b - a) */
const dayDiff = (a: Date | string, b: Date | string) => (Date.parse(dayKey(b)) - Date.parse(dayKey(a))) / 864e5

/** 10000 → "10,000원" */
export const won = (n: number) => `${n.toLocaleString('ko-KR')}원`

/** ISO 일시 → "11월 14일 (토) 오후 2:00" */
export const dateTime = (iso: string) => dateTimeFmt.format(new Date(iso))

/** ISO 일시 → 올해면 "11월 9일 오후 1:20", 아니면 "2025년 11월 9일 오후 1:20" */
export const dateTimeShort = (iso: string) => (thisYear(iso) ? shortFmt : shortYearFmt).format(new Date(iso))

/** 오늘 → "11월 9일 (월)" */
export const today = () => dayFmt.format(new Date())

/** ISO 일시 → "오후 7:30" */
export const time = (iso: string) => timeFmt.format(new Date(iso))

/** ISO 일시 → 날짜 숫자 "14", 요일 "토요일" (날짜 칩의 "14 / 월"이 "14월"로 읽히지 않게 요일을 다 쓴다) */
export const dayNum = (iso: string) => String(Number(dayKey(iso).slice(8)))
export const weekday = (iso: string) => weekdayFmt.format(new Date(iso))

/** "2026-11-03" 또는 ISO 일시 → "2026년 11월 3일" */
export const date = (s: string) => dateFmt.format(new Date(s.length === 10 ? `${s}T00:00:00+09:00` : s))

/** "2026-11" → "2026년 11월" */
export const month = (m: string) => `${m.slice(0, 4)}년 ${Number(m.slice(5, 7))}월`

/** 이번 달 "YYYY-MM" (서울) */
export const thisMonth = () => dayKey(new Date()).slice(0, 7)

const thisYear = (iso: string) => dayKey(iso).slice(0, 4) === dayKey(new Date()).slice(0, 4)

/** ISO 일시 → 올해면 "11월 7일", 아니면 "2025년 11월 7일" */
export const shortDate = (iso: string) => (thisYear(iso) ? mdFmt.format(new Date(iso)) : date(iso))

/** ISO 일시가 속한 달 제목: 올해면 "11월", 아니면 "2025년 12월" */
export const monthHeading = (iso: string) => {
  const k = dayKey(iso)
  return thisYear(iso) ? `${Number(k.slice(5, 7))}월` : month(k)
}

/** 모임까지 남은 날: "오늘", "내일", "5일 남음" */
export const dDay = (iso: string) => {
  const n = dayDiff(new Date(), iso)
  if (n <= 0) return '오늘'
  if (n === 1) return '내일'
  return `${n}일 남음`
}

/** 지난 시각: "방금", "12분 전", "2시간 전", "어제", "11월 6일" (다른 해면 "2025년 11월 6일") */
export const ago = (iso: string) => {
  const min = Math.floor((Date.now() - Date.parse(iso)) / 60000)
  if (min < 1) return '방금'
  if (min < 60) return `${min}분 전`
  const days = dayDiff(iso, new Date())
  if (days === 0) return `${Math.floor(min / 60)}시간 전`
  if (days === 1) return '어제'
  return shortDate(iso)
}

/** 정원보다 신청자가 많은지. 정원은 신청을 막지 않는다. */
export const over = (e: EventSummary) => !!e.capacity && e.confirmed_count > e.capacity

/** 인원: "9 / 12명", 넘치면 "23 / 20명 (+3명)", 정원 없으면 "9명 · 정원 없음". 넘치면 over()로 경고색을 입힌다. */
export const headcount = (e: EventSummary) => {
  if (!e.capacity) return `${e.confirmed_count}명 · 정원 없음`
  const base = `${e.confirmed_count} / ${e.capacity}명`
  return over(e) ? `${base} (+${e.confirmed_count - e.capacity}명)` : base
}

/** "my.team@gmail.com" → ["my.", "team@", "gmail.", "com"]. 조각마다 <wbr>을 붙여 '.'과 '@' 뒤에서만 줄을 바꾼다. */
export const emailChunks = (e: string) => e.split(/(?<=[.@])/)

/** 받침에 맞춰 "와/과"를 붙인다: "이영희와", "홍길동과" */
export const withParticle = (word: string) => {
  const c = word.charCodeAt(word.length - 1) - 0xac00
  return word + (c >= 0 && c < 11172 && c % 28 ? '과' : '와')
}

export const attendanceMark: Record<AttendanceMark, string> = { unknown: '미확인', present: '출석', absent: '결석' }
export const category: Record<Category, string> = { dues: '회비', other_income: '기타 수입', expense: '지출' }

/** 비밀번호 규칙 안내 (가입·비밀번호 변경 공통) */
export const passwordHint = '8자 이상, 영문·숫자·특수문자를 모두 넣어 주세요. 특수문자로 시작할 수 없어요.'

/** 계약의 비밀번호 규칙을 미리 검사한다. 통과하면 ''. 최종 판단(흔한 비밀번호 등)은 서버가 한다. */
export function passwordError(pw: string) {
  const special = /[^A-Za-z0-9\s]/
  if ([...pw].length < 8 || !/[A-Za-z]/.test(pw) || !/\d/.test(pw) || !special.test(pw))
    return '비밀번호는 8자 이상으로, 영문·숫자·특수문자를 모두 넣어 주세요.'
  if (special.test(pw[0])) return '비밀번호는 특수문자로 시작할 수 없어요.'
  return ''
}
