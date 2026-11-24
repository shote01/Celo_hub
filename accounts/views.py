from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from finance.models import Employee

from .forms import ProfileForm
from .models import AuditLog


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        AuditLog.record(request.user, "Updated profile", request.user.username)
        messages.success(request, "Your profile was updated.")
        return redirect("accounts:profile")
    employee = Employee.objects.filter(user=request.user).first()
    return render(request, "accounts/profile.html", {"form": form, "employee": employee})


class CeloPasswordChangeView(PasswordChangeView):
    """Django's built-in flow (keeps the user logged in) plus a message and an audit entry."""

    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        response = super().form_valid(form)
        AuditLog.record(self.request.user, "Changed password", self.request.user.username)
        messages.success(self.request, "Your password was changed.")
        return response
