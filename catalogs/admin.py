from django.contrib import admin
from django.db.models import Count

from catalogs.models import Catalog


@admin.register(Catalog)
class CatalogAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "public_id",
        "business",
        "type",
        "is_active",
        "is_available",
        "image_count",
        "created_at",
    )

    list_filter = (
        "type",
        "is_active",
        "is_available",
        "created_at",
    )

    search_fields = (
        "name",
        "public_id",
        "slug",
        "description",
        "business__name",
        "business__slug",
    )

    autocomplete_fields = (
        "business",
        "images",
    )

    readonly_fields = (
        "id",
        "public_id",
        "slug",
        "created_at",
        "updated_at",
    )

    list_editable = (
        "is_active",
        "is_available",
    )

    list_select_related = (
        "business",
    )

    ordering = (
        "name",
        "-created_at",
    )

    date_hierarchy = "created_at"
    list_per_page = 50
    save_on_top = True

    fieldsets = (
        (
            "Catalog",
            {
                "fields": (
                    "business",
                    "type",
                    "name",
                    "description",
                )
            },
        ),
        (
            "Media",
            {
                "fields": (
                    "images",
                )
            },
        ),
        (
            "Details",
            {
                "fields": (
                    "custom_fields",
                )
            },
        ),
        (
            "Visibility",
            {
                "fields": (
                    "is_active",
                    "is_available",
                )
            },
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

    actions = (
        "mark_as_active",
        "mark_as_inactive",
        "mark_as_available",
        "mark_as_unavailable",
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        return (
            queryset
            .select_related("business")
            .annotate(_image_count=Count("images"))
        )

    @admin.display(description="Images", ordering="_image_count")
    def image_count(self, obj):
        return obj._image_count

    @admin.action(description="Mark selected catalogs as active")
    def mark_as_active(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Mark selected catalogs as inactive")
    def mark_as_inactive(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description="Mark selected catalogs as available")
    def mark_as_available(self, request, queryset):
        queryset.update(is_available=True)

    @admin.action(description="Mark selected catalogs as unavailable")
    def mark_as_unavailable(self, request, queryset):
        queryset.update(is_available=False)
