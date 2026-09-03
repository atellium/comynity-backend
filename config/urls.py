from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Comynity Administration"
admin.site.site_title = "Comynity Admin"
admin.site.index_title = "Dashboard"

urlpatterns = [
    path("api/", include("core.urls")),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("locations.urls")),
    path("api/", include("categories.urls")),
    path("api/", include("businesses.urls")),
    path("api/", include("catalogs.urls")),
    path("api/", include("bookmarks.urls")),
    path("api/", include("offers.urls")),
    path("admin/", admin.site.urls),
]
