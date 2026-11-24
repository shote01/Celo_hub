from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import AuditLog
from accounts.permissions import admin_required

from . import services
from .forms import AdvanceForm, CeloUserCreationForm, EmployeeForm, ExpenseForm, PayrollForm
from .models import Attendance, Employee, Expense, PayrollRecord


def _form_page(request, form, title, cancel_url, submit="Save"):
    return render(request, "form_card.html", {"title": title, "form": form, "submit": submit, "cancel_url": cancel_url})


@login_required
def attendance(request):
    employee = Employee.objects.filter(user=request.user, is_active=True).first()
    today = timezone.localdate()

    if request.method == "POST":
        if employee is None:
            messages.error(request, "Your login is not linked to an active employee. Ask an administrator to link it.")
            return redirect("finance:attendance")

        if request.POST.get("action") == "time_in":
            _, created = Attendance.objects.get_or_create(
                employee=employee,
                work_date=today,
                defaults={"check_in": timezone.now()},
            )
            if created:
                messages.success(request, "Time-in recorded.")
            else:
                messages.info(request, "A time-in is already recorded for today.")
        elif request.POST.get("action") == "time_out":
            record = Attendance.objects.filter(employee=employee, work_date=today, check_out__isnull=True).first()
            if record is None:
                messages.error(request, "There is no open time-in to record a time-out for today.")
            elif record.break_time_out and not record.break_time_in:
                messages.error(request, "Record your break time-in before ending the workday.")
            else:
                record.check_out = timezone.now()
                record.save(update_fields=["check_out"])
                messages.success(request, "Time-out recorded.")
        elif request.POST.get("action") == "break_time_out":
            record = Attendance.objects.filter(
                employee=employee, work_date=today, check_out__isnull=True
            ).first()
            if record is None:
                messages.error(request, "Time in before starting a break.")
            elif record.break_time_out:
                messages.info(request, "Today's break has already been recorded.")
            else:
                record.break_time_out = timezone.now()
                record.save(update_fields=["break_time_out"])
                messages.success(request, "Break time-out recorded.")
        elif request.POST.get("action") == "break_time_in":
            record = Attendance.objects.filter(
                employee=employee,
                work_date=today,
                break_time_out__isnull=False,
                break_time_in__isnull=True,
                check_out__isnull=True,
            ).first()
            if record is None:
                messages.error(request, "There is no active break to end.")
            else:
                record.break_time_in = timezone.now()
                record.save(update_fields=["break_time_in"])
                messages.success(request, "Break time-in recorded.")
        else:
            messages.error(request, "Unknown attendance action.")
        return redirect("finance:attendance")

    current_record = Attendance.objects.filter(employee=employee, work_date=today).first() if employee else None
    records = Attendance.objects.select_related("employee")
    if not request.user.is_celo_admin:
        records = records.filter(employee=employee) if employee else records.none()

    return render(request, "finance/attendance.html", {
        "employee": employee,
        "current_record": current_record,
        "records": records[:100],
        "is_admin": request.user.is_celo_admin,
    })


# ---- expense ledger --------------------------------------------------------
@admin_required
def expense_list(request):
    start, end = services.current_period()
    return render(request, "finance/expense_list.html", {
        "expenses": Expense.objects.filter(incurred_on__range=(start, end)),
        "b": services.accounting_breakdown(start, end),
    })


@admin_required
def expense_edit(request, pk=None):
    expense = get_object_or_404(Expense, pk=pk) if pk else None
    form = ExpenseForm(request.POST or None, instance=expense)
    if request.method == "POST" and form.is_valid():
        e = form.save()
        AuditLog.record(request.user, "Saved expense", f"{e.get_category_display()} PHP {e.amount}")
        return redirect("finance:expenses")
    return _form_page(request, form, "Expense ledger", "finance:expenses", "Confirm")


@admin_required
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == "POST":
        AuditLog.record(request.user, "Deleted expense", str(expense))
        expense.delete()
        return redirect("finance:expenses")
    return render(request, "confirm_delete.html", {"object": expense, "cancel_url": "finance:expenses"})


# ---- payroll & cash advances ----------------------------------------------
def _summaries(employees, start, end):
    """Attendance + pay figures per employee, as plain strings (used by the payroll form's live preview)."""
    out = {}
    for emp in employees:
        att = services.attendance_summary(emp, start, end)
        out[str(emp.pk)] = {
            "name": emp.name, "salary": str(emp.salary), "daily_rate": str(att["daily_rate"]),
            "days": att["days"], "hours": str(att["hours"]), "incomplete": att["incomplete"],
            "estimate": str(att["estimate"]), "advance": str(emp.outstanding_advance),
        }
    return out


@admin_required
def payroll_list(request):
    start, end = services.current_period()
    employees = Employee.objects.filter(is_active=True).prefetch_related("payroll_records").select_related("user")
    rows = []
    for emp in employees:
        rows.append({
            "emp": emp, "last": emp.payroll_records.first(), "advance": emp.outstanding_advance,
            "att": services.attendance_summary(emp, start, end),
        })
    return render(request, "finance/payroll_list.html", {
        "rows": rows, "records": PayrollRecord.objects.select_related("employee")[:30],
        "start": start, "end": end, "workdays": services.workdays_per_period(),
    })


@admin_required
def user_new(request):
    form = CeloUserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        account = form.save()
        AuditLog.record(request.user, "Created user", f"{account.username} ({account.get_role_display()})")
        messages.success(request, f"User account '{account.username}' was created.")
        return redirect("finance:payroll")
    return render(request, "finance/user_form.html", {"form": form})


@admin_required
def payroll_new(request):
    start, end = services.current_period()
    employees = list(Employee.objects.filter(is_active=True))
    initial = {}
    preselected = request.GET.get("employee", "")
    if preselected.isdigit() and any(e.pk == int(preselected) for e in employees):
        initial["employee"] = int(preselected)
    form = PayrollForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            rec = services.create_payroll(employee=d["employee"], pay_type=d["pay_type"], value=d["value"])
        except ValueError as exc:      # business-rule errors are shown on the form, not as a 500 page
            form.add_error(None, str(exc))
        else:
            AuditLog.record(request.user, "Payroll record", f"{rec.employee} net PHP {rec.net_pay}")
            messages.success(request, f"{rec.employee}: PHP {rec.amount} less advances PHP {rec.advance_deducted} = PHP {rec.net_pay}.")
            return redirect("finance:payroll")
    return render(request, "finance/payroll_form.html", {
        "form": form, "summaries": _summaries(employees, start, end), "start": start, "end": end,
        "workdays": services.workdays_per_period(),
    })


@admin_required
def payroll_delete(request, pk):
    rec = get_object_or_404(PayrollRecord, pk=pk)
    if request.method == "POST":
        AuditLog.record(request.user, "Deleted payroll record", str(rec))
        rec.delete()          # CashAdvance.settled_in is SET_NULL, so advances become outstanding again
        return redirect("finance:payroll")
    return render(request, "confirm_delete.html", {"object": rec, "cancel_url": "finance:payroll"})


@admin_required
def advance_new(request):
    form = AdvanceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        adv = form.save()
        AuditLog.record(request.user, "Cash advance", f"{adv.employee} PHP {adv.amount}")
        return redirect("finance:payroll")
    return _form_page(request, form, "Cash advance", "finance:payroll")


# ---- employee management ---------------------------------------------------
@admin_required
def employee_list(request):
    status = request.GET.get("status", "active")
    q = request.GET.get("q", "").strip()
    employees = Employee.objects.select_related("user")
    if status == "active":
        employees = employees.filter(is_active=True)
    elif status == "inactive":
        employees = employees.filter(is_active=False)
    else:
        status = "all"
    if q:
        employees = employees.filter(Q(name__icontains=q) | Q(position__icontains=q))
    start, end = services.current_period()
    rows = [{"emp": e, "att": services.attendance_summary(e, start, end), "advance": e.outstanding_advance}
            for e in employees]
    return render(request, "finance/employee_list.html", {
        "rows": rows, "status": status, "q": q, "start": start, "end": end,
        "counts": {"active": Employee.objects.filter(is_active=True).count(),
                   "inactive": Employee.objects.filter(is_active=False).count()},
    })


@admin_required
def employee_edit(request, pk=None):
    emp = get_object_or_404(Employee, pk=pk) if pk else None
    form = EmployeeForm(request.POST or None, instance=emp)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        AuditLog.record(request.user, "Updated employee" if emp else "Added employee", saved.name)
        if form.created_user:
            AuditLog.record(request.user, "Created user", f"{form.created_user.username} ({form.created_user.get_role_display()})")
            messages.success(request, f"{saved.name} was added with login '{form.created_user.username}'.")
        else:
            messages.success(request, f"{saved.name} was {'updated' if emp else 'added'}.")
        return redirect("finance:employees")
    return render(request, "finance/employee_form.html", {"form": form, "employee": emp})


@admin_required
@require_POST
def employee_toggle(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    emp.is_active = not emp.is_active
    emp.save(update_fields=["is_active"])
    AuditLog.record(request.user, "Reactivated employee" if emp.is_active else "Deactivated employee", emp.name)
    messages.success(request, f"{emp.name} is now {'active' if emp.is_active else 'inactive'}.")
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return redirect(target)
    return redirect("finance:employees")


@admin_required
def employee_delete(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    has_history = (emp.payroll_records.exists() or emp.advances.exists() or emp.attendance_records.exists())
    if has_history:
        messages.error(request, f"{emp.name} has payroll or attendance history, so it can't be deleted. Deactivate the employee instead.")
        return redirect("finance:employees")
    if request.method == "POST":
        AuditLog.record(request.user, "Deleted employee", emp.name)
        emp.delete()
        messages.success(request, f"{emp.name} was deleted.")
        return redirect("finance:employees")
    return render(request, "confirm_delete.html", {"object": emp, "cancel_url": "finance:employees"})
