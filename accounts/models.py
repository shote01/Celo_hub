from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Login account. Role drives what the navigation and views expose."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        STAFF = "staff", "Staff"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)

    @property
    def is_celo_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN


class AuditLog(models.Model):
    """Activity log shown to admins (charter: activity and audit log monitoring)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="audit_entries"
    )
    action = models.CharField(max_length=60)
    detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action}"

    @classmethod
    def record(cls, user, action, detail=""):
        cls.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            action=action,
            detail=detail[:255],
        )
