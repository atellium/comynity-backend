from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from businesses.services import get_business_for_update, get_public_business_by_slug
from offers.models import Offer
from offers.serializers import (
    NearbyOfferListQuerySerializer,
    NearbyOfferSerializer,
    OfferSerializer,
    OfferWriteSerializer,
)
from offers.services import list_nearby_offers, paginate_offers


def _owned_business(request, business_slug):
    business = get_business_for_update(business_slug)
    if business is None:
        raise NotFound("Business not found.")
    if business.owner_id != request.user.pk:
        raise PermissionDenied("You can only manage offers for your own business.")
    return business


def _owned_offer(request, business_slug, offer_id):
    business = _owned_business(request, business_slug)
    offer = (
        Offer.objects
        .filter(pk=offer_id, business=business)
        .select_related("business", "image")
        .first()
    )
    if offer is None:
        raise NotFound("Offer not found.")
    return offer


@api_view(["GET"])
@permission_classes([AllowAny])
def public_business_offer_list(request, business_slug):
    business = get_public_business_by_slug(business_slug)
    if business is None:
        raise NotFound("Business not found.")

    offers = (
        Offer.objects
        .active()
        .filter(business=business)
        .select_related("business", "image")
    )

    return Response(
        {
            "business": {
                "id": business.pk,
                "name": business.name,
                "slug": business.slug,
            },
            "results": OfferSerializer(
                offers,
                many=True,
                context={"request": request},
            ).data,
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def nearby_offer_list(request):
    query = NearbyOfferListQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    filters = query.validated_data
    now = timezone.now()
    offers, pagination = paginate_offers(
        list_nearby_offers(filters, now=now),
        filters["page"],
        filters["page_size"],
    )
    return Response(
        {
            "pagination": pagination,
            "results": NearbyOfferSerializer(
                offers,
                many=True,
                context={"request": request},
            ).data,
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def offer_create(request, business_slug):
    business = _owned_business(request, business_slug)

    if request.method == "GET":
        offers = (
            Offer.objects
            .filter(business=business)
            .select_related("business", "image")
        )
        return Response(
            {
                "results": OfferSerializer(
                    offers,
                    many=True,
                    context={"request": request},
                ).data
            }
        )

    serializer = OfferWriteSerializer(
        data=request.data,
        context={"request": request, "business": business},
    )
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        offer = serializer.save()
    offer = (
        Offer.objects
        .select_related("business", "image")
        .get(pk=offer.pk)
    )
    return Response(
        {
            "result": OfferSerializer(
                offer, context={"request": request}
            ).data
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def offer_manage(request, business_slug, offer_id):
    offer = _owned_offer(request, business_slug, offer_id)

    if request.method == "GET":
        return Response(
            {
                "result": OfferSerializer(
                    offer,
                    context={"request": request},
                ).data
            }
        )

    if request.method == "DELETE":
        offer.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = OfferWriteSerializer(
        offer,
        data=request.data,
        partial=request.method == "PATCH",
        context={"request": request, "business": offer.business},
    )
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        offer = serializer.save()
    offer = (
        Offer.objects
        .select_related("business", "image")
        .get(pk=offer.pk)
    )
    return Response(
        {
            "result": OfferSerializer(
                offer, context={"request": request}
            ).data
        }
    )
