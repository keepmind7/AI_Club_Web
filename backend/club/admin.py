from django import forms
from django.apps import apps
from django.contrib import admin, messages
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm, UserCreationForm
from django.contrib.auth.models import Group, User
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Announcement, ClubSetting, Comment, Event, Member, Post, Registration, SharedAccount, Transaction

# 화면 색·문구 틀은 backend/templates/admin/ 에서 바꾼다. 여기서는 이름과 메뉴만.
admin.site.site_header = admin.site.site_title = "Mythos 관리"
admin.site.site_url = "/staff"  # 왼쪽 위 [‹ 운영 화면]이 돌아가는 곳: 회원 앱 운영 탭 (관리자 화면 바로가기가 모인 곳)
admin.site.index_title = "관리 메뉴"
# 운영진이 보는 이름. Meta가 아니라 실행 중 값만 바꾸므로 django.contrib.auth에 마이그레이션이 생기지 않는다.
User._meta.verbose_name = User._meta.verbose_name_plural = "회원 계정"
apps.get_app_config("auth").verbose_name = "동아리"

MENU = ["User", "Member", "Event", "Transaction", "Announcement", "Post", "SharedAccount", "ClubSetting"]


def get_app_list(request, app_label=None):
    """첫 화면·옆 메뉴: 회원 계정까지 '동아리' 한 묶음에, 자주 쓰는 순서로."""
    groups = admin.AdminSite.get_app_list(admin.site, request, app_label)
    club = next((g for g in groups if g["app_label"] == "club"), None)
    if app_label or not club:
        return groups
    models = [m for g in groups for m in g["models"]]
    models.sort(key=lambda m: MENU.index(m["object_name"]) if m["object_name"] in MENU else len(MENU))
    return [{**club, "models": models}]


admin.site.get_app_list = get_app_list


def index(request, extra_context=None):
    """첫 화면 바로 가기에 승인 대기 회원 수를 보여 준다 (templates/admin/index.html)."""
    pending = Member.objects.filter(status=Member.Status.PENDING).count()
    return admin.AdminSite.index(admin.site, request, {"pending_signups": pending, **(extra_context or {})})


admin.site.index = index


def won(amount):
    return f"{amount:,}원"


def help_texts(**texts):
    """모델 help_text를 관리자 화면에서만 바꾼다 (모델을 고치면 마이그레이션이 생긴다)."""
    return type("HelpTextForm", (forms.ModelForm,), {"Meta": type("Meta", (), {"help_texts": texts})})


def simplify_password_fields(form):
    """'비밀번호 기반 인증' 선택(SSO·LDAP용)을 빼고, 비밀번호 칸 두 개와 짧은 안내만 남긴다."""
    form.fields.pop("usable_password", None)
    p1, p2 = form.fields["password1"], form.fields["password2"]
    p1.required = p2.required = True
    p1.help_text = ("8자 이상으로, 영문·숫자·특수문자를 모두 넣어 주세요. 특수문자로 시작할 수 없고, "
                    "흔한 것이나 아이디와 비슷한 것도 쓸 수 없어요.")
    p2.help_text = "한 번 더 입력해 주세요."


class AddUserForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        simplify_password_fields(self)


class ResetPasswordForm(AdminPasswordChangeForm):
    """운영진이 관리자 화면에서 비밀번호를 바꾸면 회원은 다음 로그인 때 새로 정해야 한다."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        simplify_password_fields(self)

    def save(self, commit=True):
        user = super().save(commit)
        Member.objects.filter(user=user).update(must_change_password=True)
        return user


def apply_status_change(form):
    """회원·회원 계정 화면에서 상태를 바꿔 저장한 뒤 호출한다. 승인 대기 → 활동이면 가입일을 승인한 날로
    (회원 목록의 '가입 승인' 액션도 같은 규칙: MemberAdmin.approve_signups),
    휴면·탈퇴로 바뀌면 시작 전 모임 신청을 취소한다."""
    member = form.instance
    if "status" not in form.changed_data:
        return
    if member.status == Member.Status.ACTIVE and form.initial.get("status") == Member.Status.PENDING:
        member.joined_on = timezone.localdate()
        member.save(update_fields=["joined_on"])
    elif member.status != Member.Status.ACTIVE:
        member.cancel_upcoming()


MemberForm = help_texts(must_change_password="켜 두면 다음 로그인 때 새 비밀번호를 정하게 해요.")


class MemberInline(admin.StackedInline):
    model = Member
    form = MemberForm
    can_delete = False
    verbose_name = verbose_name_plural = "회원 정보"


admin.site.unregister(User)
admin.site.unregister(Group)  # 권한은 '운영진' 체크 하나로 충분하다.


@admin.register(User)
class ClubUserAdmin(UserAdmin):
    inlines = [MemberInline]
    add_form = AddUserForm
    change_password_form = ResetPasswordForm
    list_display = ["login_id", "name", "email", "member_status", "operator", "can_login"]
    list_select_related = ["member"]  # 이름·상태 칸이 줄마다 회원을 따로 읽지 않게
    list_filter = ["member__status"]
    show_facets = admin.ShowFacets.NEVER  # 필터 옆 '개수 표시' 버튼을 숨긴다
    search_fields = ["username", "member__name", "email"]
    add_fieldsets = [(None, {"fields": ["username", "email", "password1", "password2"]})]
    fieldsets = [
        (None, {"fields": ["username", "email", "password_reset"]}),
        ("권한", {"fields": ["is_active", "is_staff"]}),
        ("기록", {"fields": ["last_login", "date_joined"]}),
    ]
    readonly_fields = ["password_reset", "last_login", "date_joined"]
    LABELS = {
        "username": ("아이디", "글자, 숫자와 @ . + - _ 만 쓸 수 있어요."),
        "email": ("이메일", "운영진이 만드는 계정은 비워도 돼요."),
        "is_active": ("로그인 허용", "끄면 이 아이디로 로그인할 수 없어요. 계정을 지우는 대신 이 칸을 꺼 주세요."),
        "is_staff": ("운영진", "체크하면 관리자 화면과 운영 대시보드를 모두 쓸 수 있어요."),
    }

    @admin.display(description="아이디", ordering="username")
    def login_id(self, obj):
        return obj.username

    @admin.display(description="이름", ordering="member__name")
    def name(self, obj):
        member = Member.of(obj)
        return member and member.name

    @admin.display(boolean=True, description="로그인 허용", ordering="is_active")
    def can_login(self, obj):
        return obj.is_active

    @admin.display(description="비밀번호")
    def password_reset(self, obj):
        return format_html(
            '<a class="button" href="{}">비밀번호 초기화</a>'
            '<br><span class="mini quiet">회원은 다음 로그인 때 비밀번호를 다시 정해요.</span>',
            reverse("admin:auth_user_password_change", args=[obj.pk]))

    @admin.display(description="상태", ordering="member__status")
    def member_status(self, obj):
        member = Member.of(obj)
        return member and member.get_status_display()

    @admin.display(boolean=True, description="운영진", ordering="is_staff")
    def operator(self, obj):
        return obj.is_staff

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in self.LABELS:
            kwargs["label"], kwargs["help_text"] = self.LABELS[db_field.name]
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        obj.is_superuser = obj.is_staff  # 운영진 = 모든 권한
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        for f in formset.forms:
            apply_status_change(f)


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    form = MemberForm
    list_display = ["name", "user", "email", "phone", "joined_on", "status"]
    list_editable = ["status"]  # 목록에서 바로 바꾸고 '저장'. 승인 대기 → 활동이면 가입일이 오늘로 (save_model)
    list_select_related = ["user"]
    search_fields = ["name", "user__username", "user__email", "phone"]
    actions = ["approve_signups"]

    @admin.display(description="이메일", ordering="user__email")
    def email(self, obj):
        return obj.user.email

    @admin.action(description="가입 승인")
    def approve_signups(self, request, queryset):
        """고른 회원 중 승인 대기만 활동으로. 가입일은 승인한 날(회비는 그 달부터)."""
        count = queryset.filter(status=Member.Status.PENDING).update(
            status=Member.Status.ACTIVE, joined_on=timezone.localdate())
        if count:
            self.message_user(request, f"{count}명을 승인했어요. 이제 로그인할 수 있어요.")
        else:
            self.message_user(request, "고른 회원 중 승인 대기인 회원이 없어요.", messages.WARNING)

    def has_add_permission(self, request):
        return False  # 회원은 회원 계정 추가 화면에서 아이디와 함께 만든다 (templates/admin/club/member/change_list.html)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        apply_status_change(form)


class WrappedFilteredSelectMultiple(FilteredSelectMultiple):
    """SelectFilter2.js가 위젯을 부모 맨 앞에 넣으므로, Django가 하듯 div로 감싸야 라벨 뒤에 그려진다."""

    def render(self, *args, **kwargs):
        return format_html('<div class="related-widget-wrapper">{}</div>', super().render(*args, **kwargs))


class SharedAccountForm(forms.ModelForm):
    members = forms.ModelMultipleChoiceField(
        Member.objects.select_related("shared_account"), required=False, label="쓰는 회원",
        widget=WrappedFilteredSelectMultiple("회원", False),
        help_text="회원 한 명은 공유 계정 하나에만 속해요. 다른 계정에 있던 회원을 고르면 이 계정으로 옮겨져요.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["members"].initial = self.instance.members.all()
        # 다른 계정에 속한 회원은 그 계정을 붙여 보여 준다: "박민수 (club.team2@gmail.com)"
        self.fields["members"].label_from_instance = lambda m: (
            f"{m.name} ({m.shared_account.email})" if m.shared_account_id not in (None, self.instance.pk) else m.name)


@admin.register(SharedAccount)
class SharedAccountAdmin(admin.ModelAdmin):
    form = SharedAccountForm
    list_display = ["email", "memo", "member_names"]
    search_fields = ["email", "memo"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("members")  # '쓰는 회원' 칸

    @admin.display(description="쓰는 회원")
    def member_names(self, obj):
        return ", ".join(m.name for m in obj.members.all())

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # 고른 회원은 이 계정으로(다른 계정에서 옮겨 옴), 선택에서 뺀 회원은 계정 없음으로.
        form.instance.members.set(form.cleaned_data["members"])


class DateHourMinuteWidget(forms.MultiWidget):
    """날짜(달력) + 시(0~23시) + 분(5분 단위). Django 기본 시계는 '지금·자정·오전 6시·정오·오후 6시'만 골라진다.
    세 칸을 'YYYY-MM-DD HH:MM' 한 줄로 합쳐 forms.DateTimeField가 그대로 읽는다.
    좁은 화면에서 Django가 폼 칸을 세로로 쌓으므로 div.hm-row로 감싸 늘 한 줄에 둔다 (templates/admin/base_site.html)."""

    def __init__(self):
        blank = [("", "--")]
        super().__init__([
            forms.DateInput(attrs={"type": "date", "aria-label": "날짜"}, format="%Y-%m-%d"),
            forms.Select(attrs={"aria-label": "시"}, choices=blank + [(f"{h:02d}", f"{h}시") for h in range(24)]),
            forms.Select(attrs={"aria-label": "분"}, choices=blank + [(f"{m:02d}", f"{m:02d}분") for m in range(0, 60, 5)]),
        ])

    def render(self, *args, **kwargs):
        return format_html('<div class="hm-row">{}</div>', super().render(*args, **kwargs))

    def decompress(self, value):
        if isinstance(value, str):  # 오류로 다시 그릴 때는 value_from_datadict가 합친 "날짜 시:분" (일부가 빌 수 있음)
            day, _, hour_minute = value.partition(" ")
            hour, _, minute = hour_minute.partition(":")
            return [day or None, hour, minute]
        if not value:
            return [None, "", ""]
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        minute = f"{value.minute:02d}"
        if minute not in dict(self.widgets[2].choices):  # 5분 단위가 아닌 예전 값도 그대로 보이게
            self.widgets[2].choices = [*self.widgets[2].choices, (minute, f"{minute}분")]
        return [value.date(), f"{value.hour:02d}", minute]

    def value_from_datadict(self, data, files, name):
        """'날짜 시:분'으로 합친다. 셋 다 비면 "" (필수 오류). 일부만 고르면 DateTimeField가 형식 오류로 돌려보내고,
        decompress가 이 문자열을 다시 나눠 오류 화면에 고른 값을 남긴다."""
        values = super().value_from_datadict(data, files, name)
        return "{} {}:{}".format(*values) if any(values) else ""


class EventForm(help_texts(capacity="넘게 신청해도 받아요. 목록에 넘친 인원이 빨갛게 보여요. 0이면 정원이 없어요.")):
    starts_at = forms.DateTimeField(label="일시", widget=DateHourMinuteWidget(), error_messages={
        "required": "날짜, 시, 분을 모두 골라 주세요.", "invalid": "날짜, 시, 분을 모두 골라 주세요."})


class RegistrationInline(admin.TabularInline):
    model = Registration
    extra = 0
    fields = ["member", "status", "attendance", "applied_at"]
    readonly_fields = ["applied_at"]
    autocomplete_fields = ["member"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    form = EventForm
    list_display = ["title", "starts_at", "place", "capacity_text"]
    search_fields = ["title"]
    date_hierarchy = "starts_at"
    inlines = [RegistrationInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            applied=Count("registrations", filter=Q(registrations__status=Registration.Status.CONFIRMED)))

    @admin.display(description="신청 / 정원", ordering="applied")
    def capacity_text(self, obj):
        """API 계약의 화면 표기: 23 / 20명 (넘치면 빨갛게 + (+3명)), 정원 0이면 23명 · 정원 없음."""
        if not obj.capacity:
            return f"{obj.applied}명 · 정원 없음"
        text = f"{obj.applied} / {obj.capacity}명"
        if obj.applied <= obj.capacity:
            return text
        return format_html('<span style="color: var(--error-fg)">{} (+{}명)</span>', text, obj.applied - obj.capacity)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    form = help_texts(
        category="회비는 회원과 회비 대상 월을 꼭 넣어요. 지출은 어느 모임에 쓴 돈인지 골라 둘 수 있어요.",
        amount="원 단위 숫자만 써요. 들어온 돈인지 나간 돈인지는 구분으로 정해져요.",
        dues_month="회비일 때만 써요. 예: 2026-11. 여러 달을 한 번에 냈으면 달마다 한 줄씩 넣어요.",
    )
    list_display = ["date", "category", "amount_text", "member", "event", "dues_month", "memo", "creator"]
    list_select_related = ["member", "event", "created_by__member"]  # 입력자 칸까지 한 번에
    list_filter = ["category", "date"]
    show_facets = admin.ShowFacets.NEVER
    date_hierarchy = "date"
    search_fields = ["memo", "member__name"]
    autocomplete_fields = ["member", "event"]
    readonly_fields = ["created_by"]

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="금액", ordering="amount")
    def amount_text(self, obj):
        return won(obj.amount)

    @admin.display(description="입력자", ordering="created_by__member__name")
    def creator(self, obj):
        return obj.created_by and Member.name_of(obj.created_by)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ["title", "created_at"]
    search_fields = ["title", "body"]


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = readonly_fields = ["author", "body", "created_at"]  # 운영진은 지우기만 한다

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["title", "author_name", "created_at", "comment_count"]
    list_select_related = ["author__member"]
    search_fields = ["title", "body"]
    readonly_fields = ["author"]
    inlines = [CommentInline]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="작성자", ordering="author__member__name")
    def author_name(self, obj):
        return Member.name_of(obj.author)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(comment_count=Count("comments"))

    @admin.display(description="댓글 수", ordering="comment_count")
    def comment_count(self, obj):
        return obj.comment_count


@admin.register(ClubSetting)
class ClubSettingAdmin(admin.ModelAdmin):
    form = help_texts(
        monthly_dues="한 명이 한 달에 내는 금액이에요. 원 단위로 써요.",
        carry_over="이 앱으로 장부를 옮기기 전에 남아 있던 돈이에요.",
        carry_over_date="이 날짜가 끝났을 때 잔액이 이월 잔액이에요. 다음 날부터의 거래만 더해요. 비우면 모든 거래를 더해요.",
    )
    list_display = ["__str__", "monthly_dues_text", "carry_over_text", "carry_over_date"]

    @admin.display(description="월 회비")
    def monthly_dues_text(self, obj):
        return won(obj.monthly_dues)

    @admin.display(description="이월 잔액")
    def carry_over_text(self, obj):
        return won(obj.carry_over)

    def has_add_permission(self, request):
        return not ClubSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
