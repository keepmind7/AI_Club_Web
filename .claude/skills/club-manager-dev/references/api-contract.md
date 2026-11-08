# Club Manager API 명세 (백엔드 ↔ 프론트엔드 계약)

이 문서가 유일한 기준이다. 백엔드와 프론트엔드는 이 문서에 맞춰 구현한다. 바꿔야 할 이유가 생기면 임의로 바꾸지 말고 오케스트레이터에게 보고한다.

## 공통

- 기본 경로: `/api/`. 관리자 화면: `/club-admin/`. Django 정적 파일: `/static/`.
- 인증: Django 세션 쿠키. 프론트엔드와 같은 출처(개발 시 Vite 프록시, 운영 시 Caddy)에서 호출한다.
- CSRF: `GET /api/auth/me`가 `csrftoken` 쿠키를 심는다. 프론트엔드는 POST 요청마다 쿠키 값을 `X-CSRFToken` 헤더로 보낸다.
- 요청·응답 본문은 JSON. 필드 이름은 snake_case.
- 날짜: `"YYYY-MM-DD"`. 일시: ISO 8601, 서울 시간대 포함 (`"2026-11-20T19:00:00+09:00"`). 월: `"YYYY-MM"`.
- 금액: 원 단위 정수.
- 오류 응답: `{"detail": "사람이 읽을 수 있는 한국어 메시지"}`
  - 401 또는 403: 로그인 안 됨, 활동 상태가 아님, 권한 없음
  - 400: 입력 오류, 규칙 위반 (이미 신청함 등)
  - 404: 대상 없음 (예: `{"detail": "모임을 찾을 수 없습니다."}`)
- 활동(`active`) 상태가 아닌 회원은 로그인한 세션이 있어도 `/api/auth/logout`을 제외한 모든 API에서 403 (`/api/auth/me` 포함). 이때 `detail`은 정확히 `"이용이 제한된 계정입니다. 운영진에게 문의하세요."`이며, 프론트엔드는 "이용이 제한" 포함 여부로 이용 제한을 구분하므로 이 문구를 바꾸지 않는다. `/api/auth/me`는 403이어도 CSRF 쿠키는 심는다.
- Member 기록이 없는 슈퍼유저/운영진 계정은 활동 회원으로 취급하고 `name`은 `username`으로 대신한다.

## 공통 객체

### User
```json
{ "id": 1, "username": "hong", "name": "홍길동", "is_staff": false, "must_change_password": true, "phone": "010-1234-5678", "joined_on": "2026-03-01" }
```
- `phone`, `joined_on`: Member 기록이 없으면 `null`.

### EventSummary
```json
{
  "id": 3,
  "title": "11월 정기 모임",
  "starts_at": "2026-11-20T19:00:00+09:00",
  "place": "강남역 스터디룸",
  "capacity": 12,
  "fee": 10000,
  "confirmed_count": 12,
  "waitlist_count": 2,
  "my_status": "confirmed"
}
```
- `capacity`: 정원. `0`이면 정원 제한 없음.
- `fee`: 참가비. `0`이면 무료.
- `my_status`: `"confirmed"` | `"waitlisted"` | `null` (신청 안 함 또는 취소함)

### EventDetail
EventSummary의 모든 필드 + 아래 필드
```json
{
  "description": "모임 설명",
  "my_waitlist_position": null,
  "attendees": [
    { "name": "홍길동", "status": "confirmed" },
    { "name": "김철수", "status": "waitlisted" }
  ]
}
```
- `my_waitlist_position`: 대기 중일 때 1부터 시작하는 순번, 아니면 `null`
- `attendees`: 취소하지 않은 신청자. 확정자를 먼저, 그다음 대기자를 신청 순서대로. 이름만 공개한다.

## 인증

| 메서드 | 경로 | 요청 | 성공 응답 | 실패 |
| --- | --- | --- | --- | --- |
| GET | `/api/auth/me` | - | 200 User | 401/403 로그인 안 됨 |
| POST | `/api/auth/login` | `{"username","password"}` | 200 User | 400 아이디·비밀번호 불일치, 403 활동 상태 아님 |
| POST | `/api/auth/logout` | - | 204 | - |
| POST | `/api/auth/password` | `{"old_password","new_password"}` | 204 | 400 기존 비밀번호 불일치 또는 Django 비밀번호 규칙 위반 |

- 비밀번호 변경에 성공하면 `must_change_password`를 `false`로 바꾸고 로그인 상태를 유지한다.
- 운영진이 관리자 화면에서 회원 비밀번호를 바꾸면 `must_change_password`가 `true`가 된다.
- 로그인 실패 제한: 같은 아이디로 10분 안에 5회 실패하면 10분간 400 `{"detail": "로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요."}`

## 모임

| 메서드 | 경로 | 요청 | 성공 응답 | 실패 |
| --- | --- | --- | --- | --- |
| GET | `/api/events` | 쿼리 `past=1` 선택 | 200 `EventSummary[]` | - |
| GET | `/api/events/{id}` | - | 200 EventDetail | 404 |
| POST | `/api/events/{id}/register` | - | 200 EventDetail | 400 이미 신청함 / 이미 시작한 모임 |
| POST | `/api/events/{id}/cancel` | - | 200 EventDetail | 400 신청 내역 없음 / 이미 시작한 모임 |

- `GET /api/events`: 기본은 시작 전 모임을 `starts_at` 오름차순. `past=1`이면 이미 시작한 모임을 내림차순.
- 신청: 확정 인원이 정원 미만(또는 정원 0)이면 `confirmed`, 아니면 `waitlisted`. 예전에 취소한 회원이 다시 신청하면 기존 신청을 되살리고 신청 시각을 지금으로 바꾼다.
- 취소: 확정자가 취소하면 같은 트랜잭션에서 가장 먼저 신청한 대기자를 `confirmed`로 승격한다.
- 신청·취소·승격은 하나의 DB 트랜잭션에서 처리한다. 동시에 신청해도 정원을 넘지 않아야 한다.

## 내 정보

### GET `/api/me/attendance` → 200
```json
{
  "total": 10,
  "present": 8,
  "absent": 1,
  "rate": 80,
  "records": [
    { "event_id": 3, "title": "11월 정기 모임", "starts_at": "2026-11-20T19:00:00+09:00", "attendance": "present" }
  ]
}
```
- 이미 시작한 모임 중 내가 `confirmed`인 신청만 대상. `records`는 최신순.
- `attendance`: `"unknown"` | `"present"` | `"absent"`
- `rate`: `present / total × 100`을 반올림한 정수. `total`이 0이면 `null`.

### GET `/api/me/payments` → 200
```json
{
  "monthly_dues": 20000,
  "dues": [ { "month": "2026-11", "paid": false }, { "month": "2026-10", "paid": true } ],
  "event_fees": [ { "event_id": 3, "title": "11월 정기 모임", "starts_at": "2026-11-20T19:00:00+09:00", "fee": 10000, "paid": true } ],
  "transactions": [ { "date": "2026-11-03", "category": "dues", "amount": 20000, "memo": "" } ]
}
```
- `dues`: 가입한 달부터 이번 달까지, 최신순. 그 달의 `dues` 거래가 있으면 `paid: true`.
- `event_fees`: 참가비가 있는 모임 중 내가 `confirmed`인 것, 최신순. 그 모임의 `event_fee` 거래가 있으면 `paid: true`.
- `transactions`: 나와 연결된 장부 거래 전체, 최신순.
- 운영진·슈퍼유저처럼 Member 기록이 없으면 빈 목록과 `monthly_dues`만 반환한다.

## 공지

### GET `/api/announcements` → 200
```json
[ { "id": 1, "title": "12월 일정 안내", "body": "본문", "created_at": "2026-11-01T10:00:00+09:00" } ]
```
- 최신순 전체.

## 운영 대시보드 (운영진 전용)

### GET `/api/dashboard` → 200, 운영진이 아니면 403

쿼리(선택): `year=YYYY`, `month=1~12` (`month`는 `year`와 함께만). 지정하면 `attendance`만 그 기간에 시작한 모임으로 계산한다. 다른 필드는 기간과 무관하다. 형식이 틀리면 400.
```json
{
  "balance": 523000,
  "carry_over": 300000,
  "totals": { "dues": 400000, "event_fee": 120000, "other_income": 0, "expense": 287000, "refund": 10000 },
  "monthly": [ { "month": "2026-11", "income": 160000, "expense": 87000 } ],
  "unpaid_dues": [ { "member_id": 2, "name": "김철수", "months": ["2026-10", "2026-11"] } ],
  "unpaid_event_fees": [ { "event_id": 3, "title": "11월 정기 모임", "member_id": 2, "name": "김철수", "fee": 10000 } ],
  "refunds_needed": [ { "event_id": 3, "title": "11월 정기 모임", "member_id": 5, "name": "이영희", "amount": 10000 } ],
  "attendance": [ { "member_id": 2, "name": "김철수", "total": 10, "present": 7, "rate": 70 } ]
}
```
- `balance` = `carry_over` + (dues + event_fee + other_income) − (expense + refund). `carry_over` 이후 날짜의 거래만 집계한다.
- `monthly`: 거래가 있는 달 전체, 최신순. `income` = 입금 구분 합계, `expense` = 지출 + 환불.
- `unpaid_dues`: 활동 회원만. 가입한 달부터 이번 달까지 회비 거래가 없는 달. 미납 달이 없는 회원은 빼낸다. `monthly_dues`가 0이면 빈 목록 (`/api/me/payments`의 `dues`도 빈 목록).
- `balance`와 `totals`는 이월 기준일 다음 날부터, `monthly`는 전체 기간이다. 화면에 이 차이를 표기한다.
- `unpaid_event_fees`: 참가비가 있는 모임의 `confirmed` 신청자 중 해당 모임 `event_fee` 거래가 없는 사람.
- `refunds_needed`: 해당 모임 신청이 취소된 상태이고 (`event_fee` 합계 − `refund` 합계) > 0 인 회원. `amount`는 그 차액.
- `attendance`: 활동 회원 전체. 계산 방식은 `/api/me/attendance`와 같다.

## 장부 거래 구분 (`category`)

| 값 | 의미 | 방향 | 연결 |
| --- | --- | --- | --- |
| `dues` | 회비 | 입금 | 회원 + 회비 대상 월 필수 |
| `event_fee` | 참가비 | 입금 | 회원 + 모임 필수 |
| `other_income` | 기타 수입 | 입금 | 없음 |
| `expense` | 지출 | 출금 | 모임 선택 |
| `refund` | 환불 | 출금 | 회원 + 모임 필수 |

금액은 항상 양수로 저장하고, 방향은 구분으로 정한다.
