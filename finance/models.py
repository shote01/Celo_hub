from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Expense(models.Model):
    class Category(models.TextChoices):
        UTILITIES = "utilities", "Utilities"
        RENT = "rent", "Rent"
        OTHER = "other", "Other"

    category = models.CharField(max_length=10, choices=Category.choices, default=Category.UTILITIES)
    description = models.CharField(max_length=160, blank=True, help_text="e.g. Electricity + water")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    incurred_on = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["-incurred_on", "-id"]

    def __str__(self):
        return f"{self.get_category_display()} PHP {self.amount}"


class Employee(models.Model):
    name = models.CharField(max_length=120)
    position = models.CharField(max_length=60, blank=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                 help_text="Base pay per 15-day period.")
    is_active = models.BooleanField(default=True)
    user = models.OneToOneField("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                help_text="Link to a login account, if they have one.")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def outstanding_advance(self):
        return self.advances.filter(settled_in__isnull=True).aggregate(t=models.Sum("amount"))["t"] or Decimal("0")


class PayrollRecord(models.Model):
    class PayType(models.TextChoices):
        FIXED = "fixed", "Fixed Amount"
        PERCENTAGE = "percentage", "Percentage of Gross Sales"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="payroll_records")
    pay_type = models.CharField(max_length=12, choices=PayType.choices, default=PayType.FIXED)
    value = models.DecimalField(max_digits=10, decimal_places=2, help_text="PHP amount, or percent")
    period_start = models.DateField()
    period_end = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)            # computed gross pay
    advance_deducted = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee} {self.period_start}..{self.period_end}"


class CashAdvance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="advances")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    given_on = models.DateField(default=timezone.localdate)
    note = models.CharField(max_length=160, blank=True)
    settled_in = models.ForeignKey(PayrollRecord, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="settled_advances")

    class Meta:
        ordering = ["-given_on", "-id"]

    def __str__(self):
        return f"{self.employee} advance PHP {self.amount}"
