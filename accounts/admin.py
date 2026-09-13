from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import UserAddForm
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = UserAddForm
    ordering = ("phone",)
    list_display = (
        "phone",
        "full_name",
        "email",
        "gender",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = ("is_active", "is_staff", "is_superuser", "gender")
    search_fields = ("phone", "full_name", "email")
    readonly_fields = ("profile_color", "last_login", "date_joined")
    date_hierarchy = "date_joined"
    list_per_page = 50
    save_on_top = True

    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        (
            "Personal information",
            {
                "fields": (
                    "full_name",
                    "email",
                    "gender",
                    "date_of_birth",
                    "profile_color",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "phone",
                    "full_name",
                    "email",
                    "gender",
                    "date_of_birth",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )
