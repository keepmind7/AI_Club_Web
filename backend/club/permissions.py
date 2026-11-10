from rest_framework.permissions import BasePermission, IsAdminUser

from .models import Member


class ActiveMember(BasePermission):
    """로그인 + 활동 상태. 로그인 API도 allows()로 같은 판단을 한다."""

    message = "이용이 제한된 계정이에요. 운영진에게 문의해 주세요."

    @staticmethod
    def allows(user):
        """Member 기록이 없으면 운영진만 활동으로 본다. 운영진이 아닌데 Member가 없는 계정
        (가입 거절 때 회원 정보만 지운 경우 등)은 휴면·탈퇴처럼 막는다."""
        member = Member.of(user)
        return user.is_staff if member is None else member.status == Member.Status.ACTIVE

    def has_permission(self, request, view):
        return request.user.is_authenticated and self.allows(request.user)


class StaffOnly(IsAdminUser):
    message = "운영진만 볼 수 있어요."
