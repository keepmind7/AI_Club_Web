import sqlite3
import tempfile
import threading
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Announcement, ClubSetting, Event, Member, Registration, Transaction

C = Transaction.Category
PW = "Club-pass-2026!"


def make_member(username, status=Member.Status.ACTIVE, staff=False, joined_on=None, name=None):
    user = User.objects.create_user(username, password=PW, is_staff=staff)
    return Member.objects.create(user=user, name=name or username, status=status,
                                 joined_on=joined_on or timezone.localdate())


def make_event(days=7, capacity=0, fee=0, title="모임"):
    return Event.objects.create(title=title, starts_at=timezone.now() + timedelta(days=days), capacity=capacity, fee=fee)


def client_for(member_or_user):
    c = APIClient()
    c.force_login(getattr(member_or_user, "user", member_or_user))
    return c


def prev_month(d):
    first = d.replace(day=1)
    return (first - timedelta(days=1)).replace(day=1)


class AuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.member = make_member("hong", name="홍길동")

    def test_anonymous_is_rejected_and_me_sets_csrf_cookie(self):
        c = APIClient()
        self.assertIn(c.get("/api/events").status_code, (401, 403))
        res = c.get("/api/auth/me")
        self.assertIn(res.status_code, (401, 403))
        self.assertIn("csrftoken", res.cookies)

    def test_login_and_me(self):
        c = APIClient()
        res = c.post("/api/auth/login", {"username": "hong", "password": PW}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"id": self.member.user.id, "username": "hong", "name": "홍길동",
                                      "is_staff": False, "must_change_password": True,
                                      "phone": "", "joined_on": timezone.localdate().isoformat()})
        self.assertEqual(c.get("/api/auth/me").status_code, 200)
        self.assertEqual(c.post("/api/auth/logout").status_code, 204)
        self.assertIn(c.get("/api/auth/me").status_code, (401, 403))

    def test_wrong_password_400(self):
        res = APIClient().post("/api/auth/login", {"username": "hong", "password": "x"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("detail", res.json())

    def test_login_rate_limit(self):
        c = APIClient()
        for _ in range(5):
            c.post("/api/auth/login", {"username": "hong", "password": "wrong"}, format="json")
        res = c.post("/api/auth/login", {"username": "hong", "password": PW}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"], "로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요.")
        # 다른 아이디는 영향 없음
        make_member("kim")
        self.assertEqual(c.post("/api/auth/login", {"username": "kim", "password": PW}, format="json").status_code, 200)

    def test_dormant_member(self):
        dormant = make_member("sleep", status=Member.Status.DORMANT)
        res = APIClient().post("/api/auth/login", {"username": "sleep", "password": PW}, format="json")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["detail"], "이용이 제한된 계정입니다. 운영진에게 문의하세요.")  # 계약 고정 문구, 프론트가 이 문구로 판별
        c = client_for(dormant)  # 로그인 후 휴면으로 바뀐 경우
        self.assertEqual(c.get("/api/events").status_code, 403)
        self.assertEqual(c.get("/api/me/payments").status_code, 403)
        res = c.get("/api/auth/me")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["detail"], "이용이 제한된 계정입니다. 운영진에게 문의하세요.")  # 계약 고정 문구, 프론트가 이 문구로 판별
        self.assertIn("csrftoken", res.cookies)
        self.assertEqual(c.post("/api/auth/logout").status_code, 204)

    def test_change_password(self):
        c = client_for(self.member)
        bad_old = c.post("/api/auth/password", {"old_password": "x", "new_password": "Another-pass-99"}, format="json")
        self.assertEqual(bad_old.status_code, 400)
        weak = c.post("/api/auth/password", {"old_password": PW, "new_password": "1234"}, format="json")
        self.assertEqual(weak.status_code, 400)
        res = c.post("/api/auth/password", {"old_password": PW, "new_password": "Another-pass-99"}, format="json")
        self.assertEqual(res.status_code, 204)
        self.member.refresh_from_db()
        self.assertFalse(self.member.must_change_password)
        self.assertEqual(c.get("/api/auth/me").status_code, 200)  # 로그인 유지

    def test_admin_password_reset_sets_must_change(self):
        Member.objects.filter(pk=self.member.pk).update(must_change_password=False)
        admin = User.objects.create_superuser("boss", password=PW)
        c = APIClient()
        c.force_login(admin)
        res = c.post(f"/club-admin/auth/user/{self.member.user.id}/password/",
                     {"password1": "Reset-pass-2026", "password2": "Reset-pass-2026"})
        self.assertEqual(res.status_code, 302)
        self.member.refresh_from_db()
        self.assertTrue(self.member.must_change_password)

    def test_staff_without_member(self):
        boss = User.objects.create_user("boss", password=PW, is_staff=True)
        c = client_for(boss)
        me = c.get("/api/auth/me").json()
        self.assertEqual((me["name"], me["is_staff"], me["must_change_password"], me["phone"], me["joined_on"]),
                         ("boss", True, False, None, None))
        self.assertEqual(c.get("/api/dashboard").status_code, 200)
        pay = c.get("/api/me/payments").json()
        self.assertEqual(pay, {"monthly_dues": 0, "dues": [], "event_fees": [], "transactions": []})

    def test_dashboard_staff_only(self):
        self.assertEqual(client_for(self.member).get("/api/dashboard").status_code, 403)


class EventTests(TestCase):
    def setUp(self):
        self.a, self.b, self.c = make_member("a"), make_member("b"), make_member("c")

    def register(self, member, event):
        return client_for(member).post(f"/api/events/{event.id}/register")

    def cancel(self, member, event):
        return client_for(member).post(f"/api/events/{event.id}/cancel")

    def statuses(self, event):
        return {r.member.user.username: r.status for r in event.registrations.select_related("member__user")}

    def test_capacity_and_waitlist(self):
        e = make_event(capacity=2)
        self.assertEqual(self.register(self.a, e).json()["my_status"], "confirmed")
        self.assertEqual(self.register(self.b, e).json()["my_status"], "confirmed")
        res = self.register(self.c, e).json()
        self.assertEqual((res["my_status"], res["my_waitlist_position"]), ("waitlisted", 1))
        self.assertEqual((res["confirmed_count"], res["waitlist_count"]), (2, 1))
        self.assertEqual([x["status"] for x in res["attendees"]], ["confirmed", "confirmed", "waitlisted"])
        self.assertEqual(self.register(self.a, e).status_code, 400)  # 중복 신청

    def test_unlimited_capacity(self):
        e = make_event(capacity=0)
        for m in (self.a, self.b, self.c):
            self.assertEqual(self.register(m, e).json()["my_status"], "confirmed")

    def test_started_event(self):
        e = make_event(days=-1)
        self.assertEqual(self.register(self.a, e).status_code, 400)
        self.assertEqual(self.cancel(self.a, e).status_code, 400)

    def test_cancel_confirmed_promotes_first_waiter(self):
        e = make_event(capacity=1)
        d = make_member("d")
        for m in (self.a, self.b, self.c, d):
            self.register(m, e)
        res = self.cancel(self.a, e)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.json()["my_status"])
        self.assertEqual(self.statuses(e), {"a": "cancelled", "b": "confirmed", "c": "waitlisted", "d": "waitlisted"})

    def test_cancel_waiter_does_not_promote(self):
        e = make_event(capacity=1)
        for m in (self.a, self.b, self.c):
            self.register(m, e)
        self.cancel(self.b, e)
        self.assertEqual(self.statuses(e), {"a": "confirmed", "b": "cancelled", "c": "waitlisted"})
        self.assertEqual(self.cancel(self.b, e).status_code, 400)  # 신청 내역 없음

    def test_reregister_reuses_row_and_goes_to_back(self):
        e = make_event(capacity=1)
        for m in (self.a, self.b, self.c):
            self.register(m, e)
        self.cancel(self.b, e)
        res = self.register(self.b, e).json()
        self.assertEqual(Registration.objects.filter(event=e, member=self.b).count(), 1)
        self.assertEqual((res["my_status"], res["my_waitlist_position"]), ("waitlisted", 2))

    def test_list_and_detail(self):
        future = make_event(days=3, title="미래")
        later = make_event(days=10, title="나중")
        past = make_event(days=-3, title="과거")
        self.register(self.a, future)
        c = client_for(self.a)
        upcoming = c.get("/api/events").json()
        self.assertEqual([x["title"] for x in upcoming], ["미래", "나중"])
        self.assertEqual(upcoming[0]["my_status"], "confirmed")
        self.assertIsNone(upcoming[1]["my_status"])
        self.assertEqual([x["title"] for x in c.get("/api/events?past=1").json()], ["과거"])
        detail = c.get(f"/api/events/{future.id}").json()
        self.assertEqual(detail["attendees"], [{"name": "a", "status": "confirmed"}])
        self.assertTrue(detail["starts_at"].endswith("+09:00"))
        missing = c.get("/api/events/9999")
        self.assertEqual((missing.status_code, missing.json()), (404, {"detail": "모임을 찾을 수 없습니다."}))
        self.assertEqual(c.post("/api/events/9999/register").json(), {"detail": "모임을 찾을 수 없습니다."})
        self.assertEqual(c.post("/api/events/9999/cancel").status_code, 404)
        self.assertEqual(later.registrations.count() + past.registrations.count(), 0)


class ConcurrentRegisterTests(TransactionTestCase):
    def test_concurrent_register_never_exceeds_capacity(self):
        e = make_event(capacity=1)
        clients = [client_for(make_member(f"m{i}")) for i in range(6)]
        barrier = threading.Barrier(len(clients))
        codes = []

        def run(c):
            try:
                barrier.wait()
                codes.append(c.post(f"/api/events/{e.id}/register").status_code)
            finally:
                connection.close()

        threads = [threading.Thread(target=run, args=(c,)) for c in clients]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(codes, [200] * 6)
        self.assertEqual(e.registrations.filter(status="confirmed").count(), 1)
        self.assertEqual(e.registrations.filter(status="waitlisted").count(), 5)


class LedgerTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.prev = prev_month(self.today)
        self.staff = make_member("boss", staff=True)
        self.kim = make_member("kim", joined_on=self.prev, name="김철수")
        ClubSetting.objects.update_or_create(pk=1, defaults={"monthly_dues": 20000})

    def tx(self, category, amount, member=None, event=None, dues_month="", day=None):
        return Transaction.objects.create(date=day or self.today, category=category, amount=amount,
                                          member=member, event=event, dues_month=dues_month)

    def dashboard(self):
        res = client_for(self.staff).get("/api/dashboard")
        self.assertEqual(res.status_code, 200)
        return res.json()

    def test_balance_totals_monthly(self):
        s = ClubSetting.get()
        s.carry_over, s.carry_over_date = 300000, self.today - timedelta(days=40)
        s.save()
        e = make_event(fee=10000)
        self.tx(C.DUES, 99999, self.kim, dues_month="2020-01", day=s.carry_over_date)  # 이월 기준일 당일: 잔액 제외
        self.tx(C.DUES, 20000, self.kim, dues_month=f"{self.today:%Y-%m}")
        self.tx(C.EVENT_FEE, 10000, self.kim, e)
        self.tx(C.OTHER_INCOME, 5000)
        self.tx(C.EXPENSE, 7000, event=e)
        self.tx(C.REFUND, 3000, self.kim, e)
        d = self.dashboard()
        self.assertEqual(d["carry_over"], 300000)
        self.assertEqual(d["totals"], {"dues": 20000, "event_fee": 10000, "other_income": 5000, "expense": 7000, "refund": 3000})
        self.assertEqual(d["balance"], 300000 + 35000 - 10000)
        self.assertEqual(d["monthly"][0], {"month": f"{self.today:%Y-%m}", "income": 35000, "expense": 10000})
        self.assertEqual(len(d["monthly"]), 2)  # 이월 기준일 달도 월별 목록에는 남는다

    def test_unpaid_dues(self):
        make_member("sleep", status=Member.Status.DORMANT, joined_on=self.prev)
        self.tx(C.DUES, 20000, self.kim, dues_month=f"{self.prev:%Y-%m}")
        unpaid = {u["name"]: u["months"] for u in self.dashboard()["unpaid_dues"]}
        self.assertEqual(unpaid["김철수"], [f"{self.today:%Y-%m}"])
        self.assertNotIn("sleep", unpaid)  # 휴면 회원 제외
        dues = client_for(self.kim).get("/api/me/payments").json()["dues"]
        self.assertEqual(dues, [{"month": f"{self.today:%Y-%m}", "paid": False}, {"month": f"{self.prev:%Y-%m}", "paid": True}])

    def test_zero_monthly_dues_means_no_dues(self):
        ClubSetting.objects.filter(pk=1).update(monthly_dues=0)
        self.assertEqual(self.dashboard()["unpaid_dues"], [])
        pay = client_for(self.kim).get("/api/me/payments").json()
        self.assertEqual((pay["monthly_dues"], pay["dues"]), (0, []))

    def test_dashboard_attendance_period(self):
        now = timezone.localtime()
        this_month = now.replace(day=1, hour=0, minute=0, second=1)  # 이번 달 1일 (이미 시작함)
        last_year = now - timedelta(days=400)
        for starts_at, att in [(this_month, "present"), (last_year, "absent")]:
            e = Event.objects.create(title="x", starts_at=starts_at)
            Registration.objects.create(event=e, member=self.kim, status="confirmed", attendance=att)
        c = client_for(self.staff)

        def kim_row(query):
            res = c.get(f"/api/dashboard{query}")
            self.assertEqual(res.status_code, 200)
            return next((a["total"], a["present"]) for a in res.json()["attendance"] if a["name"] == "김철수")

        self.assertEqual(kim_row(""), (2, 1))
        self.assertEqual(kim_row(f"?year={now.year}"), (1, 1))
        self.assertEqual(kim_row(f"?year={now.year}&month={now.month}"), (1, 1))
        self.assertEqual(kim_row(f"?year={last_year.year}&month={last_year.month}"), (1, 0))
        for bad in ["?year=26", "?year=abcd", f"?month={now.month}", f"?year={now.year}&month=13", f"?year={now.year}&month=0"]:
            res = c.get(f"/api/dashboard{bad}")
            self.assertEqual(res.status_code, 400, bad)
            self.assertIn("detail", res.json())

    def test_unpaid_event_fee_and_my_payments(self):
        paid_event, unpaid_event, free = make_event(fee=10000, title="유료1"), make_event(days=8, fee=5000, title="유료2"), make_event()
        for e in (paid_event, unpaid_event, free):
            client_for(self.kim).post(f"/api/events/{e.id}/register")
        self.tx(C.EVENT_FEE, 10000, self.kim, paid_event)
        d = self.dashboard()
        self.assertEqual(d["unpaid_event_fees"], [{"event_id": unpaid_event.id, "title": "유료2", "member_id": self.kim.id, "name": "김철수", "fee": 5000}])
        pay = client_for(self.kim).get("/api/me/payments").json()
        self.assertEqual([(f["title"], f["paid"]) for f in pay["event_fees"]], [("유료2", False), ("유료1", True)])
        self.assertEqual(pay["transactions"], [{"date": self.today.isoformat(), "category": "event_fee", "amount": 10000, "memo": ""}])

    def test_refunds_needed(self):
        e = make_event(fee=10000, title="환불")
        c = client_for(self.kim)
        c.post(f"/api/events/{e.id}/register")
        self.tx(C.EVENT_FEE, 10000, self.kim, e)
        self.assertEqual(self.dashboard()["refunds_needed"], [])  # 아직 확정 상태
        c.post(f"/api/events/{e.id}/cancel")
        self.assertEqual(self.dashboard()["refunds_needed"],
                         [{"event_id": e.id, "title": "환불", "member_id": self.kim.id, "name": "김철수", "amount": 10000}])
        self.tx(C.REFUND, 4000, self.kim, e)
        self.assertEqual(self.dashboard()["refunds_needed"][0]["amount"], 6000)
        self.tx(C.REFUND, 6000, self.kim, e)
        self.assertEqual(self.dashboard()["refunds_needed"], [])

    def test_attendance_rate(self):
        events = [make_event(days=-i) for i in (1, 2, 3)]
        future = make_event(days=1)
        for e, att in zip(events, ["present", "present", "absent"]):
            Registration.objects.create(event=e, member=self.kim, status="confirmed", attendance=att)
        Registration.objects.create(event=make_event(days=-4), member=self.kim, status="waitlisted")
        Registration.objects.create(event=future, member=self.kim, status="confirmed")
        res = client_for(self.kim).get("/api/me/attendance").json()
        self.assertEqual((res["total"], res["present"], res["absent"], res["rate"]), (3, 2, 1, 67))
        self.assertEqual([r["event_id"] for r in res["records"]], [e.id for e in events])
        row = next(a for a in self.dashboard()["attendance"] if a["name"] == "김철수")
        self.assertEqual((row["total"], row["present"], row["rate"]), (3, 2, 67))

    def test_attendance_rounds_half_up_and_empty_is_null(self):
        self.assertIsNone(client_for(self.kim).get("/api/me/attendance").json()["rate"])
        for i in range(8):
            Registration.objects.create(event=make_event(days=-1 - i), member=self.kim, status="confirmed",
                                        attendance="present" if i == 0 else "unknown")
        self.assertEqual(client_for(self.kim).get("/api/me/attendance").json()["rate"], 13)  # 12.5 -> 13

    def test_transaction_required_links(self):
        e = make_event()
        cases = [
            (Transaction(category=C.DUES, amount=1, member=self.kim), "dues_month"),
            (Transaction(category=C.DUES, amount=1, dues_month="2026-11"), "member"),
            (Transaction(category=C.EVENT_FEE, amount=1, member=self.kim), "event"),
            (Transaction(category=C.REFUND, amount=1, event=e), "member"),
            (Transaction(category=C.DUES, amount=1, member=self.kim, dues_month="2026-13"), "dues_month"),
            (Transaction(category=C.OTHER_INCOME, amount=0), "amount"),
        ]
        for t, field in cases:
            with self.assertRaises(ValidationError) as ctx:
                t.full_clean()
            self.assertIn(field, ctx.exception.message_dict)
        Transaction(category=C.EXPENSE, amount=1000).full_clean()  # 연결 없이도 유효

    def test_announcements(self):
        Announcement.objects.create(title="첫 공지", body="본문")
        Announcement.objects.create(title="둘째 공지", body="본문")
        res = client_for(self.kim).get("/api/announcements").json()
        self.assertEqual([a["title"] for a in res], ["둘째 공지", "첫 공지"])


class BackupTests(SimpleTestCase):
    def test_backup_keeps_latest_seven(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "db.sqlite3"
            con = sqlite3.connect(db)
            con.execute("create table t (x)")
            con.close()
            backups = Path(tmp) / "backups"
            backups.mkdir()
            for i in range(1, 9):
                (backups / f"db-2000010{i}.sqlite3").write_bytes(b"")
            with mock.patch.dict(settings.DATABASES["default"], NAME=db):
                call_command("backup_db", stdout=StringIO())
            names = sorted(p.name for p in backups.iterdir())
            self.assertEqual(len(names), 7)
            self.assertEqual(names[-1], f"db-{timezone.localdate():%Y%m%d}.sqlite3")
            self.assertNotIn("db-20000101.sqlite3", names)


class AdminPagesTests(TestCase):
    def test_admin_pages_render(self):
        admin = User.objects.create_superuser("boss", password=PW)
        member = make_member("kim")
        event = make_event()
        c = APIClient()
        c.force_login(admin)
        for url in ["auth/user/", "auth/user/add/", f"auth/user/{member.user.id}/change/", "club/member/",
                    "club/event/", "club/event/add/", f"club/event/{event.id}/change/", "club/transaction/",
                    "club/transaction/add/", "club/announcement/add/", "club/clubsetting/add/"]:
            self.assertEqual(c.get(f"/club-admin/{url}").status_code, 200, url)

    def test_transaction_admin_records_creator(self):
        admin = User.objects.create_superuser("boss", password=PW)
        member = make_member("kim")
        c = APIClient()
        c.force_login(admin)
        res = c.post("/club-admin/club/transaction/add/", {"date": "2026-11-03", "category": "dues", "amount": 20000,
                                                           "member": member.id, "dues_month": "2026-11", "memo": ""})
        self.assertEqual(res.status_code, 302)
        self.assertEqual(Transaction.objects.get().created_by, admin)
        bad = c.post("/club-admin/club/transaction/add/", {"date": "2026-11-03", "category": "dues", "amount": 20000, "memo": ""})
        self.assertEqual(bad.status_code, 200)  # 회원·월 누락은 폼 오류로 되돌아온다
        self.assertEqual(Transaction.objects.count(), 1)
