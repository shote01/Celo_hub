from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AuditLog, User


@admin.register(User)
class CeloUserAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "role", "is_active")
    fieldsets = UserAdmin.fieldsets + (("Celo", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Celo", {"fields": ("role",)}),)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "detail")
    list_filter = ("action",)
    readonly_fields = ("user", "action", "detail", "created_at")
