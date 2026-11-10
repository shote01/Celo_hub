from django import forms

from .models import Customer, Order


class SaleHeaderForm(forms.Form):
    order_type = forms.ChoiceField(choices=Order.OrderType.choices, label="Order type")
    payment_method = forms.ChoiceField(choices=Order.Payment.choices, label="Payment")
    customer = forms.ModelChoiceField(queryset=Customer.objects.all(), required=False,
                                      empty_label="No customer", label="Customer")


class CustomerForm(forms.ModelForm):
    phone = forms.CharField(max_length=30, required=False, label="Phone (optional)",
                            widget=forms.TextInput(attrs={"inputmode": "tel", "placeholder": "e.g. 0917 123 4567"}))
    notes = forms.CharField(max_length=200, required=False, label="Notes (optional)")

    class Meta:
        model = Customer
        fields = ["name", "phone", "notes"]

    def clean_phone(self):
        return " ".join(self.cleaned_data.get("phone", "").split())
