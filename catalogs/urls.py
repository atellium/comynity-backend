from django.urls import path

from catalogs import views


app_name = "catalogs"

urlpatterns = [
    path(
        "catalogs/categories/",
        views.catalog_category_list,
        name="catalog-category-list",
    ),
    path(
        "businesses/mine/<slug:business_slug>/catalogs/",
        views.catalog_create,
        name="catalog-create",
    ),
    path(
        "businesses/mine/<slug:business_slug>/catalogs/<slug:catalog_slug>/",
        views.catalog_manage,
        name="catalog-manage",
    ),
    path(
        "businesses/mine/<slug:business_slug>/catalogs/<slug:catalog_slug>/edit/",
        views.catalog_edit,
        name="catalog-edit",
    ),
    path(
        "businesses/mine/<slug:business_slug>/catalogs/<slug:catalog_slug>/images/",
        views.catalog_image_create,
        name="catalog-image-create",
    ),
    path("businesses/mine/<slug:business_slug>/catalogs/<slug:catalog_slug>/images/uploads/", views.catalog_image_upload_create, name="catalog-image-upload-create"),
    path("businesses/mine/<slug:business_slug>/catalogs/<slug:catalog_slug>/images/uploads/<uuid:upload_id>/", views.catalog_image_upload_detail, name="catalog-image-upload-detail"),
    path("businesses/mine/<slug:business_slug>/catalogs/<slug:catalog_slug>/images/uploads/<uuid:upload_id>/complete/", views.catalog_image_upload_complete, name="catalog-image-upload-complete"),
    path(
        "businesses/mine/<slug:business_slug>/catalogs/<slug:catalog_slug>/images/<int:image_id>/",
        views.catalog_image_manage,
        name="catalog-image-manage",
    ),
    path(
        "catalogs/products/<slug:slug>/",
        views.product_detail,
        name="product-detail",
    ),
    path(
        "businesses/<slug:slug>/catalogs/products/",
        views.business_product_list,
        name="business-product-list",
    ),
    path(
        "businesses/<slug:slug>/catalogs/",
        views.business_catalog_list,
        name="business-catalog-list",
    ),
]
