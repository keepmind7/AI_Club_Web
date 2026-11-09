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

export type RegStatus = 'confirmed' | 'waitlisted'

export interface EventSummary {
  id: number
  title: string
  starts_at: string
  place: string
  capacity: number
  fee: number
  confirmed_count: number
  waitlist_count: number
  my_status: RegStatus | null
  my_waitlist_position: number | null
}

export interface EventDetail extends EventSummary {
  description: string
  attendees: { name: string; status: RegStatus }[]
}

export type AttendanceMark = 'unknown' | 'present' | 'absent'

export interface MyAttendance {
  total: number
  present: number
  absent: number
  rate: number | null
  records: { event_id: number; title: string; starts_at: string; attendance: AttendanceMark }[]
}

export type Category = 'dues' | 'event_fee' | 'other_income' | 'expense' | 'refund'

export interface MyPayments {
  monthly_dues: number
  dues: { month: string; paid: boolean }[]
  event_fees: { event_id: number; title: string; starts_at: string; fee: number; paid: boolean }[]
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
  unpaid_event_fees: { event_id: number; title: string; member_id: number; name: string; fee: number }[]
  refunds_needed: { event_id: number; title: string; member_id: number; name: string; amount: number }[]
  attendance: { member_id: number; name: string; total: number; present: number; rate: number | null }[]
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
