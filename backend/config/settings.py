import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_list(name, default=""):
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


# 로컬 개발 기본값은 DEBUG=1. 운영(docker-compose)은 DEBUG=0으로 고정한다.
DEBUG = os.environ.get("DEBUG", "1") == "1"
SECRET_KEY = os.environ.get("SECRET_KEY") or ("dev-only-insecure-key" if DEBUG else "")
if not SECRET_KEY:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("운영 모드(DEBUG=0)에서는 .env에 SECRET_KEY를 설정해야 합니다.")
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "club",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # 관리자 화면 템플릿 덮어쓰기 (Django 기본보다 먼저 찾는다)
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "data" / "db.sqlite3"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DB_PATH,
        # 트랜잭션 시작 때 쓰기 잠금을 잡아 동시 신청에도 정원을 넘지 않게 한다.
        "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 20},
        # 테스트도 파일 DB를 써야 동시 신청 테스트가 실제 잠금을 검사한다.
        "TEST": {"NAME": DB_PATH.parent / "test_db.sqlite3"},
    }
}

# 로그인 실패 횟수용. 파일 캐시라 gunicorn 워커들이 같은 값을 보고, 추가 패키지·테이블이 필요 없다.
# 워커 사이 읽기-쓰기 경합은 api.login_view가 DB 쓰기 잠금(IMMEDIATE 트랜잭션) 안에서 처리해 막는다.
# MAX_ENTRIES: 기본 300개를 넘으면 오래된 기록을 지우므로 넉넉히 둔다.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
                      "LOCATION": DB_PATH.parent / "cache", "OPTIONS": {"MAX_ENTRIES": 10000}}}

# 관리자 화면에서 로그아웃하면 Django 기본 안내 대신 회원 앱 로그인 화면으로 보낸다.
LOGOUT_REDIRECT_URL = "/login"

# 기본 PBKDF2(100만 회 반복)는 로그인 한 번에 1.5초 넘게 걸려서 Django 내장 scrypt를 쓴다 (이 PC 기준 1.6초 → 0.5초, 16MB, OWASP 권장 값).
# 둘째 줄은 예전 비밀번호 확인용: 그 회원이 다음에 로그인할 때 scrypt로 자동으로 바꿔 저장된다.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.ScryptPasswordHasher",
                    "django.contrib.auth.hashers.PBKDF2PasswordHasher"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    # 길이·숫자만 검사는 이 검증기가 함께 한다 (MinimumLength·Numeric를 같이 두면 같은 뜻의 문구가 두 번 나온다)
    {"NAME": "club.validators.ClubPasswordValidator"},
]

LANGUAGE_CODE = "ko-kr"
# 관리자 화면의 어색한 Django 기본 번역을 고친 것 (locale/ko/LC_MESSAGES/django.po)
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["club.permissions.ActiveMember"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
}

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Caddy가 HTTPS를 끝내고 X-Forwarded-Proto로 알려준다.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if sys.argv[1:2] == ["test"]:  # manage.py test 일 때만 (createsuperuser --username test 등은 제외)
    # 테스트마다 계정을 만들어서 기본 해시(수십만 회 반복)로는 테스트가 1분 넘게 걸린다.
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    # 테스트가 cache.clear()로 운영·개발 캐시를 지우지 않게 따로 둔다.
    CACHES["default"]["LOCATION"] = DB_PATH.parent / "test_cache"
