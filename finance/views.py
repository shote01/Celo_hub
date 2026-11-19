from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

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
@admin_required
def payroll_list(request):
    employees = Employee.objects.filter(is_active=True).prefetch_related("payroll_records")
    rows = []
    for emp in employees:
        last = emp.payroll_records.first()
        rows.append({"emp": emp, "last": last, "advance": emp.outstanding_advance})
    return render(request, "finance/payroll_list.html", {
        "rows": rows, "records": PayrollRecord.objects.select_related("employee")[:30],
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
    form = PayrollForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        rec = services.create_payroll(employee=d["employee"], pay_type=d["pay_type"], value=d["value"])
        AuditLog.record(request.user, "Payroll record", f"{rec.employee} net PHP {rec.net_pay}")
        messages.success(request, f"{rec.employee}: PHP {rec.amount} less advances PHP {rec.advance_deducted} = PHP {rec.net_pay}.")
        return redirect("finance:payroll")
    return _form_page(request, form, "Employee payroll record", "finance:payroll")


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


@admin_required
def employee_edit(request, pk=None):
    emp = get_object_or_404(Employee, pk=pk) if pk else None
    form = EmployeeForm(request.POST or None, instance=emp)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("finance:payroll")
    return _form_page(request, form, "Edit employee" if emp else "Add employee", "finance:payroll")
