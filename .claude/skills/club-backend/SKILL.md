---
name: club-backend
description: "Club Manager의 Django 백엔드(모델, Django Admin, DRF API, 권한, 장부 계산, 테스트)와 배포 파일(backend Dockerfile, docker-compose, .env.example, README)을 구현하는 방법. club-backend-dev 에이전트가 백엔드 작업을 할 때, 또는 Club Manager의 API·모델·관리자 화면·장부 계산을 고칠 때 사용한다. Vue 화면 작업에는 club-frontend를 쓴다."
---

# Club Manager 백엔드 구현 방법

## 먼저 할 일

1. `ponytail:ponytail` 스킬을 불러온다. 이 프로젝트의 모든 코드는 "가장 작은 완전한 변경" 원칙을 따른다.
2. 계획서, 동작 흐름, API 계약(`.claude/skills/club-manager-dev/references/api-contract.md`)을 읽는다. 계약과 다르게 만들어야 하면 구현하지 말고 보고서에 적는다. 프론트엔드가 같은 계약을 보고 동시에 개발 중이기 때문이다.

## 기술 선택 (바꾸지 않는다)

| 항목 | 선택 | 이유 |
| --- | --- | --- |
| Django | 5.2 LTS | SQLite `transaction_mode` 옵션(5.1+)과 장기 지원 |
| API | Django REST Framework | 세션 인증·CSRF·권한 클래스가 기본 제공 |
| DB | SQLite, 경로는 환경 변수 `DB_PATH` (기본 `backend/data/db.sqlite3`) | 서버 이전 시 파일 하나만 복사 |
| 정적 파일 | whitenoise | 관리자 화면 CSS를 Django가 직접 제공해 Caddy와 볼륨 공유가 필요 없다 |
| 실행 | gunicorn, 워커 2개 | 1GB 메모리 서버 기준 |
| 의존성 | `backend/requirements.txt` | Docker와 로컬 모두 `pip install -r`로 끝난다 |

설정: `TIME_ZONE = "Asia/Seoul"`, `LANGUAGE_CODE = "ko-kr"`(관리자 화면이 한국어가 된다), `USE_TZ = True`.
SQLite `OPTIONS = {"transaction_mode": "IMMEDIATE"}`: 트랜잭션 시작 시점에 쓰기 잠금을 잡아 동시 신청에도 정원이 넘지 않게 한다.
환경 변수: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DB_PATH`. 운영에서는 `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`를 켠다(`DEBUG`가 꺼져 있을 때).

## 구조

```
backend/
  manage.py  requirements.txt  Dockerfile
  config/    settings.py urls.py wsgi.py
  club/      models.py admin.py api.py ledger.py tests.py
             management/commands/backup_db.py
```

앱은 `club` 하나로 둔다. 30명 규모에서 앱을 나누면 파일만 늘어난다. 파일이 400줄을 넘을 때만 나눈다.

## 모델

| 모델 | 필드 |
| --- | --- |
| `Member` | `user`(OneToOne), `name`, `phone`, `joined_on`(date), `status`(active/dormant/withdrawn), `must_change_password`(기본 True) |
| `Event` | `title`, `description`, `starts_at`, `place`, `capacity`(0=무제한), `fee`(0=무료) |
| `Registration` | `event`, `member`, `status`(confirmed/waitlisted/cancelled), `attendance`(unknown/present/absent), `applied_at`. (`event`, `member`) 유일 |
| `Transaction` | `date`, `category`(계약의 5가지), `amount`(양의 정수), `member`(null), `event`(null), `dues_month`(char 7, 빈 값 허용), `memo`, `created_by`(User) |
| `Announcement` | `title`, `body`, `created_at` |
| `ClubSetting` | `monthly_dues`, `carry_over`, `carry_over_date`. 한 행만 쓴다 (`ClubSetting.get()`이 없으면 만들어 반환) |

`Transaction.clean()`에서 계약 표의 필수 연결(회비는 회원+월 등)을 검증한다. 관리자 화면에서 잘못 입력하는 것을 막는 유일한 장치다.

## 관리자 화면 (운영진 업무 대부분)

- `User` 관리 화면에 `Member` 인라인을 붙인다. 계정 생성과 회원 정보를 한곳에서 처리한다.
- 운영진이 다른 사람의 비밀번호를 바꾸면 `must_change_password = True`가 되게 한다 (UserAdmin의 비밀번호 변경 처리 지점 하나에서).
- `Event` 관리 화면에 `Registration` 인라인(상태, 출석 편집 가능)을 붙인다. 출석 체크를 이 화면에서 한다.
- `Transaction`: 목록 필터(구분, 월), 검색(메모, 회원 이름), 저장 시 `created_by` 자동 기록, "저장 후 다른 거래 추가"를 그대로 쓴다.
- 관리자 경로는 `/club-admin/`.

새 화면을 만들지 말고 Django Admin 옵션(`list_display`, `list_filter`, `inlines`, `autocomplete_fields`)으로 해결한다.

## API

- 계약의 경로·필드·상태 코드를 그대로 따른다. 함수형 뷰(`@api_view`) + 직렬화는 dict로 직접 만든다. 엔드포인트가 열몇 개뿐이라 ViewSet·Serializer 계층은 코드만 늘린다.
- 권한 클래스 하나(`ActiveMember`)로 "로그인 + 활동 상태"를 검사하고 기본 권한으로 지정한다. 운영진 전용은 `is_staff` 확인을 추가한다.
- `/api/auth/me`에 `ensure_csrf_cookie`를 붙인다.
- 로그인 실패 제한은 Django 캐시(기본 로컬 메모리)에 아이디별 횟수를 저장한다. 별도 패키지를 쓰지 않는다.
- 신청·취소·승격은 `transaction.atomic()` 블록 하나 안에서 처리한다.

## 장부 계산 (`ledger.py`)

납부 여부·미납·잔액·환불 필요 건은 저장하지 않고 `Transaction`에서 계산한다. 회원 화면과 대시보드가 같은 함수를 써야 숫자가 어긋나지 않는다. 계산식은 계약 문서의 대시보드 절을 따른다. 30명 규모이므로 쿼리 최적화보다 읽기 쉬운 코드를 우선한다.

## 백업

`python manage.py backup_db`: `sqlite3` 표준 라이브러리의 `backup()`으로 `data/backups/db-YYYYMMDD.sqlite3`를 만들고 최근 7개만 남긴다. 실행 중에도 안전하게 복사된다.

## 배포 파일 (루트)

- `backend/Dockerfile`: `python:3.12-slim`, requirements 설치, `collectstatic`, 시작 시 `migrate` 후 gunicorn.
- `docker-compose.yml`: `django`(backend), `caddy`(frontend/Dockerfile로 빌드, 80·443 공개, `caddy_data` 볼륨, `DOMAIN` 환경 변수 전달). `./data`를 django의 DB 경로에 마운트. `restart: unless-stopped`.
- `.env.example`: 필요한 환경 변수와 설명 한 줄씩.
- `.gitignore`: `data/`, `.env`, `.venv/`, `node_modules/`, `dist/`, `__pycache__/`, `_workspace*/`.
- `README.md`: 로컬 개발 실행, 운영 서버 최초 설정(스왑 2GB, Docker 설치, `.env`, `docker compose up -d --build`, 관리자 계정 생성, 백업 cron 한 줄), 배포(`git pull` + `up -d --build`), 서버 이전. 짧게 쓴다.

## 테스트 (`club/tests.py`)

로직이 있는 곳만 테스트한다.
- 권한: 비로그인 401/403, 휴면 회원 403, 일반 회원의 대시보드 403
- 신청: 정원 안 → confirmed, 정원 초과 → waitlisted, 정원 0 → 항상 confirmed, 중복 신청 400
- 취소: 확정자 취소 시 첫 대기자 승격, 대기자 취소 시 승격 없음, 재신청 시 기존 행 재사용
- 장부: 잔액 계산, 회비 미납 달, 참가비 미납, 환불 필요 건
- 비밀번호 변경 후 `must_change_password` false, 로그인 실패 제한

실행: `python manage.py test club`. 결과 출력을 보고서에 붙인다.

## 로컬 실행 (Windows + Git Bash)

```bash
cd backend
uv venv .venv && uv pip install -r requirements.txt --python .venv
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py test club
.venv/Scripts/python manage.py runserver 8000
```
