from django import forms

from .models import User


class ProfileForm(forms.ModelForm):
    """What a user may change about themselves. Username and role are admin-controlled."""

    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, required=False, label="Last name")
    email = forms.EmailField(required=False, label="Email (optional)")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
