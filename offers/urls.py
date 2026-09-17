from django.urls import path

from offers import views


app_name = "offers"

urlpatterns = [
    path(
        "businesses/<slug:business_slug>/offers/",
        views.public_business_offer_list,
        name="public-business-offer-list",
    ),
    path(
        "offers/nearby/",
        views.nearby_offer_list,
        name="nearby-offer-list",
    ),
    path(
        "businesses/mine/<slug:business_slug>/offers/",
        views.offer_create,
        name="offer-create",
    ),
    path(
        "businesses/mine/<slug:business_slug>/offers/<uuid:offer_id>/",
        views.offer_manage,
        name="offer-manage",
    ),
]
