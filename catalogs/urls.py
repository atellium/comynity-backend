from django.urls import path

from catalogs import views


app_name = "catalogs"

urlpatterns = [
    path(
        "businesses/<slug:business_slug>/catalogs/",
        views.public_business_catalog_list,
        name="public-business-catalog-list",
    ),
    path(
        "businesses/mine/<slug:business_slug>/catalogs/",
        views.catalog_list_create,
        name="catalog-list-create",
    ),
    path(
        "businesses/mine/<slug:business_slug>/catalogs/<slug:catalog_slug>/",
        views.catalog_detail,
        name="catalog-detail",
    ),
]
