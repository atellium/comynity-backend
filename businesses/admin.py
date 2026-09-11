from django import forms
from django.contrib import admin
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    Business,
    BusinessCategoryAssignment,
    BusinessProfile,
    BusinessHour,
    BusinessHoliday,
    BusinessGalleryImage,
)


class BusinessAdminForm(forms.ModelForm):
    latitude = forms.DecimalField(
        required=False,
        min_value=-90,
        max_value=90,
    )
    longitude = forms.DecimalField(
        required=False,
        min_value=-180,
        max_value=180,
    )

    class Meta:
        model = Business
        exclude = ("location",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.location:
            self.initial.setdefault("latitude", self.instance.location.y)
            self.initial.setdefault("longitude", self.instance.location.x)

    def clean(self):
        cleaned_data = super().clean()
        latitude = cleaned_data.get("latitude")
        longitude = cleaned_data.get("longitude")
        if (latitude is None) != (longitude is None):
            raise forms.ValidationError(
                "Latitude and longitude must both be provided or both be empty."
            )
        return cleaned_data

    def save(self, commit=True):
        business = super().save(commit=False)
        latitude = self.cleaned_data.get("latitude")
        longitude = self.cleaned_data.get("longitude")
        business.location = (
            Point(float(longitude), float(latitude), srid=4326)
            if latitude is not None and longitude is not None
            else None
        )
        if commit:
            business.save()
            self.save_m2m()
        return business


class BusinessProfileInline(admin.StackedInline):
    model = BusinessProfile
    extra = 0
    max_num = 1
    can_delete = False

    fieldsets = (
        (
            "Profile",
            {
                "fields": (
                    "description",
                    "social_urls",
                    "alternate_numbers",
                    "services",
                )
            },
        ),
        (
            "SEO",
            {
                "classes": ("collapse",),
                "fields": (
                    "seo_title",
                    "seo_description",
                    "seo_keywords",
                ),
            },
        ),
    )


class BusinessCategoryAssignmentInline(admin.TabularInline):
    model = BusinessCategoryAssignment
    extra = 1
    autocomplete_fields = ("category",)

    fields = (
        "category",
        "sort_order",
    )

    ordering = ("sort_order",)


class BusinessHourInline(admin.TabularInline):
    model = BusinessHour
    extra = 0

    fields = (
        "days",
        "opens_at",
        "closes_at",
    )

    ordering = ("opens_at",)


class BusinessHolidayInline(admin.TabularInline):
    model = BusinessHoliday
    extra = 0

    fields = (
        "start_date",
        "end_date",
        "reason",
    )

    ordering = ("start_date",)


class BusinessGalleryImageInline(admin.TabularInline):
    model = BusinessGalleryImage
    extra = 0

    fields = (
        "image",
        "image_preview",
        "sort_order",
    )

    readonly_fields = ("image_preview",)

    ordering = (
        "sort_order",
        "created_at",
    )

    @admin.display(description="Preview")
    def image_preview(self, obj):
        if obj.pk and obj.image:
            return format_html(
                '<img src="{}" '
                'style="width:80px;height:80px;'
                'object-fit:cover;border-radius:8px;" />',
                obj.image.url,
            )

        return "—"


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    form = BusinessAdminForm

    list_display = (
        "name",
        "handle_display",
        "locality",
        "city",
        "status",
        "is_active",
        "is_verified",
        "is_paid",
        "paid_until",
        "owner",
        "published_at",
    )

    list_filter = (
        "status",
        "is_active",
        "is_verified",
        "is_paid",
        "city__state",
        "city",
        "created_at",
    )

    search_fields = (
        "name",
        "handle",
        "slug",
        "phone",
        "whatsapp",
        "email",
        "address",
        "landmark",
        "locality",
        "postal_code",
        "city__name",
        "city__state__name",
    )

    autocomplete_fields = (
        "owner",
        "city",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "published_at",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }

    list_select_related = (
        "owner",
        "city",
        "city__state",
    )

    list_per_page = 50
    save_on_top = True

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "owner",
                    "name",
                    "slug",
                    "handle",
                    "established_year",
                    "offerings",
                )
            },
        ),
        (
            "Location",
            {
                "fields": (
                    "address",
                    "landmark",
                    "locality",
                    "city",
                    "postal_code",
                    "latitude",
                    "longitude",
                )
            },
        ),
        (
            "Contact",
            {
                "fields": (
                    "phone",
                    "whatsapp",
                    "email",
                    "website",
                )
            },
        ),
        (
            "Media",
            {
                "fields": (
                    "thumbnail",
                )
            },
        ),
        (
            "Publishing",
            {
                "fields": (
                    "status",
                    "is_active",
                    "is_verified",
                    "published_at",
                )
            },
        ),
        (
            "Payment",
            {
                "fields": (
                    "is_paid",
                    "payment_date",
                    "paid_until",
                )
            },
        ),
        (
            "Display Settings",
            {
                "classes": ("collapse",),
                "fields": (
                    "display_full_address",
                    "display_business_hours",
                ),
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

    inlines = (
        BusinessProfileInline,
        BusinessCategoryAssignmentInline,
        BusinessHourInline,
        BusinessHolidayInline,
        BusinessGalleryImageInline,
    )

    actions = (
        "mark_as_active",
        "mark_as_inactive",
        "mark_as_verified",
        "mark_as_unverified",
        "mark_as_paid",
        "mark_as_unpaid",
        "publish_businesses",
    )

    @admin.display(
        description="Handle",
        ordering="handle",
    )
    def handle_display(self, obj):
        return f"@{obj.handle}"

    @admin.display(description="Latitude")
    def latitude_display(self, obj):
        if not obj.location:
            return "—"

        return round(obj.location.y, 7)

    @admin.display(description="Longitude")
    def longitude_display(self, obj):
        if not obj.location:
            return "—"

        return round(obj.location.x, 7)

    @admin.action(description="Mark selected businesses as active")
    def mark_as_active(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Mark selected businesses as inactive")
    def mark_as_inactive(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description="Mark selected businesses as verified")
    def mark_as_verified(self, request, queryset):
        queryset.update(is_verified=True)

    @admin.action(description="Remove verification")
    def mark_as_unverified(self, request, queryset):
        queryset.update(is_verified=False)

    @admin.action(description="Mark selected businesses as paid")
    def mark_as_paid(self, request, queryset):
        queryset.update(is_paid=True, payment_date=timezone.now())

    @admin.action(description="Mark selected businesses as unpaid")
    def mark_as_unpaid(self, request, queryset):
        queryset.update(is_paid=False, paid_until=None)

    @admin.action(description="Publish selected businesses")
    def publish_businesses(self, request, queryset):
        queryset.update(
            status=Business.Status.PUBLISHED,
            is_active=True,
        )
