import csv
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.models import AuditLog
from accounts.permissions import admin_required
from celo.utils import day_end, day_start
from finance import services as fin
from sales.models import Order

from . import services


@login_required
def home(request):
    start, end = fin.current_period()
    if request.user.is_celo_admin:
        b = fin.accounting_breakdown(start, end)
        return render(request, "dashboard/admin_home.html", {
            "b": b, "series": services.daily_series(start, end),
            "alerts": services.attention_counts(), "top": services.bestsellers(start, end),
        })
    # Staff: individual performance only (charter: "view individual performance metrics")
    mine = Order.objects.filter(created_by=request.user)
    today = mine.filter(created_at__gte=day_start(timezone.localdate()))
    period = mine.filter(created_at__gte=day_start(start), created_at__lt=day_end(end))
    return render(request, "dashboard/staff_home.html", {
        "today_count": today.count(), "today_total": today.aggregate(t=Sum("total"))["t"] or 0,
        "period_count": period.count(), "period_total": period.aggregate(t=Sum("total"))["t"] or 0,
        "recent": mine[:5],
    })


@admin_required
def reports(request):
    period = request.GET.get("period", "daily")
    if period not in services.TRUNC:
        period = "daily"
    span = {"daily": 14, "weekly": 90, "monthly": 365, "yearly": 365 * 5}[period]
    end = timezone.localdate()
    start = end - timedelta(days=span)
    rows = services.sales_report(period, start, end)

    if request.GET.get("format") == "csv":
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="celo-sales-{period}.csv"'
        w = csv.writer(resp)
        w.writerow(["period_start", "orders", "gross_sales"])
        for r in rows:
            w.writerow([r["bucket"].date(), r["orders"], r["total"]])
        return resp

    return render(request, "dashboard/reports.html", {
        "period": period, "rows": rows, "top": services.bestsellers(start, end, limit=10),
        "b": fin.accounting_breakdown(start, end), "start": start, "end": end,
    })


@admin_required
def audit_log(request):
    return render(request, "dashboard/audit_log.html", {"entries": AuditLog.objects.select_related("user")[:200]})
