from django.urls import path

from bookmarks import views


app_name = "bookmarks"

urlpatterns = [
    path("saved-items/", views.saved_item_create, name="saved-item-create"),
    path(
        "saved-items/<uuid:object_id>/",
        views.saved_item_detail,
        name="saved-item-detail",
    ),
]
