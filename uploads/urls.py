from django.urls import path

from uploads import views


app_name = "uploads"

urlpatterns = [
    path("uploads/", views.upload_list_create, name="upload-list-create"),
    path("uploads/complete/", views.upload_complete, name="upload-complete"),
    path("uploads/delete/", views.upload_delete, name="upload-delete"),
]
