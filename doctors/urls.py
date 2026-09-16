from django.urls import path

from doctors import views


app_name = "doctors"

urlpatterns = [
    path(
        "businesses/my/<uuid:business_id>/doctors/",
        views.my_business_doctor_list,
        name="my-business-doctor-list",
    ),
    path(
        "businesses/my/<uuid:business_id>/doctors/<uuid:doctor_id>/",
        views.my_business_doctor_detail,
        name="my-business-doctor-detail",
    ),
    path(
        "businesses/<slug:business_slug>/doctors/",
        views.business_doctor_list,
        name="business-doctor-list",
    ),
    path(
        "doctors/specialties/",
        views.doctor_specialty_list,
        name="doctor-specialty-list",
    ),
    path("doctors/", views.doctor_list, name="doctor-list"),
    path("doctors/<slug:slug>/", views.doctor_detail, name="doctor-detail"),
]
