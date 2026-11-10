from django.contrib import admin

from .models import CashAdvance, Employee, Expense, PayrollRecord

for m in (Expense, Employee, PayrollRecord, CashAdvance):
    admin.site.register(m)
