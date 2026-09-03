from django.contrib import admin
from django.utils.html import format_html

from offers.models import Offer


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "business",
        "status_display",
        "starts_at",
        "expires_at",
        "is_active",
        "sort_order",
        "created_at",
    )
    list_filter = (
        "is_active",
        "starts_at",
        "expires_at",
        "created_at",
    )
    search_fields = (
        "title",
        "description",
        "business__name",
        "business__handle",
        "business__slug",
    )
    autocomplete_fields = ("business",)
    list_editable = ("is_active", "sort_order")
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
            return format_html(
                '<img src="{}" alt="" style="max-height: 180px; max-width: 320px; object-fit: contain;" />',
                obj.image.url,
            )
        return "No image"
