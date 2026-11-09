from rest_framework.permissions import BasePermission

from .models import Member


class ActiveMember(BasePermission):
    """로그인 + 활동 상태. Member 기록이 없는 운영진·슈퍼유저 계정은 활동 회원으로 본다."""

    message = "이용이 제한된 계정이에요. 운영진에게 문의해 주세요."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        member = Member.of(request.user)
        return member is None or member.status == Member.Status.ACTIVE
