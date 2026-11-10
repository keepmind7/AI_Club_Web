"""대기 제도와 참가비를 없앤다 (2026-11-10).
대기 신청은 시작 전 모임이면 확정, 이미 시작한 모임이면 취소로 바꾼다 (참석하지 못한 대기자가 출석률 분모에 들어가지 않게).
참가비 거래는 기타 수입으로, 환불 거래는 지출로 바꾼다. 방향이 같아 잔액은 그대로다.
메모 앞에 원래 구분을 붙여 장부에서 알아볼 수 있게 한다."""
from django.db import migrations, models
from django.utils import timezone

OLD_CATEGORIES = {"event_fee": ("other_income", "[참가비] "), "refund": ("expense", "[환불] ")}


def forwards(apps, schema_editor):
    Registration = apps.get_model("club", "Registration")
    Transaction = apps.get_model("club", "Transaction")
    waiting, now = Registration.objects.filter(status="waitlisted"), timezone.now()
    waiting.filter(event__starts_at__gt=now).update(status="confirmed")
    waiting.filter(event__starts_at__lte=now).update(status="cancelled")
    for t in Transaction.objects.filter(category__in=OLD_CATEGORIES):
        t.category, prefix = OLD_CATEGORIES[t.category]
        t.memo = (prefix + t.memo)[:200].rstrip()  # 메모가 비어 있었으면 "[환불]"
        t.save(update_fields=["category", "memo"])


class Migration(migrations.Migration):

    dependencies = [
        ("club", "0005_member_pending_status"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="event",
            name="fee",
        ),
        migrations.AlterField(
            model_name="registration",
            name="status",
            field=models.CharField(choices=[("confirmed", "확정"), ("cancelled", "취소")], default="confirmed", max_length=10, verbose_name="신청 상태"),
        ),
        migrations.AlterField(
            model_name="transaction",
            name="category",
            field=models.CharField(choices=[("dues", "회비"), ("other_income", "기타 수입"), ("expense", "지출")], max_length=20, verbose_name="구분"),
        ),
    ]
