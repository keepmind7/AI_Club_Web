"""장부 계산. 납부 여부·미납·잔액은 저장하지 않고 Transaction에서 계산한다.
회원 화면과 대시보드가 같은 함수를 써서 숫자가 어긋나지 않게 한다."""
from collections import defaultdict

from django.utils import timezone

from .models import ClubSetting, Registration, Transaction

Category = Transaction.Category
Reg = Registration


def month_range(start):
    """start가 속한 달부터 이번 달까지 'YYYY-MM' 오름차순."""
    today = timezone.localdate()
    y, m = start.year, start.month
    months = []
    while (y, m) <= (today.year, today.month):
        months.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months


def dues_status(member):
    """[(월, 납부 여부)] 가입한 달부터 이번 달까지 오름차순. 월 회비가 0원이면 빈 목록.
    그 달 회비 거래 합계가 현재 월 회비 이상이어야 납부(일부만 냈으면 미납)."""
    monthly_dues = ClubSetting.get().monthly_dues
    if not monthly_dues:
        return []
    paid = defaultdict(int)
    for month, amount in member.transactions.filter(category=Category.DUES).values_list("dues_month", "amount"):
        paid[month] += amount
    return [(month, paid[month] >= monthly_dues) for month in month_range(member.joined_on)]


def attendance(member, **period):
    """이미 시작한 모임 중 확정 신청만. period는 event__starts_at__year/month 필터. (요약 dict, 신청 목록 최신순)"""
    regs = list(member.registrations.filter(status=Reg.Status.CONFIRMED, event__starts_at__lte=timezone.now(), **period)
                .select_related("event").order_by("-event__starts_at"))
    total = len(regs)
    present = sum(r.attendance == Reg.Attendance.PRESENT for r in regs)
    absent = sum(r.attendance == Reg.Attendance.ABSENT for r in regs)
    # 정수 사사오입 (파이썬 round는 짝수 쪽으로 반올림한다)
    rate = (present * 200 + total) // (2 * total) if total else None
    return {"total": total, "present": present, "absent": absent, "rate": rate}, regs


def summary():
    """잔액, 이월 잔액, 구분별 합계(이월 기준일 이후), 월별 수입·지출(전체, 최신순)."""
    setting = ClubSetting.get()
    totals = {c: 0 for c in Category.values}
    monthly = defaultdict(lambda: {"income": 0, "expense": 0})
    for t in Transaction.objects.all():
        monthly[t.date.strftime("%Y-%m")]["income" if t.category in Transaction.INCOME else "expense"] += t.amount
        if setting.carry_over_date is None or t.date > setting.carry_over_date:
            totals[t.category] += t.amount
    balance = setting.carry_over + sum(totals[c] for c in Transaction.INCOME) - totals[Category.EXPENSE]
    return {
        "balance": balance,
        "carry_over": setting.carry_over,
        "totals": totals,
        "monthly": [{"month": k, **v} for k, v in sorted(monthly.items(), reverse=True)],
    }
