import re

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import ledger
from .models import Announcement, ClubSetting, Comment, Event, Member, Post, Registration, SharedAccount
from .permissions import ActiveMember, StaffOnly

Reg = Registration.Status
LOGIN_LIMIT, LOGIN_WINDOW = 5, 600
# Django 비밀번호 검증 오류(합니다체)를 화면과 같은 해요체로. 여기 없는 코드는 검증기 메시지 그대로
# (club.validators.ClubPasswordValidator는 처음부터 계약 문구라 여기 없다).
PASSWORD_MESSAGES = {
    "password_too_common": "너무 흔한 비밀번호예요. 다른 걸로 정해 주세요.",
    "password_too_similar": "아이디나 이메일과 너무 비슷해요.",
}
# 계약 고정 문구. "이용이 제한"을 넣지 않는다 (프론트가 이용 제한 화면으로 보내지 않게).
PENDING_MESSAGE = "가입 승인을 기다리고 있어요. 운영진이 승인하면 로그인할 수 있어요."
USERNAME_TAKEN = "이미 쓰고 있는 아이디예요."


def check_username(raw):
    """가입과 아이디 중복 확인이 같이 쓴다. (정규화한 아이디, 오류 문구 또는 None)
    Django 회원 계정 추가 화면과 같은 규칙: NFKC 정규화(전각 ｂｏｓｓ → boss), 대소문자만 달라도 중복."""
    username = User.normalize_username(raw.strip())
    if len(username) > 150 or not re.fullmatch(r"[\w.@+-]+", username):
        return username, "아이디는 150자 이하로, 글자·숫자와 @ . + - _ 만 써 주세요."
    if User.objects.filter(username__iexact=username).exists():
        return username, USERNAME_TAKEN
    return username, None


def phone_ok(phone):
    """숫자와 하이픈만, 숫자 10~11자리. 20자는 DB 칸 길이."""
    return len(phone) <= 20 and re.fullmatch(r"[0-9-]+", phone) and 10 <= sum(c.isdigit() for c in phone) <= 11


def email_ok(email):
    try:
        EmailValidator()(email)
    except ValidationError:
        return False
    return len(email) <= 254


def error(message, status=400):
    return Response({"detail": message}, status=status)


def text(request, name):
    """JSON 본문의 문자열 필드. 없거나 문자열이 아니면 빈 문자열."""
    value = request.data.get(name) if isinstance(request.data, dict) else None
    return value if isinstance(value, str) else ""


def password_error(password, user):
    """Django 비밀번호 규칙을 어기면 해요체 메시지, 지키면 None."""
    try:
        validate_password(password, user)
    except ValidationError as e:
        return " ".join(
            PASSWORD_MESSAGES[x.code].format(**(x.params or {})) if x.code in PASSWORD_MESSAGES else x.messages[0]
            for x in e.error_list)


def iso(dt):
    return timezone.localtime(dt).isoformat()


def user_data(user):
    member = Member.of(user)
    return {
        "id": user.id,
        "username": user.username,
        "name": Member.name_of(user),
        "is_staff": user.is_staff,
        "must_change_password": member.must_change_password if member else False,
        "phone": member.phone if member else None,
        "joined_on": member.joined_on.isoformat() if member else None,
    }


def event_data(event, member, detail=False):
    """EventSummary 또는 EventDetail. event.registrations는 member까지 prefetch해 둔다."""
    regs = sorted((r for r in event.registrations.all() if r.status == Reg.CONFIRMED), key=lambda r: (r.applied_at, r.id))
    mine = next((r for r in regs if member and r.member_id == member.id), None)
    data = {
        "id": event.id,
        "title": event.title,
        "starts_at": iso(event.starts_at),
        "place": event.place,
        "capacity": event.capacity,
        "confirmed_count": len(regs),  # 정원보다 많을 수 있다 (정원은 기준 인원)
        "my_status": Reg.CONFIRMED if mine else None,
        # 출석률과 같은 기준: 이미 시작한 모임의 확정 신청만
        "my_attendance": mine.attendance if mine and event.starts_at <= timezone.now() else None,
    }
    if detail:
        data["description"] = event.description
        data["attendees"] = [{"name": r.member.name} for r in regs]
    return data


def events_qs(detail=False):
    # 목록은 신청 수와 내 신청만 보므로 회원까지 불러오지 않는다. 신청자 이름은 상세에서만.
    return Event.objects.prefetch_related("registrations__member" if detail else "registrations")


def find_event(qs, pk):
    event = qs.filter(pk=pk).first()
    if event is None:
        raise NotFound("모임을 찾을 수 없어요.")
    return event


# ---- 인증 ----

@ensure_csrf_cookie  # 403 응답에도 csrftoken 쿠키를 심는다
@api_view(["GET"])
def me(request):
    return Response(user_data(request.user))


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    username, password = text(request, "username"), text(request, "password")
    # 실패 횟수는 파일 캐시(settings.CACHES)에 두어 gunicorn 워커가 같은 값을 본다.
    # 비밀번호 확인 전에 시도 1회를 먼저 기록하고(맞으면 지운다), 그 읽기-쓰기를 IMMEDIATE 트랜잭션의
    # DB 쓰기 잠금으로 워커 사이에서 직렬화한다. 잠금은 해시 계산 동안 잡지 않는다.
    # 실패할 때마다 10분 창을 새로 연다: 실패 간격이 10분 미만으로 5회 이어지면 마지막 실패부터 10분 잠금.
    # (파일 캐시의 incr는 만료 시각을 기본값으로 덮어써서 쓰지 않는다)
    key = f"login-fail:{username}"
    with transaction.atomic():
        fails = cache.get(key, 0)
        if fails < LOGIN_LIMIT:
            cache.set(key, fails + 1, LOGIN_WINDOW)
    if fails >= LOGIN_LIMIT:
        return error("로그인 시도가 너무 많아요. 10분 뒤에 다시 시도해 주세요.")
    user = authenticate(request, username=username, password=password)
    if user is None:
        return error("아이디나 비밀번호가 맞지 않아요.")
    with transaction.atomic():  # Windows에서 다른 요청이 파일을 읽는 중 지우면 PermissionError가 나므로 같은 잠금 안에서
        cache.delete(key)
    member = Member.of(user)
    if member and member.status == Member.Status.PENDING:
        return error(PENDING_MESSAGE, 403)
    if not ActiveMember.allows(user):
        return error(ActiveMember.message, 403)
    login(request, user)
    return Response(user_data(user))


@api_view(["POST"])
@permission_classes([AllowAny])
def signup(request):
    """회원이 직접 가입한다. 승인 대기로 만들고 로그인시키지 않는다. 운영진이 관리자 화면에서 승인한다."""
    try:  # DRF는 로그인 안 한 요청의 CSRF를 검사하지 않아 직접 검사한다.
        SessionAuthentication().enforce_csrf(request)
    except PermissionDenied:
        return error("보안 확인에 실패했어요. 화면을 새로고침한 뒤 다시 시도해 주세요.", 403)
    username, message = check_username(text(request, "username"))
    password = text(request, "password")
    name, phone, email = (text(request, f).strip() for f in ("name", "phone", "email"))
    user = User(username=username, email=email)
    message = (message or password_error(password, user) or length_error("이름", name, 50)
               or (None if phone_ok(phone) else "연락처는 010-1234-5678처럼 숫자로 써 주세요.")
               or (None if email_ok(email) else "이메일 주소를 확인해 주세요."))
    if message:
        return error(message)
    user.set_password(password)  # 해시 계산은 쓰기 잠금 밖에서
    try:
        with transaction.atomic():
            user.save()
            Member.objects.create(user=user, name=name, phone=phone,
                                  status=Member.Status.PENDING, must_change_password=False)
    except IntegrityError:  # 같은 아이디로 동시에 가입한 경우
        return error(USERNAME_TAKEN)
    return Response({"detail": "가입 신청이 접수됐어요. 운영진이 승인하면 로그인할 수 있어요."}, status=201)


@api_view(["GET"])
@permission_classes([AllowAny])
def username_check(request):
    """가입 화면의 아이디 중복 확인. 안내일 뿐이고 가입 때 다시 검사한다. 항상 200."""
    _, message = check_username(request.query_params.get("username", ""))
    return Response({"available": message is None, "detail": message or "쓸 수 있는 아이디예요."})


@api_view(["POST"])
@permission_classes([AllowAny])
def logout_view(request):
    logout(request)
    return Response(status=204)


@api_view(["POST"])
def change_password(request):
    user = request.user
    if not user.check_password(text(request, "old_password")):
        return error("현재 비밀번호가 맞지 않아요.")
    new = text(request, "new_password")
    message = password_error(new, user)
    if message:
        return error(message)
    user.set_password(new)
    user.save()
    update_session_auth_hash(request, user)
    Member.objects.filter(user=user).update(must_change_password=False)
    return Response(status=204)


# ---- 모임 ----

@api_view(["GET"])
def event_list(request):
    now = timezone.now()
    month = request.query_params.get("month")
    if month is None:
        qs = events_qs().filter(starts_at__gt=now)
    else:  # 그 달(서울 시각)에 이미 시작한 모임. __year/__month는 settings.TIME_ZONE 기준이다.
        m = re.fullmatch(r"([0-9]{4})-(0[1-9]|1[0-2])", month)
        if not m or not 1900 <= int(m[1]) <= 9998:
            return error("month는 YYYY-MM 형식이어야 해요.")
        qs = events_qs().filter(starts_at__lte=now, starts_at__year=int(m[1]), starts_at__month=int(m[2]))
    qs = qs.order_by("starts_at")
    member = Member.of(request.user)
    return Response([event_data(e, member) for e in qs])


@api_view(["GET"])
def event_detail(request, pk):
    return Response(event_data(find_event(events_qs(detail=True), pk), Member.of(request.user), detail=True))


@api_view(["POST"])
def event_register(request, pk):
    member = Member.of(request.user)
    if member is None:
        return error("회원 정보가 없는 운영진 계정이에요. 관리자 화면의 회원 계정에서 이 아이디에 회원 정보를 넣으면 신청할 수 있어요.")
    # 정원과 관계없이 항상 확정. IMMEDIATE 모드: 여기서 쓰기 잠금을 잡아 같은 회원이 동시에 눌러도 신청은 하나다.
    with transaction.atomic():
        event = find_event(Event.objects, pk)
        if event.starts_at <= timezone.now():
            return error("이미 시작한 모임이에요.")
        reg = Registration.objects.filter(event=event, member=member).first()
        if reg and reg.status != Reg.CANCELLED:
            return error("이미 신청한 모임이에요.")
        if reg:  # 예전에 취소한 신청을 되살린다
            reg.status, reg.applied_at = Reg.CONFIRMED, timezone.now()
            reg.save(update_fields=["status", "applied_at"])
        else:
            Registration.objects.create(event=event, member=member, status=Reg.CONFIRMED)
    return Response(event_data(events_qs(detail=True).get(pk=pk), member, detail=True))


@api_view(["POST"])
def event_cancel(request, pk):
    member = Member.of(request.user)
    with transaction.atomic():
        event = find_event(Event.objects, pk)
        if event.starts_at <= timezone.now():
            return error("이미 시작한 모임이에요.")
        reg = Registration.objects.filter(event=event, member=member).exclude(status=Reg.CANCELLED).first()
        if reg is None:
            return error("신청 내역이 없어요.")
        reg.status = Reg.CANCELLED
        reg.save(update_fields=["status"])
    return Response(event_data(events_qs(detail=True).get(pk=pk), member, detail=True))


# ---- 내 정보 ----

@api_view(["GET"])
def my_attendance(request):
    member = Member.of(request.user)
    if member is None:
        return Response({"total": 0, "present": 0, "absent": 0, "rate": None, "records": []})
    data, regs = ledger.attendance(member)
    data["records"] = [
        {"event_id": r.event_id, "title": r.event.title, "starts_at": iso(r.event.starts_at), "attendance": r.attendance}
        for r in regs
    ]
    return Response(data)


@api_view(["GET"])
def my_payments(request):
    data = {"monthly_dues": ClubSetting.get().monthly_dues, "dues": [], "transactions": []}
    member = Member.of(request.user)
    if member is None:
        return Response(data)
    data["dues"] = [{"month": m, "paid": paid} for m, paid in reversed(ledger.dues_status(member))]
    data["transactions"] = [
        {"date": t.date.isoformat(), "category": t.category, "amount": t.amount, "memo": t.memo}
        for t in member.transactions.order_by("-date", "-id")
    ]
    return Response(data)


# ---- 공지 ----

@api_view(["GET"])
def announcements(request):
    return Response([
        {"id": a.id, "title": a.title, "body": a.body, "created_at": iso(a.created_at)}
        for a in Announcement.objects.all()
    ])


# ---- 공유 계정 ----

@api_view(["GET"])
def shared_accounts(request):
    accounts = SharedAccount.objects.prefetch_related(Prefetch("members", Member.objects.filter(status=Member.Status.ACTIVE)))
    if not request.user.is_staff:
        member = Member.of(request.user)
        accounts = accounts.filter(pk=member.shared_account_id if member else None)
    return Response([
        {"id": a.id, "email": a.email, "password": a.password, "memo": a.memo,
         "members": [{"name": m.name} for m in a.members.all()]}
        for a in accounts
    ])


# ---- 게시판 ----

def length_error(label, value, limit):
    """value(앞뒤 공백을 뺀 값)가 1~limit자가 아니면 오류 메시지."""
    if not 1 <= len(value) <= limit:
        return f"{label}은 1~{limit}자로 써 주세요."


def post_input(request):
    title, body = text(request, "title").strip(), text(request, "body").strip()
    return title, body, length_error("제목", title, 100) or length_error("본문", body, 5000)


def excerpt(body, limit=80):
    """연속 공백·줄바꿈을 공백 하나로 줄인 앞 limit자. 넘치면 '…'."""
    flat = " ".join(body.split())
    return flat[:limit].rstrip() + "…" if len(flat) > limit else flat


def can_delete(obj, user):
    return obj.author_id == user.id or user.is_staff


def post_data(post, user, detail=False):
    """PostSummary 또는 PostDetail. post는 posts_qs()에서 가져온다."""
    data = {"id": post.id, "title": post.title, "author": Member.name_of(post.author),
            "created_at": iso(post.created_at), "comment_count": post.comment_count, "excerpt": excerpt(post.body)}
    if detail:
        data.update(body=post.body, updated_at=iso(post.updated_at),
                    can_edit=post.author_id == user.id, can_delete=can_delete(post, user), comments=[
                        {"id": c.id, "author": Member.name_of(c.author), "body": c.body,
                         "created_at": iso(c.created_at), "can_delete": can_delete(c, user)}
                        for c in post.comments.select_related("author__member")])
    return data


def posts_qs():
    # GROUP BY 쿼리에는 Meta.ordering이 적용되지 않아 정렬을 직접 준다.
    return (Post.objects.select_related("author__member").annotate(comment_count=Count("comments"))
            .order_by("-created_at", "-id"))


def find_post(pk):
    post = posts_qs().filter(pk=pk).first()
    if post is None:
        raise NotFound("글을 찾을 수 없어요.")
    return post


@api_view(["GET", "POST"])
def posts(request):
    if request.method == "GET":
        return Response([post_data(p, request.user) for p in posts_qs()])
    title, body, message = post_input(request)
    if message:
        return error(message)
    post = Post.objects.create(author=request.user, title=title, body=body)
    return Response(post_data(find_post(post.pk), request.user, detail=True), status=201)


@api_view(["GET"])
def post_detail(request, pk):
    return Response(post_data(find_post(pk), request.user, detail=True))


@api_view(["POST"])
def post_edit(request, pk):
    post = find_post(pk)
    if post.author_id != request.user.id:  # 운영진도 남의 글은 고칠 수 없다
        return error("작성자만 수정할 수 있어요.", 403)
    post.title, post.body, message = post_input(request)
    if message:
        return error(message)
    post.updated_at = timezone.now()
    post.save(update_fields=["title", "body", "updated_at"])
    return Response(post_data(find_post(pk), request.user, detail=True))


@api_view(["POST"])
def post_delete(request, pk):
    post = find_post(pk)
    if not can_delete(post, request.user):
        return error("작성자나 운영진만 삭제할 수 있어요.", 403)
    post.delete()  # 댓글도 함께 지워진다 (CASCADE)
    return Response(status=204)


@api_view(["POST"])
def comment_create(request, pk):
    post = find_post(pk)
    body = text(request, "body").strip()
    message = length_error("댓글", body, 1000)
    if message:
        return error(message)
    Comment.objects.create(post=post, author=request.user, body=body)
    return Response(post_data(find_post(pk), request.user, detail=True), status=201)


@api_view(["POST"])
def comment_delete(request, pk):
    comment = Comment.objects.filter(pk=pk).first()
    if comment is None:
        return error("댓글을 찾을 수 없어요.", 404)
    if not can_delete(comment, request.user):
        return error("작성자나 운영진만 삭제할 수 있어요.", 403)
    comment.delete()
    return Response(status=204)


# ---- 운영 대시보드 ----

@api_view(["GET"])
@permission_classes([ActiveMember, StaffOnly])
def dashboard(request):
    # 선택 기간: attendance만 이 기간에 시작한 모임으로 계산한다.
    year, month = request.query_params.get("year"), request.query_params.get("month")
    period = {}
    if year is not None:
        if not (year.isascii() and year.isdigit() and len(year) == 4 and 1900 <= int(year) <= 9998):
            return error("year는 1900~9998 범위의 YYYY 형식이어야 해요.")
        period["event__starts_at__year"] = int(year)
    if month is not None:
        if year is None or not (month.isascii() and month.isdigit() and 1 <= int(month) <= 12):
            return error("month는 year와 함께 1~12로 지정해야 해요.")
        period["event__starts_at__month"] = int(month)
    data = ledger.summary()
    active = list(Member.objects.filter(status=Member.Status.ACTIVE))
    # 회원마다 질의하지 않고 활동 회원 전체의 회비·출석을 한 번씩만 센다.
    monthly_dues = ClubSetting.get().monthly_dues
    paid = ledger.dues_paid(member__status=Member.Status.ACTIVE)
    counts = ledger.attendance_counts(member__status=Member.Status.ACTIVE, **period)
    data["unpaid_dues"] = []
    for m in active:
        # 마지막 달(이번 달)은 아직 납부 기간이라 미납으로 보지 않는다.
        months = [month for month, ok in ledger.dues_status(m, monthly_dues, paid)[:-1] if not ok]
        if months:
            data["unpaid_dues"].append({"member_id": m.id, "name": m.name, "months": months})
    data["attendance"] = []
    for m in active:
        total, present = counts.get(m.id, (0, 0))
        data["attendance"].append({"member_id": m.id, "name": m.name, "total": total, "present": present,
                                   "rate": ledger.rate(present, total)})
    data["pending_signups"] = Member.objects.filter(status=Member.Status.PENDING).count()
    return Response(data)
