from django.urls import path

from businesses import views

app_name = "businesses"

urlpatterns = [
    path("businesses/", views.business_list, name="business-list"),
    path("businesses/mine/", views.my_business_list, name="my-business-list"),
    path("businesses/mine/<slug:slug>/", views.owner_business_detail, name="owner-business-detail"),
    path("businesses/<slug:slug>/", views.business_detail, name="business-detail"),
    path("businesses/<slug:slug>/hours/", views.business_hours_update, name="business-hours-update"),
]
