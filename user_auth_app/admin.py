from django.contrib import admin

from user_auth_app.models import User


@admin.register(User)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin configuration for User instances"""

    list_display = ("username", "is_active",
                    "is_staff", "is_superuser")
