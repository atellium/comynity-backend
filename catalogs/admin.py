from django.contrib import admin
from django.utils.html import format_html

from .models import Catalog, CatalogCategory, CatalogImage


class CatalogImageInline(admin.TabularInline):
    model = CatalogImage
    extra = 1
    fields = (
        "image",
        "image_preview",
        "alt_text",
        "is_primary",
        "is_active",
        "sort_order",
    )
    readonly_fields = ("image_preview",)
    ordering = ("sort_order", "created_at")

    @admin.display(description="Preview")
    def image_preview(self, obj):
        if obj.pk and obj.image:
            return format_html(
                '<img src="{}" style="width:80px;height:80px;'
                'object-fit:cover;border-radius:8px;" />',
                obj.image.url,
            )
        return "—"


@admin.register(Catalog)
class CatalogAdmin(admin.ModelAdmin):
    inlines = (CatalogImageInline,)

    list_display = (
        "name",
        "public_id",
        "business",
        "type",
        "price_type",
        "price",
        "is_active",
        "is_featured",
        "sort_order",
        "updated_at",
    )
    list_editable = ("is_active", "is_featured", "sort_order")
    list_filter = ("type", "price_type", "is_active", "is_featured")
    search_fields = (
        "name",
        "public_id",
        "slug",
        "business__name",
    )
    autocomplete_fields = ("business", "categories")
    list_select_related = ("business",)
    readonly_fields = (
        "id",
        "public_id",
        "slug",
        "created_at",
        "updated_at",
    )
    ordering = ("sort_order", "-created_at")
    list_per_page = 50
    save_on_top = True

    fieldsets = (
        (
            "Catalog Item",
            {
                "fields": (
                    "business",
                    "type",
                    "name",
                    "description",
                    "categories",
                )
            },
        ),
        (
            "Pricing",
            {
                "fields": (
                    "price_type",
                    "price",
                    "max_price",
                    "original_price",
                )
            },
        ),
        (
            "Details",
            {"fields": ("variants", "specifications", "custom_fields")},
        ),
        (
            "Visibility and Ordering",
            {"fields": ("is_active", "is_featured", "sort_order")},
        ),
        (
            "System",
            {
                "classes": ("collapse",),
                "fields": (
                    "id",
                    "public_id",
                    "slug",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )


@admin.register(CatalogCategory)
class CatalogCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "label",
        "type",
        "parent",
        "is_active",
        "is_featured",
        "is_display",
        "sort_order",
        "updated_at",
    )
    list_editable = (
        "is_active",
        "is_featured",
        "is_display",
        "sort_order",
    )
    list_filter = (
        "type",
        "is_active",
        "is_featured",
        "is_display",
    )
    search_fields = (
        "name",
        "label",
        "aliases",
        "slug",
        "parent__name",
    )
    autocomplete_fields = ("parent",)
    list_select_related = ("parent",)
    readonly_fields = (
        "image_preview",
        "created_at",
        "updated_at",
    )
    ordering = (
        "type",
        "sort_order",
        "name",
    )
    list_per_page = 50
    save_on_top = True

    fieldsets = (
        (
            "Category",
            {
                "fields": (
                    "name",
                    "label",
                    "type",
                    "parent",
                    "aliases",
                )
            },
        ),
        ("URL", {"fields": ("slug",)}),
        ("Image", {"fields": ("image", "image_preview")}),
        ("Ordering", {"fields": ("sort_order",)}),
        (
            "Visibility",
            {"fields": ("is_active", "is_featured", "is_display")},
        ),
        (
            "System",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    @admin.display(description="Preview")
    def image_preview(self, obj):
        if obj.pk and obj.image:
            return format_html(
                '<img src="{}" style="width:100px;height:100px;'
                'object-fit:cover;border-radius:8px;" />',
                obj.image.url,
            )
        return "—"
