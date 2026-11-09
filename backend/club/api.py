from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from . import ledger
from .models import Announcement, ClubSetting, Comment, Event, Member, Post, Registration, SharedAccount
from .permissions import ActiveMember

Reg = Registration.Status
LOGIN_LIMIT, LOGIN_WINDOW = 5, 600


def error(message, status=400):
    return Response({"detail": message}, status=status)


def text(request, name):
    """JSON 본문의 문자열 필드. 없거나 문자열이 아니면 빈 문자열."""
    value = request.data.get(name) if isinstance(request.data, dict) else None
    return value if isinstance(value, str) else ""


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
    regs = sorted((r for r in event.registrations.all() if r.status != Reg.CANCELLED), key=lambda r: (r.applied_at, r.id))
    confirmed = [r for r in regs if r.status == Reg.CONFIRMED]
    waiting = [r for r in regs if r.status == Reg.WAITLISTED]
    mine = next((r for r in regs if member and r.member_id == member.id), None)
    data = {
        "id": event.id,
        "title": event.title,
        "starts_at": iso(event.starts_at),
        "place": event.place,
        "capacity": event.capacity,
        "fee": event.fee,
        "confirmed_count": len(confirmed),
        "waitlist_count": len(waiting),
        "my_status": mine.status if mine else None,
    }
    if detail:
        data["description"] = event.description
        data["my_waitlist_position"] = waiting.index(mine) + 1 if mine in waiting else None
        data["attendees"] = [{"name": r.member.name, "status": r.status} for r in confirmed + waiting]
    return data


def events_qs():
    return Event.objects.prefetch_related("registrations__member")


def find_event(qs, pk):
    event = qs.filter(pk=pk).first()
    if event is None:
        raise NotFound("모임을 찾을 수 없습니다.")
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
        return error("로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요.")
    user = authenticate(request, username=username, password=password)
    if user is None:
        return error("아이디 또는 비밀번호가 올바르지 않습니다.")
    with transaction.atomic():  # Windows에서 다른 요청이 파일을 읽는 중 지우면 PermissionError가 나므로 같은 잠금 안에서
        cache.delete(key)
    member = Member.of(user)
    if member and member.status != Member.Status.ACTIVE:
        return error(ActiveMember.message, 403)
    login(request, user)
    return Response(user_data(user))


@api_view(["POST"])
@permission_classes([AllowAny])
def logout_view(request):
    logout(request)
    return Response(status=204)


@api_view(["POST"])
def change_password(request):
    user = request.user
    if not user.check_password(text(request, "old_password")):
        return error("기존 비밀번호가 올바르지 않습니다.")
    new = text(request, "new_password")
    try:
        validate_password(new, user)
    except ValidationError as e:
        return error(" ".join(e.messages))
    user.set_password(new)
    user.save()
    update_session_auth_hash(request, user)
    Member.objects.filter(user=user).update(must_change_password=False)
    return Response(status=204)


# ---- 모임 ----

@api_view(["GET"])
def event_list(request):
    now = timezone.now()
    if request.query_params.get("past") == "1":
        qs = events_qs().filter(starts_at__lte=now).order_by("-starts_at")
    else:
        qs = events_qs().filter(starts_at__gt=now).order_by("starts_at")
    member = Member.of(request.user)
    return Response([event_data(e, member) for e in qs])


@api_view(["GET"])
def event_detail(request, pk):
    return Response(event_data(find_event(events_qs(), pk), Member.of(request.user), detail=True))


@api_view(["POST"])
def event_register(request, pk):
    member = Member.of(request.user)
    if member is None:
        return error("회원 정보가 없는 계정은 신청할 수 없습니다.")
    with transaction.atomic():  # IMMEDIATE 모드: 여기서 쓰기 잠금을 잡아 정원 계산과 저장 사이에 끼어들 수 없다
        event = find_event(Event.objects, pk)
        if event.starts_at <= timezone.now():
            return error("이미 시작한 모임입니다.")
        reg = Registration.objects.filter(event=event, member=member).first()
        if reg and reg.status != Reg.CANCELLED:
            return error("이미 신청한 모임입니다.")
        confirmed = event.registrations.filter(status=Reg.CONFIRMED).count()
        status = Reg.CONFIRMED if event.capacity == 0 or confirmed < event.capacity else Reg.WAITLISTED
        if reg:  # 예전에 취소한 신청을 되살린다
            reg.status, reg.applied_at = status, timezone.now()
            reg.save(update_fields=["status", "applied_at"])
        else:
            Registration.objects.create(event=event, member=member, status=status)
    return Response(event_data(events_qs().get(pk=pk), member, detail=True))


@api_view(["POST"])
def event_cancel(request, pk):
    member = Member.of(request.user)
    with transaction.atomic():
        event = find_event(Event.objects, pk)
        if event.starts_at <= timezone.now():
            return error("이미 시작한 모임입니다.")
        reg = Registration.objects.filter(event=event, member=member).exclude(status=Reg.CANCELLED).first()
        if reg is None:
            return error("신청 내역이 없습니다.")
        reg.status = Reg.CANCELLED
        reg.save(update_fields=["status"])
        event.promote_waitlist()
    return Response(event_data(events_qs().get(pk=pk), member, detail=True))


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
    data = {"monthly_dues": ClubSetting.get().monthly_dues, "dues": [], "event_fees": [], "transactions": []}
    member = Member.of(request.user)
    if member is None:
        return Response(data)
    data["dues"] = [{"month": m, "paid": paid} for m, paid in reversed(ledger.dues_status(member))]
    data["event_fees"] = [
        {"event_id": r.event_id, "title": r.event.title, "starts_at": iso(r.event.starts_at), "fee": r.event.fee, "paid": paid}
        for r, paid in ledger.event_fee_status(member)
    ]
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
    accounts = SharedAccount.objects.all()
    if not request.user.is_staff:
        member = Member.of(request.user)
        accounts = accounts.filter(pk=member.shared_account_id if member else None)
    return Response([
        {"id": a.id, "email": a.email, "password": a.password, "memo": a.memo,
         "members": [{"name": m.name} for m in a.members.filter(status=Member.Status.ACTIVE)]}
        for a in accounts
    ])


# ---- 게시판 ----

def length_error(label, value, limit):
    """value(앞뒤 공백을 뺀 값)가 1~limit자가 아니면 오류 메시지."""
    if not 1 <= len(value) <= limit:
        return f"{label}은 1~{limit}자로 입력하세요."


def post_input(request):
    title, body = text(request, "title").strip(), text(request, "body").strip()
    return title, body, length_error("제목", title, 100) or length_error("본문", body, 5000)


def can_delete(obj, user):
    return obj.author_id == user.id or user.is_staff


def post_data(post, user, detail=False):
    """PostSummary 또는 PostDetail. post는 posts_qs()에서 가져온다."""
    data = {"id": post.id, "title": post.title, "author": Member.name_of(post.author),
            "created_at": iso(post.created_at), "comment_count": post.comment_count}
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
        raise NotFound("글을 찾을 수 없습니다.")
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
        return error("작성자만 수정할 수 있습니다.", 403)
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
        return error("작성자나 운영진만 삭제할 수 있습니다.", 403)
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
        return error("댓글을 찾을 수 없습니다.", 404)
    if not can_delete(comment, request.user):
        return error("작성자나 운영진만 삭제할 수 있습니다.", 403)
    comment.delete()
    return Response(status=204)


# ---- 운영 대시보드 ----

@api_view(["GET"])
@permission_classes([ActiveMember, IsAdminUser])
def dashboard(request):
    # 선택 기간: attendance만 이 기간에 시작한 모임으로 계산한다.
    year, month = request.query_params.get("year"), request.query_params.get("month")
    period = {}
    if year is not None:
        if not (year.isascii() and year.isdigit() and len(year) == 4 and 1900 <= int(year) <= 9998):
            return error("year는 1900~9998 범위의 YYYY 형식이어야 합니다.")
        period["event__starts_at__year"] = int(year)
    if month is not None:
        if year is None or not (month.isascii() and month.isdigit() and 1 <= int(month) <= 12):
            return error("month는 year와 함께 1~12로 지정해야 합니다.")
        period["event__starts_at__month"] = int(month)
    data = ledger.summary()
    active = list(Member.objects.filter(status=Member.Status.ACTIVE))
    data["unpaid_dues"] = []
    for m in active:
        # 마지막 달(이번 달)은 아직 납부 기간이라 미납으로 보지 않는다.
        months = [month for month, paid in ledger.dues_status(m)[:-1] if not paid]
        if months:
            data["unpaid_dues"].append({"member_id": m.id, "name": m.name, "months": months})
    data["unpaid_event_fees"] = [
        {"event_id": r.event_id, "title": r.event.title, "member_id": r.member_id, "name": r.member.name, "fee": r.event.fee}
        for r, paid in ledger.event_fee_status() if not paid
    ]
    data["refunds_needed"] = [
        {"event_id": r.event_id, "title": r.event.title, "member_id": r.member_id, "name": r.member.name, "amount": amount}
        for r, amount in ledger.refunds_needed()
    ]
    data["attendance"] = []
    for m in active:
        a, _ = ledger.attendance(m, **period)
        data["attendance"].append({"member_id": m.id, "name": m.name, "total": a["total"], "present": a["present"], "rate": a["rate"]})
    return Response(data)
