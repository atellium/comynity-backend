from django.urls import path

from businesses import views

app_name = "businesses"

urlpatterns = [
    path("businesses/", views.business_list, name="business-list"),
    path("businesses/mine/", views.my_business_list, name="my-business-list"),
    path("businesses/mine/<slug:slug>/", views.owner_business_detail, name="owner-business-detail"),
    path("businesses/<slug:slug>/", views.business_detail, name="business-detail"),
    path("businesses/mine/<slug:slug>/gallery/", views.business_gallery, name="business-gallery"),
    # # path("businesses/<slug:slug>/gallery/<uuid:image_id>/", views.business_gallery_image_detail, name="business-gallery-image-detail"),
    # # path("businesses/<slug:slug>/holidays/", views.business_holiday_create, name="business-holiday-create"),
    # # path("businesses/<slug:slug>/holidays/<uuid:holiday_id>/", views.business_holiday_detail, name="business-holiday-detail"),
    path("businesses/<slug:slug>/hours/", views.business_hours_update, name="business-hours-update"),
]
