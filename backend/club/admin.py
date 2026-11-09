from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import Group, User
from django.db.models import Count
from django.utils.html import format_html

from .models import Announcement, ClubSetting, Comment, Event, Member, Post, Registration, SharedAccount, Transaction

admin.site.site_header = admin.site.site_title = "Club Manager 관리"


class ResetPasswordForm(AdminPasswordChangeForm):
    """운영진이 관리자 화면에서 비밀번호를 바꾸면 회원은 다음 로그인 때 새로 정해야 한다."""

    def save(self, commit=True):
        user = super().save(commit)
        Member.objects.filter(user=user).update(must_change_password=True)
        return user


def apply_status_change(form):
    """휴면·탈퇴로 바뀌면 시작 전 모임 신청을 취소하고 대기자를 승격한다."""
    if "status" in form.changed_data and form.instance.status != Member.Status.ACTIVE:
        form.instance.cancel_upcoming()


class MemberInline(admin.StackedInline):
    model = Member
    can_delete = False


admin.site.unregister(User)
admin.site.unregister(Group)  # 권한은 '운영자' 체크 하나로 충분하다.


@admin.register(User)
class ClubUserAdmin(UserAdmin):
    inlines = [MemberInline]
    change_password_form = ResetPasswordForm
    list_display = ["username", "member__name", "member_status", "operator", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["username", "member__name"]
    fieldsets = [
        (None, {"fields": ["username", "password"]}),
        ("권한", {"fields": ["is_active", "is_staff"]}),
        ("기록", {"fields": ["last_login", "date_joined"]}),
    ]

    @admin.display(description="상태", ordering="member__status")
    def member_status(self, obj):
        member = Member.of(obj)
        return member and member.get_status_display()

    @admin.display(boolean=True, description="운영자", ordering="is_staff")
    def operator(self, obj):
        return obj.is_staff

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "is_staff":
            kwargs.update(label="운영자", help_text="체크하면 관리자 화면과 운영 대시보드를 모두 쓸 수 있습니다.")
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        obj.is_superuser = obj.is_staff  # 운영자 = 모든 권한
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        for f in formset.forms:
            apply_status_change(f)


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "phone", "joined_on", "status", "must_change_password"]
    list_filter = ["status"]
    search_fields = ["name", "user__username", "phone"]

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
        help_text="회원 한 명은 공유 계정 하나에만 속합니다. 다른 계정에 있던 회원을 고르면 이 계정으로 옮겨집니다.",
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

    @admin.display(description="쓰는 회원")
    def member_names(self, obj):
        return ", ".join(m.name for m in obj.members.all())

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # 고른 회원은 이 계정으로(다른 계정에서 옮겨 옴), 선택에서 뺀 회원은 계정 없음으로.
        form.instance.members.set(form.cleaned_data["members"])


class RegistrationInline(admin.TabularInline):
    model = Registration
    extra = 0
    fields = ["member", "status", "attendance", "applied_at"]
    autocomplete_fields = ["member"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "starts_at", "place", "capacity", "fee"]
    search_fields = ["title"]
    date_hierarchy = "starts_at"
    inlines = [RegistrationInline]

    def save_related(self, request, form, formsets, change):
        # 신청 취소·상태 변경·정원 증가로 빈 자리가 생기면 대기자를 승격한다 (관리자 화면 저장은 트랜잭션 안).
        super().save_related(request, form, formsets, change)
        form.instance.promote_waitlist()


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["date", "category", "amount", "member", "event", "dues_month", "memo", "created_by"]
    list_filter = ["category", "date"]
    date_hierarchy = "date"
    search_fields = ["memo", "member__name"]
    autocomplete_fields = ["member", "event"]
    readonly_fields = ["created_by"]

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


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
    list_display = ["__str__", "monthly_dues", "carry_over", "carry_over_date"]

    def has_add_permission(self, request):
        return not ClubSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
