"""장부 계산. 납부 여부·미납·잔액은 저장하지 않고 Transaction에서 계산한다.
회원 화면과 대시보드가 같은 함수를 써서 숫자가 어긋나지 않게 한다."""
from collections import defaultdict

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
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


def dues_paid(**filters):
    """{(회원 id, 'YYYY-MM'): 그 달 회비 합계}. filters로 회원을 좁힌다. 대시보드는 회원 전체를 질의 한 번에."""
    rows = (Transaction.objects.filter(category=Category.DUES, **filters).order_by()
            .values_list("member_id", "dues_month").annotate(total=Sum("amount")))
    return {(m, month): total for m, month, total in rows}


def dues_status(member, monthly_dues=None, paid=None):
    """[(월, 납부 여부)] 가입한 달부터 이번 달까지 오름차순. 월 회비가 0원이면 빈 목록.
    그 달 회비 거래 합계가 현재 월 회비 이상이어야 납부(일부만 냈으면 미납).
    여러 회원을 볼 때는 monthly_dues와 dues_paid() 결과를 넘겨 회원마다 질의하지 않게 한다."""
    if monthly_dues is None:
        monthly_dues = ClubSetting.get().monthly_dues
    if not monthly_dues:
        return []
    if paid is None:
        paid = dues_paid(member=member)
    return [(month, paid.get((member.id, month), 0) >= monthly_dues) for month in month_range(member.joined_on)]


def counted_regs(**filters):
    """출석률에 넣는 신청: 이미 시작한 모임의 확정 신청. 기간은 event__starts_at__year/month 필터."""
    return Registration.objects.filter(status=Reg.Status.CONFIRMED, event__starts_at__lte=timezone.now(), **filters)


def rate(present, total):
    """출석률 %. 정수 사사오입 (파이썬 round는 짝수 쪽으로 반올림한다)."""
    return (present * 200 + total) // (2 * total) if total else None


def attendance(member, **period):
    """한 회원의 (요약 dict, 신청 목록 최신순)."""
    regs = list(counted_regs(member=member, **period).select_related("event").order_by("-event__starts_at"))
    total = len(regs)
    present = sum(r.attendance == Reg.Attendance.PRESENT for r in regs)
    absent = sum(r.attendance == Reg.Attendance.ABSENT for r in regs)
    return {"total": total, "present": present, "absent": absent, "rate": rate(present, total)}, regs


def attendance_counts(**filters):
    """{회원 id: (신청 수, 출석 수)}. 대시보드가 회원 전체를 질의 한 번에 센다."""
    rows = (counted_regs(**filters).order_by().values_list("member_id")
            .annotate(total=Count("id"), present=Count("id", filter=Q(attendance=Reg.Attendance.PRESENT))))
    return {m: (total, present) for m, total, present in rows}


def summary():
    """잔액, 이월 잔액, 구분별 합계(이월 기준일 이후), 월별 수입·지출(전체, 최신순)."""
    setting = ClubSetting.get()
    # 합계는 DB가 낸다 (거래를 한 줄씩 불러오지 않는다). 결과는 구분 수, 달 수 × 구분 수 줄뿐이다.
    txs = Transaction.objects.order_by()
    since = {} if setting.carry_over_date is None else {"date__gt": setting.carry_over_date}
    totals = {c: 0 for c in Category.values}
    totals.update(txs.filter(**since).values_list("category").annotate(total=Sum("amount")))
    monthly = defaultdict(lambda: {"income": 0, "expense": 0})
    for month, category, total in txs.annotate(month=TruncMonth("date")).values_list("month", "category").annotate(total=Sum("amount")):
        monthly[f"{month:%Y-%m}"]["income" if category in Transaction.INCOME else "expense"] += total
    balance = setting.carry_over + sum(totals[c] for c in Transaction.INCOME) - totals[Category.EXPENSE]
    return {
        "balance": balance,
        "carry_over": setting.carry_over,
        "totals": totals,
        "monthly": [{"month": k, **v} for k, v in sorted(monthly.items(), reverse=True)],
    }
