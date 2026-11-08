---
name: club-frontend
description: "Club Manager의 Vue 3 + TypeScript + Vite + Tailwind 회원 화면과 운영 대시보드, 프론트엔드 Dockerfile·Caddyfile을 구현하는 방법. club-frontend-dev 에이전트가 화면 작업을 할 때, 또는 Club Manager의 Vue 페이지·라우팅·API 호출·모바일 화면을 고칠 때 사용한다. Django 모델·API·관리자 화면 작업에는 club-backend를 쓴다."
---

# Club Manager 프론트엔드 구현 방법

## 먼저 할 일

1. `ponytail:ponytail` 스킬을 불러온다. 이 프로젝트의 모든 코드는 "가장 작은 완전한 변경" 원칙을 따른다.
2. 계획서 6장(화면 구성), 동작 흐름, API 계약(`.claude/skills/club-manager-dev/references/api-contract.md`)을 읽는다. 백엔드가 같은 계약으로 동시에 개발 중이다. 계약에 없는 필드를 쓰거나 응답을 추측하지 않는다. 계약이 부족하면 보고서에 적는다.

## 기술 선택 (바꾸지 않는다)

- Vite + Vue 3 + TypeScript (`npm create vite@latest frontend -- --template vue-ts`로 시작)
- Tailwind CSS v4 (`@tailwindcss/vite` 플러그인, CSS 파일에 `@import "tailwindcss";` 한 줄)
- Vue Router, Pinia (로그인 사용자 상태 하나에만 쓴다)
- 추가 UI 라이브러리, HTTP 라이브러리(axios 등), 날짜 라이브러리 금지. `fetch`와 `Intl.DateTimeFormat`, `toLocaleString('ko-KR')`로 충분하다.
- PWA 없음.

## 구조

```
frontend/
  Dockerfile  Caddyfile  vite.config.ts  index.html  package.json
  src/
    main.ts  App.vue  router.ts  api.ts  types.ts  auth.ts(Pinia)  format.ts
    pages/  Login.vue  ChangePassword.vue  Home.vue  Events.vue  EventDetail.vue
            Attendance.vue  Payments.vue  Announcements.vue  Me.vue  Dashboard.vue
```

컴포넌트 폴더는 실제로 두 페이지 이상에서 반복되는 조각이 생길 때만 만든다.

## API 호출 (`api.ts`)

- `fetch` 래퍼 함수 하나: 같은 출처 상대 경로(`/api/...`), `credentials: 'same-origin'`, POST에는 `csrftoken` 쿠키를 읽어 `X-CSRFToken` 헤더를 붙인다.
- 실패하면 응답의 `detail`을 메시지로 담은 Error를 던진다. 401/403이면 로그인 화면으로 보낸다.
- `types.ts`의 타입은 계약 문서의 JSON 예시와 필드 이름(snake_case)을 그대로 따른다. 변환 계층을 만들지 않는다.

## 인증과 라우팅

- 앱 시작 시 `GET /api/auth/me`로 사용자 상태를 불러온다 (CSRF 쿠키도 이때 받는다).
- 라우터 가드:
  - 로그인 안 됨 → `/login`
  - `must_change_password` → `/password` 외 접근 금지
  - `/dashboard`는 `is_staff`만
- 운영진에게는 메뉴에 "운영 대시보드"와 관리자 화면 링크(`/club-admin/`, 일반 `<a>` 태그)를 보인다.

## 화면

| 경로 | 화면 | 데이터 |
| --- | --- | --- |
| `/login` | 로그인 | `POST /api/auth/login` |
| `/password` | 비밀번호 변경 | `POST /api/auth/password` |
| `/` | 홈: 최근 공지 3개, 다가오는 모임 3개, 내 신청 현황, 내 미납 내역 | events, announcements, me/payments |
| `/events` | 모임 목록 (예정 / 지난 모임 탭) | `GET /api/events`, `?past=1` |
| `/events/:id` | 모임 상세, 참석자, 신청·취소 버튼, 대기 순번 | 상세, register, cancel |
| `/attendance` | 나의 출석 기록 | me/attendance |
| `/payments` | 나의 회비·참가비 납부 내역 | me/payments |
| `/announcements` | 공지 목록 (펼쳐서 본문 보기) | announcements |
| `/me` | 내 정보, 비밀번호 변경 링크, 로그아웃 | auth/me |
| `/dashboard` | 잔액, 구분별 합계, 월별 표, 미납자, 참가비 미납, 환불 필요, 출석률 | dashboard |

- 신청 버튼을 누르면 응답으로 받은 EventDetail로 화면을 바로 바꾼다. 다시 불러오지 않는다.
- 참가비가 있는 모임에서 확정되면 "모임통장으로 참가비를 이체해 주세요" 안내를 보인다.
- 대시보드는 표와 숫자로만 보여 준다. 차트 라이브러리를 쓰지 않는다.

## 화면 원칙

- 모바일 우선. 기본 레이아웃은 한 열, 하단 또는 상단의 간단한 메뉴. 넓은 화면은 `max-w-2xl mx-auto`로 가운데 정렬.
- 금액은 `10,000원`, 일시는 `11월 20일 (금) 19:00` 형식. 형식 함수는 `format.ts` 한 곳에.
- 로딩·오류 상태를 모든 페이지에 표시한다. 오류는 API의 `detail` 메시지를 그대로 보인다.
- 버튼과 입력에 label을 붙이고, 터치 영역을 충분히(최소 44px) 둔다.

## 개발 서버 프록시 (`vite.config.ts`)

`/api`, `/club-admin`, `/static`을 `http://127.0.0.1:8000`으로 프록시한다. 같은 출처가 되어 세션 쿠키와 CSRF가 그대로 동작한다.

## 배포 파일

- `frontend/Dockerfile`: 1단계 `node:24-alpine`에서 `npm ci && npm run build`, 2단계 `caddy:2-alpine`에 `dist`와 `Caddyfile` 복사.
- `frontend/Caddyfile`:
  - 사이트 주소는 `{$DOMAIN:localhost}` (DOMAIN 환경 변수가 있으면 그 도메인으로 HTTPS 자동 발급)
  - `/api/*`, `/club-admin/*`, `/static/*` → `reverse_proxy django:8000`
  - 나머지 → `dist` 정적 파일, 없는 경로는 `index.html` (Vue Router 히스토리 모드)
  - `encode gzip`

## 검증

```bash
cd frontend
npm install
npm run build        # vue-tsc 타입 검사 포함
```

빌드 출력(성공 여부, 경고)을 보고서에 붙인다. 백엔드가 떠 있으면 `npm run dev`로 로그인부터 신청까지 실제로 눌러 본다.
