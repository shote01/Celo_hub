from django.urls import path

from . import views

app_name = "finance"
urlpatterns = [
    path("attendance/", views.attendance, name="attendance"),
    path("expenses/", views.expense_list, name="expenses"),
    path("expenses/new/", views.expense_edit, name="expense_new"),
    path("expenses/<int:pk>/edit/", views.expense_edit, name="expense_edit"),
    path("expenses/<int:pk>/delete/", views.expense_delete, name="expense_delete"),
    path("payroll/", views.payroll_list, name="payroll"),
    path("users/new/", views.user_new, name="user_new"),
    path("payroll/new/", views.payroll_new, name="payroll_new"),
    path("payroll/<int:pk>/delete/", views.payroll_delete, name="payroll_delete"),
    path("advances/new/", views.advance_new, name="advance_new"),
    path("employees/new/", views.employee_edit, name="employee_new"),
    path("employees/<int:pk>/edit/", views.employee_edit, name="employee_edit"),
]
