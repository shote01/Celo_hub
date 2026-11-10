from decimal import Decimal

from django.test import TestCase

from . import services
from .models import CashAdvance, Employee, PayrollRecord


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
