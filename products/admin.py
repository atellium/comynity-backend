from django.contrib import admin
from django.db.models import Count

from .models import ProductCategory, Product, ProductImage


class RootProductCategoryParentFilter(admin.SimpleListFilter):
    title = "parent"
    parameter_name = "parent__id__exact"

    def lookups(self, request, model_admin):
        return (
            (category.pk, str(category))
            for category in ProductCategory.objects.filter(parent__isnull=True).order_by(
                "sort_order",
                "name",
            )
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(parent_id=self.value())
        return queryset


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    search_fields = (
        "name",
        "label",
        "display_name",
        "aliases",
        "slug",
        "parent__name",
    )

    prepopulated_fields = {
        "slug": ("label",),
    }

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    list_display = (
        "name",
        "label",
        "display_name",
        "parent",
        "is_active",
        "is_featured",
        "is_search",
        "sort_order",
    )

    list_editable = (
        "is_active",
        "is_featured",
        "is_search",
        "sort_order",
    )

    list_filter = (
        "is_active",
        "is_featured",
        "is_search",
        RootProductCategoryParentFilter,
    )

    list_select_related = (
        "parent",
    )

    ordering = (
        "sort_order",
        "name",
    )

    autocomplete_fields = (
        "parent",
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
                    "display_name",
                    "aliases",
                    "parent",
                    "image",
                )
            },
        ),
        (
            "URL",
            {
                "fields": (
                    "slug",
                )
            },
        ),
        (
            "Ordering",
            {
                "fields": (
                    "sort_order",
                )
            },
        ),
        (
            "Visibility",
            {
                "fields": (
                    "is_active",
                    "is_featured",
                    "is_search",
                )
            },
        ),
        (
            "System",
            {
                "classes": ("collapse",),
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent":
            kwargs["queryset"] = ProductCategory.objects.filter(parent__isnull=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(
            request,
            queryset,
            search_term,
        )
        if request.GET.get("field_name") == "parent":
            queryset = queryset.filter(parent__isnull=True)
        return queryset, may_have_duplicates


class ProductImageInline(admin.TabularInline):
    model = ProductImage

    extra = 0

    fields = (
        "upload",
        "sort_order",
    )

    ordering = (
        "sort_order",
        "created_at",
    )

    autocomplete_fields = (
        "upload",
    )

    show_change_link = True

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "business",
        "price_type",
        "price",
        "status",
        "is_available",
        "is_featured",
        "image_count",
        "sort_order",
        "created_at",
    )

    list_filter = (
        "status",
        "price_type",
        "is_available",
        "is_featured",
        "categories",
        "created_at",
    )

    search_fields = (
        "name",
        "public_id",
        "business__name",
        "slug",
        "description",
    )

    autocomplete_fields = (
        "business",
        "categories",
    )

    readonly_fields = (
        "id",
        "public_id",
        "slug",
        "created_at",
        "updated_at",
        "discount_display",
    )

    list_editable = (
        "status",
        "is_available",
        "is_featured",
        "sort_order",
    )

    ordering = (
        "sort_order",
        "-created_at",
    )

    list_per_page = 50

    save_on_top = True

    inlines = (
        ProductImageInline,
    )

    fieldsets = (
        (
            "Product",
            {
                "fields": (
                    "business",
                    "name",
                    "description",
                )
            },
        ),

        (
            "Classification",
            {
                "fields": (
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
                    "mrp_price",
                    "max_price",
                    "discount_display",
                )
            },
        ),

        (
            "Product Information",
            {
                "fields": (
                    "variants",
                    "specifications",
                )
            },
        ),

        (
            "Visibility",
            {
                "fields": (
                    "status",
                    "is_available",
                    "is_featured",
                    "sort_order",
                )
            },
        ),

        (
            "System Information",
            {
                "classes": (
                    "collapse",
                ),
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

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        return (
            queryset
            .select_related("business")
            .prefetch_related("categories")
            .annotate(_image_count=Count("product_images"))
        )

    @admin.display(
        description="Images",
        ordering="_image_count",
    )
    def image_count(self, obj):
        return obj._image_count

    @admin.display(
        description="Discount",
    )
    def discount_display(self, obj):
        percentage = obj.discount_percentage

        if percentage is None:
            return "—"

        return f"{percentage}%"
