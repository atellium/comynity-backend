from django.contrib import admin

from locations.forms import LocalityAdminForm
from locations.models import City, Locality, State


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "slug")
    search_fields = ("name", "code", "slug")
    ordering = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    list_per_page = 50


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "tier", "slug")
    list_display_links = ("name",)
    list_editable = ("tier",)
    list_filter = ("tier", "state")
    search_fields = ("name", "slug", "state__name", "state__code")
    ordering = ("state__name", "name")
    autocomplete_fields = ("state",)
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ("state",)
    list_per_page = 50


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    form = LocalityAdminForm
    fields = ("name", "slug", "city", "aliases", "latitude", "longitude")
    list_display = ("name", "city", "state", "slug", "latitude", "longitude")
    list_filter = ("city__state", "city")
    search_fields = (
        "name",
        "slug",
        "aliases",
        "city__name",
        "city__state__name",
        "city__state__code",
    )
    ordering = ("city__state__name", "city__name", "name")
    autocomplete_fields = ("city",)
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ("city", "city__state")
    list_per_page = 50

    @admin.display(ordering="city__state__name", description="State")
    def state(self, obj):
        return obj.city.state
