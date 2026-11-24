from decimal import Decimal

from django.urls import reverse
from django.test import TestCase

from . import services
from .models import Attendance, CashAdvance, Employee, PayrollRecord


class PayrollTests(TestCase):
    def test_fixed_pay_settles_advance(self):
        e = Employee.objects.create(name="Ana", salary=7200)
        CashAdvance.objects.create(employee=e, amount=1000)
        rec = services.create_payroll(employee=e, pay_type=PayrollRecord.PayType.FIXED, value=Decimal("7200"))
        self.assertEqual(rec.net_pay, Decimal("6200"))
        self.assertEqual(e.outstanding_advance, 0)

    def test_advance_larger_than_pay_carries_over(self):
        e = Employee.objects.create(name="Jules", salary=500)
        CashAdvance.objects.create(employee=e, amount=900)
        rec = services.create_payroll(employee=e, pay_type=PayrollRecord.PayType.FIXED, value=Decimal("500"))
        self.assertEqual(rec.net_pay, Decimal("500"))
        self.assertEqual(e.outstanding_advance, Decimal("900"))

    def test_rejects_invalid_payroll_values(self):
        e = Employee.objects.create(name="Mia", salary=7000)
        with self.assertRaisesMessage(ValueError, "pay value must be greater than zero."):
            services.create_payroll(employee=e, pay_type=PayrollRecord.PayType.FIXED, value=Decimal("0"))
        with self.assertRaisesMessage(ValueError, "Percentage pay cannot exceed 100%."):
            services.create_payroll(employee=e, pay_type=PayrollRecord.PayType.PERCENTAGE, value=Decimal("120"))


class AttendanceTests(TestCase):
    def setUp(self):
        from accounts.models import User

        self.user = User.objects.create_user(username="staff", password="test-password", role="staff")
        self.employee = Employee.objects.create(name="Mika", user=self.user)
        self.client.force_login(self.user)
        self.url = reverse("finance:attendance")

    def test_staff_can_check_in_and_check_out(self):
        response = self.client.post(self.url, {"action": "time_in"})
        self.assertRedirects(response, self.url)
        record = Attendance.objects.get(employee=self.employee)
        self.assertIsNone(record.check_out)

        response = self.client.post(self.url, {"action": "time_out"})
        self.assertRedirects(response, self.url)
        record.refresh_from_db()
        self.assertIsNotNone(record.check_out)

    def test_duplicate_check_in_does_not_create_another_record(self):
        self.client.post(self.url, {"action": "time_in"})
        self.client.post(self.url, {"action": "time_in"})
        self.assertEqual(Attendance.objects.filter(employee=self.employee).count(), 1)

    def test_staff_can_record_break_time_out_and_time_in(self):
        self.client.post(self.url, {"action": "time_in"})

        self.client.post(self.url, {"action": "break_time_out"})
        record = Attendance.objects.get(employee=self.employee)
        self.assertIsNotNone(record.break_time_out)
        self.assertIsNone(record.break_time_in)

        self.client.post(self.url, {"action": "break_time_in"})
        record.refresh_from_db()
        self.assertIsNotNone(record.break_time_in)

    def test_cannot_time_out_while_break_is_open(self):
        self.client.post(self.url, {"action": "time_in"})
        self.client.post(self.url, {"action": "break_time_out"})

        self.client.post(self.url, {"action": "time_out"})
        record = Attendance.objects.get(employee=self.employee)
        self.assertIsNone(record.check_out)

    def test_unlinked_user_cannot_create_attendance(self):
        self.employee.user = None
        self.employee.save(update_fields=["user"])
        self.client.post(self.url, {"action": "time_in"})
        self.assertFalse(Attendance.objects.exists())


class UserCreationTests(TestCase):
    def setUp(self):
        from accounts.models import User

        self.admin = User.objects.create_user(username="manager", password="test-password", role="admin")
        self.staff = User.objects.create_user(username="staff", password="test-password", role="staff")
        self.url = reverse("finance:user_new")

    def test_admin_can_create_staff_user(self):
        from accounts.models import User

        self.client.force_login(self.admin)
        response = self.client.post(self.url, {
            "username": "cashier2",
            "first_name": "Casey",
            "last_name": "Cashier",
            "email": "casey@example.com",
            "role": "staff",
            "password1": "Strong-demo-password-529!",
            "password2": "Strong-demo-password-529!",
        })

        self.assertRedirects(response, reverse("finance:payroll"))
        created_user = User.objects.get(username="cashier2")
        self.assertEqual(created_user.role, User.Role.STAFF)
        self.assertTrue(created_user.check_password("Strong-demo-password-529!"))

    def test_staff_cannot_open_user_creation_page(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)


# ---- attendance linked to payroll ------------------------------------------------------------
from datetime import datetime, time, timedelta  # noqa: E402

from django.utils import timezone  # noqa: E402

from accounts.models import AuditLog, User  # noqa: E402
from .forms import EmployeeForm, PayrollForm  # noqa: E402


def _aware(day, hour, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


def _shift(employee, day, complete=True):
    """A full 8:00-17:00 shift with a 1-hour break (8 paid hours), or one missing its time-out."""
    return Attendance.objects.create(
        employee=employee, work_date=day, check_in=_aware(day, 8),
        break_time_out=_aware(day, 12) if complete else None,
        break_time_in=_aware(day, 13) if complete else None,
        check_out=_aware(day, 17) if complete else None,
    )


class AttendancePayrollTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        # salary 6,500 per period / 13 working days = 500 per day
        self.emp = Employee.objects.create(name="Mika Santos", salary=Decimal("6500"))

    def test_summary_counts_days_and_net_hours(self):
        for n in (1, 2, 3):
            _shift(self.emp, self.today - timedelta(days=n))
        start, end = services.current_period()
        s = services.attendance_summary(self.emp, start, end)
        self.assertEqual(s["days"], 3)
        self.assertEqual(s["hours"], Decimal("24.00"))       # 3 x (9h - 1h break)
        self.assertEqual(s["daily_rate"], Decimal("500.00"))
        self.assertEqual(s["estimate"], Decimal("1500.00"))
        self.assertEqual(s["incomplete"], 0)

    def test_missing_time_out_still_counts_as_present_but_is_flagged(self):
        _shift(self.emp, self.today - timedelta(days=1))
        _shift(self.emp, self.today - timedelta(days=2), complete=False)
        start, end = services.current_period()
        s = services.attendance_summary(self.emp, start, end)
        self.assertEqual(s["days"], 2)
        self.assertEqual(s["incomplete"], 1)
        self.assertEqual(s["hours"], Decimal("8.00"))

    def test_attendance_outside_the_period_is_ignored(self):
        _shift(self.emp, self.today - timedelta(days=40))
        start, end = services.current_period()
        self.assertEqual(services.attendance_summary(self.emp, start, end)["days"], 0)

    def test_attendance_payroll_pays_days_times_daily_rate(self):
        for n in (1, 2, 3, 4):
            _shift(self.emp, self.today - timedelta(days=n))
        CashAdvance.objects.create(employee=self.emp, amount=500)
        rec = services.create_payroll(employee=self.emp, pay_type=PayrollRecord.PayType.ATTENDANCE)
        self.assertEqual(rec.amount, Decimal("2000.00"))
        self.assertEqual(rec.value, Decimal("500.00"))
        self.assertEqual(rec.days_worked, 4)
        self.assertEqual(rec.hours_worked, Decimal("32.00"))
        self.assertEqual(rec.advance_deducted, Decimal("500"))
        self.assertEqual(rec.net_pay, Decimal("1500.00"))

    def test_attendance_payroll_requires_attendance_and_a_salary(self):
        with self.assertRaisesMessage(ValueError, "no attendance recorded"):
            services.create_payroll(employee=self.emp, pay_type=PayrollRecord.PayType.ATTENDANCE)
        unpaid = Employee.objects.create(name="No Salary", salary=0)
        _shift(unpaid, self.today - timedelta(days=1))
        with self.assertRaisesMessage(ValueError, "Set a base salary"):
            services.create_payroll(employee=unpaid, pay_type=PayrollRecord.PayType.ATTENDANCE)

    def test_fixed_pay_also_snapshots_attendance(self):
        _shift(self.emp, self.today - timedelta(days=1))
        rec = services.create_payroll(employee=self.emp, pay_type=PayrollRecord.PayType.FIXED, value=Decimal("3000"))
        self.assertEqual((rec.amount, rec.days_worked, rec.hours_worked), (Decimal("3000.00"), 1, Decimal("8.00")))

    def test_form_requires_amount_except_for_attendance_pay(self):
        base = {"employee": self.emp.pk}
        self.assertFalse(PayrollForm({**base, "pay_type": "fixed", "value": "0"}).is_valid())
        self.assertFalse(PayrollForm({**base, "pay_type": "fixed", "value": ""}).is_valid())
        self.assertFalse(PayrollForm({**base, "pay_type": "percentage", "value": "120"}).is_valid())
        self.assertTrue(PayrollForm({**base, "pay_type": "percentage", "value": "20"}).is_valid())
        self.assertTrue(PayrollForm({**base, "pay_type": "attendance", "value": ""}).is_valid())

    def test_payroll_view_shows_error_instead_of_crashing(self):
        admin = User.objects.create_user("boss", password="x", role="admin")
        self.client.force_login(admin)
        response = self.client.post(reverse("finance:payroll_new"), {"employee": self.emp.pk, "pay_type": "attendance"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no attendance recorded")
        self.assertEqual(PayrollRecord.objects.count(), 0)


class EmployeeManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("boss", password="x", role="admin")
        self.client.force_login(self.admin)

    def _new_employee(self, **extra):
        data = {"name": "Ana Cruz", "position": "Service", "salary": "6500", "is_active": "on"}
        data.update(extra)
        return self.client.post(reverse("finance:employee_new"), data)

    def test_add_employee_only(self):
        response = self._new_employee()
        self.assertRedirects(response, reverse("finance:employees"))
        emp = Employee.objects.get(name="Ana Cruz")
        self.assertIsNone(emp.user)
        self.assertTrue(AuditLog.objects.filter(action="Added employee").exists())

    def test_add_employee_with_new_login(self):
        response = self._new_employee(create_login="on", username="ana", role="staff", password="Str0ng-pass-2026!")
        self.assertRedirects(response, reverse("finance:employees"))
        emp = Employee.objects.get(name="Ana Cruz")
        account = User.objects.get(username="ana")
        self.assertEqual(emp.user, account)
        self.assertEqual((account.first_name, account.last_name, account.role), ("Ana", "Cruz", "staff"))
        self.assertTrue(account.check_password("Str0ng-pass-2026!"))

    def test_weak_password_or_taken_username_blocks_everything(self):
        User.objects.create_user("taken", password="x")
        self.assertEqual(self._new_employee(create_login="on", username="ana", password="123").status_code, 200)
        self.assertEqual(self._new_employee(create_login="on", username="TAKEN", password="Str0ng-pass-2026!").status_code, 200)
        self.assertEqual(Employee.objects.count(), 0)
        self.assertFalse(User.objects.filter(username="ana").exists())

    def test_cannot_pick_existing_login_and_create_another(self):
        other = User.objects.create_user("other", password="x")
        form = EmployeeForm({"name": "Ana", "salary": "100", "is_active": "on", "user": other.pk,
                             "create_login": "on", "username": "ana2", "role": "staff", "password": "Str0ng-pass-2026!"})
        self.assertFalse(form.is_valid())

    def test_login_already_linked_is_not_offered_again(self):
        taken = User.objects.create_user("linked", password="x")
        Employee.objects.create(name="Someone", user=taken)
        form = EmployeeForm()
        self.assertNotIn(taken, form.fields["user"].queryset)

    def test_deactivate_and_reactivate(self):
        emp = Employee.objects.create(name="Jules", salary=100)
        self.client.post(reverse("finance:employee_toggle", args=[emp.pk]))
        emp.refresh_from_db()
        self.assertFalse(emp.is_active)
        self.client.post(reverse("finance:employee_toggle", args=[emp.pk]))
        emp.refresh_from_db()
        self.assertTrue(emp.is_active)
        self.assertEqual(self.client.get(reverse("finance:employee_toggle", args=[emp.pk])).status_code, 405)

    def test_toggle_ignores_external_redirect_targets(self):
        emp = Employee.objects.create(name="Jules", salary=100)
        response = self.client.post(reverse("finance:employee_toggle", args=[emp.pk]), {"next": "https://evil.example/"})
        self.assertRedirects(response, reverse("finance:employees"))

    def test_delete_blocked_when_employee_has_history_allowed_otherwise(self):
        used = Employee.objects.create(name="Has History", salary=100)
        _shift(used, timezone.localdate() - timedelta(days=1))
        clean = Employee.objects.create(name="Brand New", salary=100)
        self.client.post(reverse("finance:employee_delete", args=[used.pk]))
        self.assertTrue(Employee.objects.filter(pk=used.pk).exists())
        self.client.post(reverse("finance:employee_delete", args=[clean.pk]))
        self.assertFalse(Employee.objects.filter(pk=clean.pk).exists())

    def test_staff_cannot_manage_employees(self):
        staff = User.objects.create_user("cashier", password="x", role="staff")
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("finance:employees")).status_code, 403)
        self.assertEqual(self.client.post(reverse("finance:employee_new"), {"name": "X"}).status_code, 403)
