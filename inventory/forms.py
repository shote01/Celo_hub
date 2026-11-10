from django import forms

from .models import Product, WasteRecord


class ReceiveStockForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_active=True))
    expiry_date = forms.DateField(required=False, label="Expiry date (optional)",
                                  widget=forms.DateInput(attrs={"type": "date"}))
    amount = forms.DecimalField(min_value=0.01, max_digits=10, decimal_places=2)


class WasteForm(forms.ModelForm):
    class Meta:
        model = WasteRecord
        fields = ["product", "quantity", "reason", "note"]

    def clean(self):
        data = super().clean()
        product, qty = data.get("product"), data.get("quantity")
        if product and qty and qty > product.on_hand:
            self.add_error("quantity", f"Only {product.on_hand} {product.unit} on hand.")
        return data


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "kind", "category", "unit", "price", "unit_cost", "reorder_level", "is_active"]
