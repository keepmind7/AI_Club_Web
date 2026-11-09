import re

from django.core.exceptions import ValidationError


class ClubPasswordValidator:
    """8자 이상, 영문·숫자·특수문자(영문·숫자·공백이 아닌 문자) 각 하나 이상, 첫 글자 특수문자 금지.
    settings.AUTH_PASSWORD_VALIDATORS에 걸어 가입·비밀번호 변경·관리자 화면·createsuperuser가 모두 따른다.
    문구가 API 계약 문구 그대로라 API도 이 메시지를 그대로 쓴다."""

    SPECIAL = r"[^A-Za-z0-9\s]"

    def validate(self, password, user=None):
        errors = []
        if not (len(password) >= 8 and re.search(r"[A-Za-z]", password) and re.search(r"[0-9]", password)
                and re.search(self.SPECIAL, password)):
            errors.append(ValidationError("비밀번호는 8자 이상으로, 영문·숫자·특수문자를 모두 넣어 주세요.",
                                          code="password_too_weak"))
        if re.match(self.SPECIAL, password):
            errors.append(ValidationError("비밀번호는 특수문자로 시작할 수 없어요.", code="password_starts_with_special"))
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return "8자 이상으로, 영문·숫자·특수문자를 모두 넣어 주세요. 특수문자로 시작할 수는 없어요."
