from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from celo.utils import day_end, day_start, require_positive_decimal
from inventory.models import WasteRecord
from sales.models import Order

from .models import Expense, PayrollRecord

ZERO = Decimal("0")


def current_period():
    """The rolling 15-day window the owner reviews (charter: every 15 days)."""
    end = timezone.localdate()
    return end - timedelta(days=settings.CELO_PAYROLL_PERIOD_DAYS - 1), end


def gross_sales(start, end):
    return Order.objects.filter(created_at__gte=day_start(start), created_at__lt=day_end(end)) \
        .aggregate(t=Sum("total"))["t"] or ZERO


def accounting_breakdown(start, end):
    """Gross sales - waste - expenses - payroll = net income (the design's 'Accounting breakdown')."""
    gross = gross_sales(start, end)
    waste = WasteRecord.objects.filter(recorded_at__gte=day_start(start), recorded_at__lt=day_end(end)) \
        .aggregate(t=Sum("cost"))["t"] or ZERO
    expenses = Expense.objects.filter(incurred_on__range=(start, end)).aggregate(t=Sum("amount"))["t"] or ZERO
    payroll = PayrollRecord.objects.filter(period_end__range=(start, end)).aggregate(t=Sum("amount"))["t"] or ZERO
    return {
        "start": start, "end": end, "gross": gross, "waste": waste,
        "expenses": expenses, "payroll": payroll,
        "net": gross - waste - expenses - payroll,
    }


@transaction.atomic
def create_payroll(*, employee, pay_type, value):
    """Fixed: pay `value` PHP. Percentage: pay value% of gross sales in the current 15-day period.
    Outstanding cash advances are deducted from net pay and marked settled."""
    start, end = current_period()
    value = require_positive_decimal(value, "pay value")
    if pay_type == PayrollRecord.PayType.PERCENTAGE and value > Decimal("100"):
        raise ValueError("Percentage pay cannot exceed 100%.")
    if pay_type == PayrollRecord.PayType.PERCENTAGE:
        amount = (gross_sales(start, end) * value / Decimal("100")).quantize(Decimal("0.01"))
    else:
        amount = value.quantize(Decimal("0.01"))

    # Settle whole advances only, oldest first, as far as this pay covers. Anything that
    # doesn't fit stays outstanding and carries over, so nothing is ever deducted twice.
    cap = amount
    to_settle, deducted = [], ZERO
    for adv in employee.advances.filter(settled_in__isnull=True).order_by("given_on", "id"):
        if adv.amount <= cap:
            to_settle.append(adv)
            cap -= adv.amount
            deducted += adv.amount
    record = PayrollRecord.objects.create(
        employee=employee, pay_type=pay_type, value=value, period_start=start, period_end=end,
        amount=amount, advance_deducted=deducted, net_pay=amount - deducted,
    )
    for adv in to_settle:
        adv.settled_in = record
        adv.save(update_fields=["settled_in"])
    return record
