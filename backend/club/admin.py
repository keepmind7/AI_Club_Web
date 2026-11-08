from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User

from .models import Announcement, ClubSetting, Event, Member, Registration, Transaction

admin.site.site_header = admin.site.site_title = "Club Manager 관리"


class ResetPasswordForm(AdminPasswordChangeForm):
    """운영진이 관리자 화면에서 비밀번호를 바꾸면 회원은 다음 로그인 때 새로 정해야 한다."""

    def save(self, commit=True):
        user = super().save(commit)
        Member.objects.filter(user=user).update(must_change_password=True)
        return user


class MemberInline(admin.StackedInline):
    model = Member
    can_delete = False


admin.site.unregister(User)


@admin.register(User)
class ClubUserAdmin(UserAdmin):
    inlines = [MemberInline]
    change_password_form = ResetPasswordForm
    list_display = ["username", "member__name", "member__status", "is_staff", "is_active"]


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "phone", "joined_on", "status", "must_change_password"]
    list_filter = ["status"]
    search_fields = ["name", "user__username", "phone"]


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


@admin.register(ClubSetting)
class ClubSettingAdmin(admin.ModelAdmin):
    list_display = ["__str__", "monthly_dues", "carry_over", "carry_over_date"]

    def has_add_permission(self, request):
        return not ClubSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
