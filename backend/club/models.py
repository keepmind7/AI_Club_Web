from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone


class Member(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "활동"
        DORMANT = "dormant", "휴면"
        WITHDRAWN = "withdrawn", "탈퇴"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="member", verbose_name="계정")
    name = models.CharField("이름", max_length=50)
    phone = models.CharField("연락처", max_length=20, blank=True)
    joined_on = models.DateField("가입일", default=timezone.localdate)
    status = models.CharField("상태", max_length=10, choices=Status.choices, default=Status.ACTIVE)
    must_change_password = models.BooleanField("비밀번호 변경 필요", default=True)

    class Meta:
        verbose_name = verbose_name_plural = "회원"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @staticmethod
    def of(user):
        """user의 Member, 없으면 None (운영진·슈퍼유저 계정)."""
        return getattr(user, "member", None)

    def cancel_upcoming(self):
        """휴면·탈퇴 처리: 시작 전 모임 신청(확정·대기)을 모두 취소하고 빈 자리를 대기자로 채운다."""
        regs = list(self.registrations.filter(event__starts_at__gt=timezone.now())
                    .exclude(status=Registration.Status.CANCELLED).select_related("event"))
        for r in regs:
            r.status = Registration.Status.CANCELLED
            r.save(update_fields=["status"])
        for event in {r.event for r in regs}:
            event.promote_waitlist()


class Event(models.Model):
    title = models.CharField("제목", max_length=100)
    description = models.TextField("설명", blank=True)
    starts_at = models.DateTimeField("일시")
    place = models.CharField("장소", max_length=100, blank=True)
    capacity = models.PositiveIntegerField("정원", default=0, help_text="0이면 정원 제한 없음")
    fee = models.PositiveIntegerField("참가비", default=0, help_text="원 단위. 0이면 무료")

    class Meta:
        verbose_name = verbose_name_plural = "모임"
        ordering = ["-starts_at"]

    def __str__(self):
        return f"{timezone.localtime(self.starts_at):%Y-%m-%d} {self.title}"

    def promote_waitlist(self):
        """시작 전 모임이면 먼저 신청한 대기자부터 정원까지 확정으로 올린다(정원 0이면 모두).
        신청 취소, 정원 증가, 관리자 화면 저장 뒤 호출한다. 호출하는 쪽의 트랜잭션 안에서 실행된다."""
        if self.starts_at <= timezone.now():
            return
        regs = self.registrations
        waiting = regs.filter(status=Registration.Status.WAITLISTED).order_by("applied_at", "id")
        if self.capacity:
            waiting = waiting[:max(self.capacity - regs.filter(status=Registration.Status.CONFIRMED).count(), 0)]
        regs.filter(pk__in=[r.pk for r in waiting]).update(status=Registration.Status.CONFIRMED)


class Registration(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "확정"
        WAITLISTED = "waitlisted", "대기"
        CANCELLED = "cancelled", "취소"

    class Attendance(models.TextChoices):
        UNKNOWN = "unknown", "미확인"
        PRESENT = "present", "출석"
        ABSENT = "absent", "결석"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="registrations", verbose_name="모임")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="registrations", verbose_name="회원")
    status = models.CharField("신청 상태", max_length=10, choices=Status.choices)
    attendance = models.CharField("출석", max_length=10, choices=Attendance.choices, default=Attendance.UNKNOWN)
    applied_at = models.DateTimeField("신청 시각", default=timezone.now)

    class Meta:
        verbose_name = verbose_name_plural = "참석 신청"
        ordering = ["applied_at", "id"]
        constraints = [models.UniqueConstraint(fields=["event", "member"], name="unique_registration")]

    def __str__(self):
        return f"{self.member} - {self.event}"


class Transaction(models.Model):
    class Category(models.TextChoices):
        DUES = "dues", "회비"
        EVENT_FEE = "event_fee", "참가비"
        OTHER_INCOME = "other_income", "기타 수입"
        EXPENSE = "expense", "지출"
        REFUND = "refund", "환불"

    INCOME = (Category.DUES, Category.EVENT_FEE, Category.OTHER_INCOME)
    # 구분별 필수 연결 (API 계약의 장부 거래 구분 표)
    REQUIRED = {
        Category.DUES: ("member", "dues_month"),
        Category.EVENT_FEE: ("member", "event"),
        Category.REFUND: ("member", "event"),
    }

    date = models.DateField("거래일", default=timezone.localdate)
    category = models.CharField("구분", max_length=20, choices=Category.choices)
    amount = models.PositiveIntegerField("금액", validators=[MinValueValidator(1)], help_text="원 단위 양수. 방향은 구분으로 정한다")
    # PROTECT: 장부에 연결된 회원·모임을 지우면 금액 계산이 조용히 바뀌므로 막는다.
    member = models.ForeignKey(Member, on_delete=models.PROTECT, null=True, blank=True, related_name="transactions", verbose_name="회원")
    event = models.ForeignKey(Event, on_delete=models.PROTECT, null=True, blank=True, related_name="transactions", verbose_name="모임")
    dues_month = models.CharField(
        "회비 대상 월", max_length=7, blank=True,
        validators=[RegexValidator(r"^\d{4}-(0[1-9]|1[0-2])$", "YYYY-MM 형식으로 입력하세요. 예: 2026-11")],
        help_text="회비만. YYYY-MM. 여러 달 선납은 달마다 한 줄",
    )
    memo = models.CharField("메모", max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="입력자")

    class Meta:
        verbose_name = verbose_name_plural = "장부 거래"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.date} {self.get_category_display()} {self.amount:,}원"

    def clean(self):
        attrs = {"member": self.member_id, "event": self.event_id, "dues_month": self.dues_month}
        missing = {f: "이 구분에는 필수입니다." for f in self.REQUIRED.get(self.category, ()) if not attrs[f]}
        if missing:
            raise ValidationError(missing)


class Announcement(models.Model):
    title = models.CharField("제목", max_length=200)
    body = models.TextField("내용")
    created_at = models.DateTimeField("작성일", auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = "공지"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title


class ClubSetting(models.Model):
    monthly_dues = models.PositiveIntegerField("월 회비", default=0)
    carry_over = models.IntegerField("이월 잔액", default=0)
    carry_over_date = models.DateField(
        "이월 기준일", null=True, blank=True,
        help_text="이 날짜가 끝났을 때의 잔액이 이월 잔액. 다음 날부터의 거래만 잔액에 더한다. 비우면 모든 거래를 더한다.",
    )

    class Meta:
        verbose_name = verbose_name_plural = "운영 설정"

    def __str__(self):
        return "운영 설정"

    @classmethod
    def get(cls):
        return cls.objects.get_or_create(pk=1)[0]
