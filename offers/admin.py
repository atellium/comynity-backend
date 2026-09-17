from django.contrib import admin
from django.core.files.storage import default_storage
from django.utils.html import format_html

from offers.models import Offer


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "business",
        "status_display",
        "is_all_time",
        "starts_at",
        "expires_at",
        "is_active",
        "sort_order",
        "created_at",
    )
    list_filter = (
        "is_active",
        "is_all_time",
        "starts_at",
        "expires_at",
        "created_at",
    )
    search_fields = (
        "title",
        "description",
        "business__name",
        "business__slug",
    )
    autocomplete_fields = (
        "business",
        "image",
    )
    list_editable = ("is_all_time", "is_active", "sort_order")
    readonly_fields = (
        "id",
        "status_display",
        "image_preview",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"
    ordering = ("sort_order", "-created_at")
    list_select_related = ("business",)

    fieldsets = (
        (
            "Offer",
            {
                "fields": (
                    "id",
                    "business",
                    "title",
                    "description",
                    "terms",
                )
            },
        ),
        ("Media", {"fields": ("image", "image_preview")}),
        (
            "Availability",
            {
                "fields": (
                    "starts_at",
                    "expires_at",
                    "is_all_time",
                    "is_active",
                    "status_display",
                    "sort_order",
                )
            },
        ),
        (
            "Metadata",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    @admin.display(description="Status", ordering="is_active")
    def status_display(self, obj):
        return obj.status if obj else "-"

    @admin.display(description="Preview")
    def image_preview(self, obj):
        if obj and obj.image:
            url = default_storage.url(obj.image.object_key)
            return format_html(
                '<img src="{}" alt="" style="max-height: 180px; max-width: 320px; object-fit: contain;" />',
                url,
            )
        return "No image"
