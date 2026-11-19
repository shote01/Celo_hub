from django import forms
from django.contrib.auth.forms import UserCreationForm

from accounts.models import User
from .models import CashAdvance, Employee, Expense, PayrollRecord


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["category", "description", "amount", "incurred_on"]
        widgets = {"incurred_on": forms.DateInput(attrs={"type": "date"})}


class PayrollForm(forms.Form):
    employee = forms.ModelChoiceField(queryset=Employee.objects.filter(is_active=True), label="Name")
    pay_type = forms.ChoiceField(choices=PayrollRecord.PayType.choices, label="Payment select")
    value = forms.DecimalField(min_value=0, max_digits=10, decimal_places=2,
                               label="Amount (PHP) or percent of gross sales")

    def clean(self):
        data = super().clean()
        if data.get("pay_type") == PayrollRecord.PayType.PERCENTAGE and data.get("value") is not None:
            if data["value"] > 100:
                self.add_error("value", "A percentage can't be more than 100.")
        return data


class AdvanceForm(forms.ModelForm):
    class Meta:
        model = CashAdvance
        fields = ["employee", "amount", "given_on", "note"]
        widgets = {"given_on": forms.DateInput(attrs={"type": "date"})}


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["name", "position", "salary", "is_active", "user"]


class CeloUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(("username", "first_name", "last_name", "email", "role", "password1", "password2"))
