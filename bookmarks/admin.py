from django.contrib import admin

from bookmarks.models import SavedItem


@admin.register(SavedItem)
class SavedItemAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "item_type",
        "object_id",
        "created_at",
    )
    list_filter = ("item_type", "created_at")
    search_fields = (
        "user__phone",
        "user__full_name",
        "user__email",
        "=object_id",
    )
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)
    list_select_related = ("user",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 50
