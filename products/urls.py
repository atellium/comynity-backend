from django.urls import path

from products import views


app_name = "products"

urlpatterns = [
    path(
        "products/categories/",
        views.product_category_list,
        name="product-category-list",
    ),
    path(
        "products/categories/import/",
        views.product_category_bulk_import,
        name="product-category-bulk-import",
    ),
    path(
        "businesses/<slug:business_slug>/products/",
        views.business_product_list,
        name="business-product-list",
    ),
    path(
        "products/<slug:product_slug>/",
        views.public_product_detail,
        name="public-product-detail",
    ),
    path(
        "businesses/mine/<slug:business_slug>/products/",
        views.product_list_create,
        name="product-list-create",
    ),
    path(
        "businesses/mine/<slug:business_slug>/products/<slug:product_slug>/",
        views.product_detail,
        name="product-detail",
    ),
]
