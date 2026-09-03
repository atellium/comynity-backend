from django.contrib import admin

from categories.models import BusinessCategory, ProductCategory


class BaseCategoryAdmin(admin.ModelAdmin):
    """Shared admin configuration for category taxonomies."""

    search_fields = ("name", "label", "display_name", "aliases", "slug")
    prepopulated_fields = {"slug": ("label",)}
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 50
    save_on_top = True


@admin.register(BusinessCategory)
class BusinessCategoryAdmin(BaseCategoryAdmin):
    list_display = (
        "name",
        "label",
        "display_name",
        "is_active",
        "is_featured",
        "sort_order",
        "updated_at",
    )
    list_editable = (
        "is_active",
        "is_featured",
        "sort_order",
    )
    list_filter = ("is_active", "is_featured")
    ordering = ("sort_order", "name")
    fieldsets = (
        (
            "Category",
            {"fields": ("name", "display_name", "aliases", "image")},
        ),
        ("URL", {"fields": ("label", "slug")}),
        ("Ordering", {"fields": ("sort_order",)}),
        (
            "Visibility",
            {"fields": ("is_active", "is_featured")},
        ),
        (
            "System",
            {"classes": ("collapse",), "fields": ("created_at", "updated_at")},
        ),
    )


@admin.register(ProductCategory)
class ProductCategoryAdmin(BaseCategoryAdmin):
    list_display = (
        "name",
        "label",
        "display_name",
        "parent",
        "is_active",
        "is_featured",
        "updated_at",
    )
    list_editable = (
        "is_active",
        "is_featured",
    )
    list_filter = ("is_active", "is_featured", "parent")
    list_select_related = ("parent",)
    ordering = ("name",)
    fieldsets = (
        (
            "Category",
            {"fields": ("name", "display_name", "aliases", "parent", "image")},
        ),
        ("URL", {"fields": ("label", "slug")}),
        (
            "Visibility",
            {"fields": ("is_active", "is_featured")},
        ),
        (
            "System",
            {"classes": ("collapse",), "fields": ("created_at", "updated_at")},
        ),
    )
