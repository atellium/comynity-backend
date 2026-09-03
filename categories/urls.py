from django.urls import path

from categories import views


app_name = "categories"

urlpatterns = [
    path("categories/business/", views.business_category_list, name="business-category-list"),
    path("categories/product/", views.product_category_list, name="product-category-list"),
    path("categories/search/", views.search_categories, name="search-categories"),
]
