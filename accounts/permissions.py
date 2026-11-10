from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def admin_required(view):
    """Function views: logged in AND admin role."""

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_celo_admin:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


class AdminRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_celo_admin:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
