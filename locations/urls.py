from django.urls import path

from locations import views


app_name = "locations"

urlpatterns = [
    path("locations/cities/", views.city_list, name="city-list"),
    path("locations/nearest/", views.nearest_locality, name="nearest-locality"),
    path("locations/search/", views.search_localities, name="search-localities"),
]
