from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

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
    value = forms.DecimalField(required=False, max_digits=10, decimal_places=2,
                               label="Amount (PHP) or percent of gross sales",
                               help_text="Not used for attendance pay: it is worked out from days present.")

    def clean(self):
        data = super().clean()
        pay_type, value = data.get("pay_type"), data.get("value")
        if pay_type and pay_type != PayrollRecord.PayType.ATTENDANCE:
            if value is None or value <= 0:
                self.add_error("value", "Enter an amount greater than zero.")
            elif pay_type == PayrollRecord.PayType.PERCENTAGE and value > 100:
                self.add_error("value", "A percentage can't be more than 100.")
        return data


class AdvanceForm(forms.ModelForm):
    class Meta:
        model = CashAdvance
        fields = ["employee", "amount", "given_on", "note"]
        widgets = {"given_on": forms.DateInput(attrs={"type": "date"})}


class EmployeeForm(forms.ModelForm):
    """Add / edit an employee. When adding, the admin can also create their login in one go."""

    create_login = forms.BooleanField(required=False, label="Also create a login for this employee")
    username = forms.CharField(required=False, max_length=150, label="Username")
    role = forms.ChoiceField(choices=User.Role.choices, initial=User.Role.STAFF, required=False, label="Access")
    password = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False), label="Password")

    field_order = ["name", "position", "salary", "is_active", "user",
                   "create_login", "username", "role", "password"]

    class Meta:
        model = Employee
        fields = ["name", "position", "salary", "is_active", "user"]
        labels = {"user": "Link an existing login"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # only logins that aren't already tied to another employee (plus this employee's own)
        self.fields["user"].queryset = User.objects.filter(
            Q(employee__isnull=True) | Q(pk=self.instance.user_id)
        ).order_by("username")
        self.fields["user"].help_text = "Needed for the employee to use Attendance."
        if self.instance.pk:     # creating a login is only offered when adding
            for name in ("create_login", "username", "role", "password"):
                del self.fields[name]

    @staticmethod
    def _split_name(full_name):
        parts = full_name.split(None, 1)
        return (parts[0][:150], parts[1][:150]) if len(parts) > 1 else (parts[0][:150] if parts else "", "")

    def clean(self):
        data = super().clean()
        if not data.get("create_login"):
            return data
        if data.get("user"):
            self.add_error("create_login", "Choose an existing login or create a new one, not both.")
            return data
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if not username:
            self.add_error("username", "Enter a username for the new login.")
        elif User.objects.filter(username__iexact=username).exists():
            self.add_error("username", "That username is already taken.")
        if not password:
            self.add_error("password", "Enter a password for the new login.")
        elif username:
            first, last = self._split_name(data.get("name") or "")
            try:
                validate_password(password, user=User(username=username, first_name=first, last_name=last))
            except ValidationError as exc:
                self.add_error("password", exc)
        data["username"] = username
        return data

    @transaction.atomic
    def save(self, commit=True):
        employee = super().save(commit=False)
        self.created_user = None
        if self.cleaned_data.get("create_login"):
            first, last = self._split_name(employee.name)
            self.created_user = User.objects.create_user(
                self.cleaned_data["username"], password=self.cleaned_data["password"],
                first_name=first, last_name=last, role=self.cleaned_data.get("role") or User.Role.STAFF,
            )
            employee.user = self.created_user
        employee.save()
        return employee


class CeloUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(("username", "first_name", "last_name", "email", "role", "password1", "password2"))
