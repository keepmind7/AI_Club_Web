import sqlite3
import tempfile
import threading
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.admin import site
from django.contrib.auth.models import User
from django.core.cache import cache, caches
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .admin import ClubUserAdmin
from .models import Announcement, ClubSetting, Comment, Event, Member, Post, Registration, SharedAccount, Transaction

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
        self.assertEqual(res.json()["detail"], "로그인 시도가 너무 많아요. 10분 뒤에 다시 시도해 주세요.")
        # 다른 아이디는 영향 없음
        make_member("kim")
        self.assertEqual(c.post("/api/auth/login", {"username": "kim", "password": PW}, format="json").status_code, 200)

    def test_dormant_member(self):
        dormant = make_member("sleep", status=Member.Status.DORMANT)
        res = APIClient().post("/api/auth/login", {"username": "sleep", "password": PW}, format="json")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["detail"], "이용이 제한된 계정이에요. 운영진에게 문의해 주세요.")  # 계약 고정 문구, 프론트가 이 문구로 판별
        c = client_for(dormant)  # 로그인 후 휴면으로 바뀐 경우
        self.assertEqual(c.get("/api/events").status_code, 403)
        self.assertEqual(c.get("/api/me/payments").status_code, 403)
        res = c.get("/api/auth/me")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["detail"], "이용이 제한된 계정이에요. 운영진에게 문의해 주세요.")  # 계약 고정 문구, 프론트가 이 문구로 판별
        self.assertIn("csrftoken", res.cookies)
        self.assertEqual(c.post("/api/auth/logout").status_code, 204)

    def test_change_password(self):
        c = client_for(self.member)
        bad_old = c.post("/api/auth/password", {"old_password": "x", "new_password": "Another-pass-99"}, format="json")
        self.assertEqual(bad_old.status_code, 400)
        weak = c.post("/api/auth/password", {"old_password": PW, "new_password": "1234"}, format="json")
        self.assertEqual((weak.status_code, weak.json()["detail"]), (400, "비밀번호는 8자 이상으로 정해 주세요. "
                         "너무 흔한 비밀번호예요. 다른 걸로 정해 주세요. 숫자로만 된 비밀번호는 쓸 수 없어요."))
        similar = c.post("/api/auth/password", {"old_password": PW, "new_password": "hong12"}, format="json")
        self.assertEqual(similar.json()["detail"], "아이디나 이름과 너무 비슷해요. 비밀번호는 8자 이상으로 정해 주세요.")
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

    def test_list_waitlist_position_without_per_event_queries(self):
        events = [make_event(days=d, capacity=1) for d in (1, 2)]
        for e in events:
            self.register(self.a, e)
            self.register(self.b, e)
        self.register(self.c, events[1])
        c = client_for(self.c)
        with self.assertNumQueries(6):  # 세션, 사용자, 회원 + 모임, 신청, 신청 회원 (모임 수와 무관)
            res = c.get("/api/events").json()
        self.assertEqual([(x["my_status"], x["my_waitlist_position"]) for x in res], [(None, None), ("waitlisted", 2)])
        self.assertEqual([x["my_waitlist_position"] for x in client_for(self.a).get("/api/events").json()], [None, None])
        self.register(self.c, make_event(days=3, capacity=1))
        with self.assertNumQueries(6):
            self.assertEqual(len(c.get("/api/events").json()), 3)

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
        self.assertEqual((missing.status_code, missing.json()), (404, {"detail": "모임을 찾을 수 없어요."}))
        self.assertEqual(c.post("/api/events/9999/register").json(), {"detail": "모임을 찾을 수 없어요."})
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


class ConcurrentLoginTests(TransactionTestCase):
    def test_concurrent_wrong_passwords_respect_limit(self):
        cache.clear()
        make_member("hong")
        n = 10
        barrier = threading.Barrier(n)
        details = []

        def run():
            try:
                barrier.wait()
                details.append(APIClient().post("/api/auth/login", {"username": "hong", "password": "wrong"},
                                                format="json").json()["detail"])
            finally:
                connection.close()

        threads = [threading.Thread(target=run) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # 동시에 들어와도 비밀번호를 확인하는 시도는 정확히 5번
        self.assertEqual(details.count("아이디나 비밀번호가 맞지 않아요."), 5)
        self.assertEqual(details.count("로그인 시도가 너무 많아요. 10분 뒤에 다시 시도해 주세요."), 5)


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
        prev, this = f"{self.prev:%Y-%m}", f"{self.today:%Y-%m}"
        make_member("sleep", status=Member.Status.DORMANT, joined_on=self.prev)
        make_member("new", joined_on=self.today)  # 이번 달 가입: 대시보드 미납 없음
        self.tx(C.DUES, 10000, self.kim, dues_month=prev)
        self.tx(C.DUES, 5000, self.kim, dues_month=prev)
        unpaid = {u["name"]: u["months"] for u in self.dashboard()["unpaid_dues"]}
        self.assertEqual(unpaid, {"김철수": [prev]})  # 일부 납부는 미납. 이번 달·휴면 회원은 제외
        dues = client_for(self.kim).get("/api/me/payments").json()["dues"]
        self.assertEqual(dues, [{"month": this, "paid": False}, {"month": prev, "paid": False}])  # 이번 달도 나온다
        self.tx(C.DUES, 5000, self.kim, dues_month=prev)  # 합계 20000 = 월 회비
        self.assertEqual(self.dashboard()["unpaid_dues"], [])
        dues = client_for(self.kim).get("/api/me/payments").json()["dues"]
        self.assertEqual(dues, [{"month": this, "paid": False}, {"month": prev, "paid": True}])

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
        for bad in ["?year=26", "?year=abcd", "?year=0000", "?year=0001", "?year=1899", "?year=9999", f"?month={now.month}", f"?year={now.year}&month=13", f"?year={now.year}&month=0"]:
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

    def test_event_fee_refunded_then_reconfirmed_is_unpaid(self):
        e = make_event(fee=10000, title="재확정")
        c = client_for(self.kim)
        c.post(f"/api/events/{e.id}/register")
        self.tx(C.EVENT_FEE, 10000, self.kim, e)
        c.post(f"/api/events/{e.id}/cancel")
        self.tx(C.REFUND, 10000, self.kim, e)
        c.post(f"/api/events/{e.id}/register")  # 다시 확정: 순납부 0원
        d = self.dashboard()
        self.assertEqual([u["event_id"] for u in d["unpaid_event_fees"]], [e.id])
        self.assertEqual(d["refunds_needed"], [])
        self.assertEqual([f["paid"] for f in c.get("/api/me/payments").json()["event_fees"]], [False])
        self.tx(C.EVENT_FEE, 10000, self.kim, e)
        self.assertEqual(self.dashboard()["unpaid_event_fees"], [])

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

    def test_refunds_needed_for_waitlisted_after_start(self):
        started, upcoming = make_event(days=-1, fee=10000, title="지남"), make_event(fee=10000, title="곧")
        for e in (started, upcoming):
            Registration.objects.create(event=e, member=self.kim, status="waitlisted")
            self.tx(C.EVENT_FEE, 10000, self.kim, e)
        lee = make_member("lee", name="이영희")
        Registration.objects.create(event=started, member=lee, status="confirmed")
        self.tx(C.EVENT_FEE, 10000, lee, started)
        # 아직 시작 전인 대기자와 확정자는 환불 대상이 아니다
        self.assertEqual(self.dashboard()["refunds_needed"],
                         [{"event_id": started.id, "title": "지남", "member_id": self.kim.id, "name": "김철수", "amount": 10000}])

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


class CacheTests(SimpleTestCase):
    def test_cache_is_shared_between_workers(self):
        self.assertNotIn("LocMem", settings.CACHES["default"]["BACKEND"])
        self.assertEqual(Path(settings.CACHES["default"]["LOCATION"]).name, "test_cache")  # 운영 캐시와 분리
        self.assertGreaterEqual(cache._max_entries, 10000)  # 기본 300개 컬링으로 실패 기록이 지워지지 않게
        other = caches.create_connection("default")  # 다른 gunicorn 워커의 캐시 객체
        cache.set("shared-check", 3, 60)
        self.assertEqual(other.get("shared-check"), 3)
        cache.delete("shared-check")


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
        post = Post.objects.create(author=member.user, title="글", body="본문")
        Comment.objects.create(post=post, author=admin, body="댓글")
        c = APIClient()
        c.force_login(admin)
        for url in ["auth/user/", "auth/user/add/", f"auth/user/{member.user.id}/change/", "club/member/",
                    "club/event/", "club/event/add/", f"club/event/{event.id}/change/", "club/transaction/",
                    "club/transaction/add/", "club/announcement/add/", "club/clubsetting/add/",
                    "club/sharedaccount/add/", "auth/user/?q=kim", "club/post/", "club/post/add/",
                    f"club/post/{post.id}/change/", "club/post/?q=본문"]:
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

    def test_operator_checkbox_sets_superuser(self):
        user = make_member("kim").user
        user_admin = ClubUserAdmin(User, site)
        user.is_staff = True
        user_admin.save_model(None, user, None, True)
        self.assertTrue(User.objects.get(pk=user.pk).is_superuser)
        user.is_staff = False
        user_admin.save_model(None, user, None, True)
        self.assertFalse(User.objects.get(pk=user.pk).is_superuser)

    def test_group_menu_hidden(self):
        c = APIClient()
        c.force_login(User.objects.create_superuser("boss", password=PW))
        self.assertEqual(c.get("/club-admin/auth/group/").status_code, 404)

    def test_admin_screens_for_operators(self):
        """운영진용 화면: 한 묶음 메뉴, 쉬운 문구, 금액 표시, 비밀번호 해시·SSO 선택 숨김."""
        boss = User.objects.create_superuser("boss", password=PW)
        kim = make_member("kim", name="김철수")
        Transaction.objects.create(category=C.EXPENSE, amount=55000, memo="간식과 음료", created_by=boss)
        c = client_for(boss)
        index = c.get("/club-admin/")
        self.assertContains(index, "Mythos 관리")
        self.assertContains(index, 'href="/dashboard"')
        self.assertNotContains(index, "최근 활동")
        self.assertEqual([[m["object_name"] for m in g["models"]] for g in index.context["app_list"]],
                         [["User", "Member", "Event", "Transaction", "Announcement", "Post", "SharedAccount", "ClubSetting"]])
        add = c.get("/club-admin/auth/user/add/")
        self.assertContains(add, "회원 계정 추가")
        self.assertContains(add, "아이디")
        self.assertContains(add, "저장하고 하나 더 추가")
        self.assertNotContains(add, 'name="usable_password"')
        change = c.get(f"/club-admin/auth/user/{kim.user_id}/change/")
        self.assertContains(change, "비밀번호 초기화")
        self.assertContains(change, "로그인 허용")
        self.assertNotContains(change, kim.user.password[:12])  # 해시 일부도 안 보인다
        self.assertNotContains(change, 'name="last_login_0"')  # 기록은 읽기 전용
        self.assertNotContains(c.get(f"/club-admin/auth/user/{kim.user_id}/password/"), 'name="usable_password"')
        self.assertContains(c.get("/club-admin/club/transaction/"), "55,000원")
        self.assertContains(c.get("/club-admin/club/member/"), "회원 계정 추가")
        self.assertEqual(c.get("/club-admin/club/member/add/").status_code, 403)

    def test_admin_adds_user_with_member(self):
        c = client_for(User.objects.create_superuser("boss", password=PW))
        data = {"username": "new", "password1": "", "password2": "",
                "member-TOTAL_FORMS": 1, "member-INITIAL_FORMS": 0, "member-MIN_NUM_FORMS": 0, "member-MAX_NUM_FORMS": 1,
                "member-0-name": "신입", "member-0-phone": "", "member-0-joined_on": "2026-11-09",
                "member-0-status": "active", "member-0-must_change_password": "on"}
        self.assertEqual(c.post("/club-admin/auth/user/add/", data).status_code, 200)  # 비밀번호는 꼭 넣는다
        self.assertFalse(User.objects.filter(username="new").exists())
        res = c.post("/club-admin/auth/user/add/", {**data, "password1": "Fresh-pass-2026", "password2": "Fresh-pass-2026"})
        self.assertEqual(res.status_code, 302)
        user = User.objects.get(username="new")
        self.assertTrue(user.check_password("Fresh-pass-2026"))
        self.assertEqual((user.member.name, user.member.must_change_password), ("신입", True))


class AdminStatusTests(TestCase):
    """관리자 화면에서 바꿔도 대기자 승격과 휴면·탈퇴 신청 정리가 일어난다."""

    def setUp(self):
        self.c = APIClient()
        self.c.force_login(User.objects.create_superuser("boss", password=PW))
        self.base = timezone.now().replace(microsecond=0)

    def reg(self, event, member, status, minutes=0):
        return Registration.objects.create(event=event, member=member, status=status,
                                           applied_at=self.base + timedelta(minutes=minutes))

    def statuses(self, event):
        return [r.status for r in event.registrations.all()]  # 신청 순서

    def post(self, url, data):
        res = self.c.post(f"/club-admin/{url}", data)
        self.assertEqual(res.status_code, 302, res.context and res.context.get("errors"))

    def save_event(self, event, capacity, statuses):
        def split(name, dt):
            dt = timezone.localtime(dt)
            return {f"{name}_0": f"{dt:%Y-%m-%d}", f"{name}_1": f"{dt:%H:%M:%S}"}
        regs = list(event.registrations.all())
        data = {"title": event.title, "description": "", "place": "", "capacity": capacity, "fee": event.fee,
                **split("starts_at", event.starts_at), "registrations-TOTAL_FORMS": len(regs),
                "registrations-INITIAL_FORMS": len(regs), "registrations-MIN_NUM_FORMS": 0, "registrations-MAX_NUM_FORMS": 1000}
        for i, (r, status) in enumerate(zip(regs, statuses)):
            p = f"registrations-{i}-"
            data.update({p + "id": r.id, p + "event": event.id, p + "member": r.member_id, p + "status": status,
                         p + "attendance": r.attendance, **split(p + "applied_at", r.applied_at)})
        self.post(f"club/event/{event.id}/change/", data)

    def test_admin_cancel_and_capacity_increase_promote(self):
        e = make_event(capacity=1)
        for i, name in enumerate("abc"):
            self.reg(e, make_member(name), "confirmed" if i == 0 else "waitlisted", i)
        self.save_event(e, 1, ["cancelled", "waitlisted", "waitlisted"])  # 확정자 취소
        self.assertEqual(self.statuses(e), ["cancelled", "confirmed", "waitlisted"])
        self.save_event(e, 3, self.statuses(e))  # 정원 증가
        self.assertEqual(self.statuses(e), ["cancelled", "confirmed", "confirmed"])

    def test_admin_change_on_started_event_does_not_promote(self):
        e = make_event(days=-1, capacity=1)
        self.reg(e, make_member("a"), "confirmed")
        self.reg(e, make_member("b"), "waitlisted", 1)
        self.save_event(e, 1, ["cancelled", "waitlisted"])
        self.assertEqual(self.statuses(e), ["cancelled", "waitlisted"])

    def make_regs(self, member):
        """시작 전 정원 1 모임(확정, 뒤에 대기자 1명), 시작 전 다른 모임(대기), 지난 모임(확정)."""
        full, other, past = make_event(capacity=1), make_event(days=8), make_event(days=-1)
        self.reg(full, member, "confirmed")
        waiter = self.reg(full, make_member(f"w-{member.name}"), "waitlisted", 1)
        self.reg(other, member, "waitlisted")
        self.reg(past, member, "confirmed")
        return waiter, past

    def check_cleanup(self, member, waiter, past):
        statuses = dict(member.registrations.values_list("event_id", "status"))
        self.assertEqual(statuses.pop(past.id), "confirmed")  # 지난 모임은 그대로
        self.assertEqual(list(statuses.values()), ["cancelled", "cancelled"])
        waiter.refresh_from_db()
        self.assertEqual(waiter.status, "confirmed")

    def test_member_admin_dormant_cancels_upcoming(self):
        kim = make_member("kim")
        waiter, past = self.make_regs(kim)
        self.post(f"club/member/{kim.id}/change/", {"user": kim.user_id, "name": kim.name, "phone": "",
                                                     "joined_on": f"{kim.joined_on:%Y-%m-%d}", "status": "dormant"})
        self.check_cleanup(kim, waiter, past)

    def test_user_inline_withdrawn_cancels_upcoming(self):
        kim = make_member("kim")
        waiter, past = self.make_regs(kim)
        joined = timezone.localtime(kim.user.date_joined)
        self.post(f"auth/user/{kim.user_id}/change/", {
            "username": "kim", "is_active": "on",
            "date_joined_0": f"{joined:%Y-%m-%d}", "date_joined_1": f"{joined:%H:%M:%S}",
            "member-TOTAL_FORMS": 1, "member-INITIAL_FORMS": 1, "member-MIN_NUM_FORMS": 0, "member-MAX_NUM_FORMS": 1,
            "member-0-id": kim.id, "member-0-user": kim.user_id, "member-0-name": kim.name, "member-0-phone": "",
            "member-0-joined_on": f"{kim.joined_on:%Y-%m-%d}", "member-0-status": "withdrawn",
        })
        self.check_cleanup(kim, waiter, past)


class SharedAccountTests(TestCase):
    def setUp(self):
        self.a = SharedAccount.objects.create(email="a@club.kr", password="pw-a", memo="팀 플랜")
        self.b = SharedAccount.objects.create(email="b@club.kr", password="pw-b")
        self.kim = make_member("kim", name="김철수")
        self.hong = make_member("hong", name="홍길동")
        self.lee = make_member("lee", name="이영희", status=Member.Status.DORMANT)
        Member.objects.filter(pk__in=[self.kim.pk, self.hong.pk, self.lee.pk]).update(shared_account=self.a)

    def test_member_sees_only_own_account_with_active_members(self):
        res = client_for(self.hong).get("/api/shared-accounts")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [{"id": self.a.id, "email": "a@club.kr", "password": "pw-a", "memo": "팀 플랜",
                                       "members": [{"name": "김철수"}, {"name": "홍길동"}]}])

    def test_member_without_account_gets_empty_list(self):
        self.assertEqual(client_for(make_member("park")).get("/api/shared-accounts").json(), [])

    def test_staff_sees_all_and_others_are_rejected(self):
        boss = User.objects.create_user("boss", password=PW, is_staff=True)  # Member 기록 없는 운영진
        self.assertEqual([a["email"] for a in client_for(boss).get("/api/shared-accounts").json()], ["a@club.kr", "b@club.kr"])
        self.assertIn(APIClient().get("/api/shared-accounts").status_code, (401, 403))
        self.assertEqual(client_for(self.lee).get("/api/shared-accounts").status_code, 403)

    def test_admin_assigns_moves_and_unassigns(self):
        c = client_for(User.objects.create_superuser("boss", password=PW))
        park = make_member("park")
        self.assertContains(c.get(f"/club-admin/club/sharedaccount/{self.a.id}/change/"), f'<option value="{self.kim.id}" selected>김철수</option>')
        self.assertContains(c.get(f"/club-admin/club/sharedaccount/{self.b.id}/change/"), "김철수 (a@club.kr)")  # 다른 계정 표시
        self.assertContains(c.get("/club-admin/auth/user/"), "<td class=\"field-member_status\">활동</td>", html=True)
        res = c.post(f"/club-admin/club/sharedaccount/{self.b.id}/change/",
                     {"email": "b@club.kr", "password": "pw-b2", "memo": "", "members": [self.kim.id, park.id]})
        self.assertEqual(res.status_code, 302)
        accounts = dict(Member.objects.values_list("name", "shared_account__email"))
        self.assertEqual(accounts, {"김철수": "b@club.kr", "park": "b@club.kr", "홍길동": "a@club.kr", "이영희": "a@club.kr"})
        self.assertEqual(SharedAccount.objects.get(pk=self.b.pk).password, "pw-b2")
        c.post(f"/club-admin/club/sharedaccount/{self.b.id}/change/", {"email": "b@club.kr", "password": "pw-b2", "memo": "", "members": [park.id]})
        self.assertIsNone(Member.objects.get(pk=self.kim.pk).shared_account)


class BoardTests(TestCase):
    def setUp(self):
        self.hong = make_member("hong", name="홍길동")
        self.kim = make_member("kim", name="김철수")
        self.boss = User.objects.create_user("boss", password=PW, is_staff=True)  # Member 기록 없는 운영진

    def write(self, member, title="스터디", body="같이 해요"):
        return client_for(member).post("/api/posts", {"title": title, "body": body}, format="json")

    def test_write_list_detail_and_comment(self):
        res = self.write(self.hong, "  스터디  ", " 본문\n둘째 줄 ")
        self.assertEqual(res.status_code, 201)
        post = res.json()
        self.assertEqual((post["title"], post["body"], post["author"], post["comment_count"]), ("스터디", "본문\n둘째 줄", "홍길동", 0))
        self.assertEqual((post["can_edit"], post["can_delete"], post["comments"]), (True, True, []))
        self.write(self.kim, "두 번째")
        c = client_for(self.kim)
        res = c.post(f"/api/posts/{post['id']}/comments", {"body": "저요"}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual([(x["author"], x["body"], x["can_delete"]) for x in res.json()["comments"]], [("김철수", "저요", True)])
        client_for(self.boss).post(f"/api/posts/{post['id']}/comments", {"body": "운영진"}, format="json")
        with self.assertNumQueries(4):  # 세션, 사용자, 회원 + 글 목록 1번 (글 수와 무관)
            listing = c.get("/api/posts").json()
        self.assertEqual([(p["title"], p["comment_count"]) for p in listing], [("두 번째", 0), ("스터디", 2)])  # 최신순
        detail = c.get(f"/api/posts/{post['id']}").json()
        self.assertEqual((detail["can_edit"], detail["can_delete"]), (False, False))
        self.assertEqual([(x["author"], x["can_delete"]) for x in detail["comments"]], [("김철수", True), ("boss", False)])  # 작성순
        boss_view = client_for(self.boss).get(f"/api/posts/{post['id']}").json()
        self.assertEqual((boss_view["can_edit"], boss_view["can_delete"]), (False, True))
        self.assertEqual(c.get("/api/posts/999").json(), {"detail": "글을 찾을 수 없어요."})

    def test_excerpt(self):
        self.write(self.hong, body="첫 줄  공백\n\n\t둘째 " + "가" * 69 + "  끝말")  # 줄이면 80번째 글자가 공백
        self.write(self.kim, body="짧은\n본문")
        listing = client_for(self.hong).get("/api/posts").json()
        self.assertEqual([p["excerpt"] for p in listing], ["짧은 본문", "첫 줄 공백 둘째 " + "가" * 69 + "…"])  # 끝 공백 없이 …

    def test_input_rules(self):
        for title, body in [("   ", "본문"), ("x" * 101, "본문"), ("제목", " "), ("제목", "x" * 5001)]:
            res = self.write(self.hong, title, body)
            self.assertEqual(res.status_code, 400, (len(title), len(body)))
            self.assertIn("detail", res.json())
        self.assertEqual(self.write(self.hong, "x" * 100, "x" * 5000).status_code, 201)
        res = client_for(self.hong).post("/api/posts", {"title": 1, "body": None}, format="json")
        self.assertEqual(res.status_code, 400)
        url = f"/api/posts/{Post.objects.get().id}/comments"
        self.assertEqual(client_for(self.kim).post(url, {"body": "x" * 1001}, format="json").status_code, 400)
        self.assertEqual(client_for(self.kim).post(url, {"body": "x" * 1000}, format="json").status_code, 201)

    def test_edit_only_by_author(self):
        pk = self.write(self.hong).json()["id"]
        old = Post.objects.get().updated_at
        for who in (self.kim, self.boss):
            res = client_for(who).post(f"/api/posts/{pk}/edit", {"title": "남이 고침", "body": "x"}, format="json")
            self.assertEqual(res.status_code, 403)
        res = client_for(self.hong).post(f"/api/posts/{pk}/edit", {"title": "고침", "body": "새 본문"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.json()["title"], res.json()["body"]), ("고침", "새 본문"))
        self.assertGreater(Post.objects.get().updated_at, old)
        self.assertEqual(client_for(self.hong).post(f"/api/posts/{pk}/edit", {"title": "", "body": "x"}, format="json").status_code, 400)
        self.assertEqual(client_for(self.hong).post("/api/posts/999/edit", {"title": "a", "body": "b"}, format="json").status_code, 404)

    def test_delete_permissions_and_cascade(self):
        pk = self.write(self.hong).json()["id"]
        detail = client_for(self.kim).post(f"/api/posts/{pk}/comments", {"body": "댓글"}, format="json").json()
        comment_id = detail["comments"][0]["id"]
        self.assertEqual(client_for(make_member("lee")).post(f"/api/comments/{comment_id}/delete").status_code, 403)
        self.assertEqual(client_for(self.kim).post(f"/api/posts/{pk}/delete").status_code, 403)
        self.assertEqual(client_for(self.boss).post(f"/api/posts/{pk}/delete").status_code, 204)  # 운영진은 남의 글 삭제
        self.assertEqual(Comment.objects.count(), 0)  # 댓글도 함께 삭제
        self.assertEqual(client_for(self.boss).post(f"/api/posts/{pk}/delete").status_code, 404)
        pk = self.write(self.hong).json()["id"]
        comment = lambda: client_for(self.kim).post(f"/api/posts/{pk}/comments", {"body": "댓글"}, format="json").json()["comments"][-1]["id"]
        self.assertEqual(client_for(self.kim).post(f"/api/comments/{comment()}/delete").status_code, 204)  # 작성자 본인
        cid = comment()
        self.assertEqual(client_for(self.boss).post(f"/api/comments/{cid}/delete").status_code, 204)  # 운영진은 남의 댓글도
        self.assertEqual(client_for(self.kim).post(f"/api/comments/{cid}/delete").json(), {"detail": "댓글을 찾을 수 없어요."})
        self.assertEqual(client_for(self.hong).post(f"/api/posts/{pk}/delete").status_code, 204)  # 작성자 본인 삭제

    def test_admin_deletes_comment_without_touching_post(self):
        post = Post.objects.get(pk=self.write(self.hong).json()["id"])
        self.assertEqual(post.updated_at, post.created_at)
        cid = client_for(self.kim).post(f"/api/posts/{post.id}/comments", {"body": "댓글"}, format="json").json()["comments"][0]["id"]
        c = client_for(User.objects.create_superuser("root", password=PW))
        self.assertContains(c.get("/club-admin/club/post/"), "홍길동")  # 목록 작성자는 회원 이름
        res = c.post(f"/club-admin/club/post/{post.id}/change/", {
            "title": post.title, "body": post.body, "author": self.kim.user.id,  # author는 읽기 전용이라 무시된다
            "comments-TOTAL_FORMS": 1, "comments-INITIAL_FORMS": 1, "comments-MIN_NUM_FORMS": 0, "comments-MAX_NUM_FORMS": 1000,
            "comments-0-id": cid, "comments-0-post": post.id, "comments-0-DELETE": "on"})
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Comment.objects.exists())
        after = Post.objects.get()
        self.assertEqual((after.updated_at, after.author), (post.updated_at, self.hong.user))
        c.post("/club-admin/club/post/add/", {"title": "운영진 글", "body": "본문", "comments-TOTAL_FORMS": 0,
               "comments-INITIAL_FORMS": 0, "comments-MIN_NUM_FORMS": 0, "comments-MAX_NUM_FORMS": 1000})
        self.assertEqual(Post.objects.get(title="운영진 글").author.username, "root")

    def test_anonymous_and_dormant_rejected(self):
        dormant = make_member("lee", status=Member.Status.DORMANT)
        self.assertIn(APIClient().get("/api/posts").status_code, (401, 403))
        self.assertEqual(client_for(dormant).get("/api/posts").status_code, 403)
        self.assertEqual(self.write(dormant).status_code, 403)
        self.assertEqual(Post.objects.count(), 0)
