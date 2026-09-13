from django import forms
from django.contrib import admin
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    Business,
    BusinessCategoryAssignment,
    BusinessProfile,
    BusinessHour
)


BUSINESS_SECTION_CHOICES = (
    ("product", "Product"),
    ("offer", "Offer"),
    ("property", "Property"),
    ("course", "Course"),
    ("doctor", "Doctor"),
    ("pricing", "Pricing"),
    ("menu", "Menu"),
    ("package", "Package"),
)


class BusinessAdminForm(forms.ModelForm):
    sections = forms.MultipleChoiceField(
        choices=BUSINESS_SECTION_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
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
        if self.instance and self.instance.sections:
            self.initial.setdefault("sections", self.instance.sections)
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
        cleaned_data["sections"] = list(cleaned_data.get("sections") or [])
        return cleaned_data

    def save(self, commit=True):
        business = super().save(commit=False)
        latitude = self.cleaned_data.get("latitude")
        longitude = self.cleaned_data.get("longitude")
        business.sections = list(self.cleaned_data.get("sections") or [])
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


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    form = BusinessAdminForm

    list_display = (
        "name",
        "locality",
        "city",
        "status",
        "is_active",
        "is_verified",
        "is_paid",
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
        "cover_image",
    )

    filter_horizontal = ("gallery",)

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
                    "established_year",
                    "offerings",
                    "sections",
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
                    "cover_image",
                    "gallery",
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
        BusinessHourInline
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
