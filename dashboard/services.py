from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.db.models import Count, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek, TruncYear
from django.utils import timezone
from celo.utils import day_end, day_start
from finance.models import Employee
from inventory.models import Product, StockBatch
from sales.models import Order, OrderItem

TRUNC = {"daily": TruncDay, "weekly": TruncWeek, "monthly": TruncMonth, "yearly": TruncYear}


def bestsellers(start, end, limit=3):
    return list(
        OrderItem.objects.filter(order__created_at__gte=day_start(start), order__created_at__lt=day_end(end))
        .values("product__name").annotate(sold=Sum("quantity")).order_by("-sold")[:limit]
    )


def daily_series(start, end):
    """One entry per day (zero-filled) for the 'Sales pulse' bar chart."""
    rows = (
        Order.objects.filter(created_at__gte=day_start(start), created_at__lt=day_end(end))
        .annotate(d=TruncDay("created_at", tzinfo=timezone.get_current_timezone()))
        .values("d").annotate(t=Sum("total"))
    )
    by_day = {r["d"].date(): r["t"] for r in rows}
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    values = [by_day.get(d, Decimal("0")) for d in days]
    peak = max(values) if values and max(values) > 0 else Decimal("1")
    avg = sum(values) / len(values) if values else Decimal("0")
    return [
        {"date": d, "value": v, "height": int(v / peak * 100), "low": avg > 0 and v < avg * Decimal("0.6")}
        for d, v in zip(days, values)
    ]


def attention_counts():
    warn = timezone.localdate() + timedelta(days=settings.CELO_FIFO_WARNING_DAYS)
    fifo = StockBatch.objects.filter(remaining_qty__gt=0, expiry_date__lte=warn).count()
    low = sum(1 for p in Product.objects.filter(is_active=True, reorder_level__gt=0) if p.on_hand <= p.reorder_level)
    advances = sum((e.outstanding_advance for e in Employee.objects.filter(is_active=True)), Decimal("0"))
    return {"fifo": fifo, "low": low, "advances": advances}


def sales_report(period, start, end):
    """Grouped totals for the Reports page: daily / weekly / monthly / yearly."""
    trunc = TRUNC[period]
    rows = (
        Order.objects.filter(created_at__gte=day_start(start), created_at__lt=day_end(end))
        .annotate(bucket=trunc("created_at", tzinfo=timezone.get_current_timezone()))
        .values("bucket").annotate(total=Sum("total"), orders=Count("id"))
        .order_by("-bucket")
    )
    return list(rows)
