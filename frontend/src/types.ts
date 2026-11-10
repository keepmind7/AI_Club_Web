// API 계약(api-contract.md)의 JSON 예시를 그대로 옮긴 타입
export interface User {
  id: number
  username: string
  name: string
  is_staff: boolean
  must_change_password: boolean
  phone: string | null
  joined_on: string | null
}

export interface EventSummary {
  id: number
  title: string
  starts_at: string
  place: string
  capacity: number // 0이면 정원 없음. 신청을 막지 않는 기준 인원
  confirmed_count: number
  my_status: 'confirmed' | null
}

export interface EventDetail extends EventSummary {
  description: string
  attendees: { name: string }[]
}

export type AttendanceMark = 'unknown' | 'present' | 'absent'

export interface MyAttendance {
  total: number
  present: number
  absent: number
  rate: number | null
  records: { event_id: number; title: string; starts_at: string; attendance: AttendanceMark }[]
}

export type Category = 'dues' | 'other_income' | 'expense'

export interface MyPayments {
  monthly_dues: number
  dues: { month: string; paid: boolean }[]
  transactions: { date: string; category: Category; amount: number; memo: string }[]
}

export interface Announcement {
  id: number
  title: string
  body: string
  created_at: string
}

export interface Dashboard {
  balance: number
  carry_over: number
  totals: Record<Category, number>
  monthly: { month: string; income: number; expense: number }[]
  unpaid_dues: { member_id: number; name: string; months: string[] }[]
  attendance: { member_id: number; name: string; total: number; present: number; rate: number | null }[]
  pending_signups: number
}

export interface SharedAccount {
  id: number
  email: string
  password: string
  memo: string
  members: { name: string }[]
}

export interface PostSummary {
  id: number
  title: string
  author: string
  created_at: string
  comment_count: number
  excerpt: string
}

export interface Comment {
  id: number
  author: string
  body: string
  created_at: string
  can_delete: boolean
}

export interface PostDetail extends PostSummary {
  body: string
  updated_at: string
  can_edit: boolean
  can_delete: boolean
  comments: Comment[]
}
