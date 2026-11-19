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
