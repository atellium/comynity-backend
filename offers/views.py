from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from businesses.services import get_business_for_update
from offers.models import Offer
from offers.serializers import NearbyOfferListQuerySerializer, NearbyOfferSerializer, OfferSerializer, OfferWriteSerializer
from offers.services import list_nearby_offers, paginate_offers
from django.utils import timezone
from django.conf import settings

from businesses.direct_uploads import new_upload_key, presign_upload
from businesses.models import BusinessGalleryUpload
from businesses.serializers import BusinessGalleryUploadCreateSerializer


def _owned_business(request, business_slug):
    business = get_business_for_update(business_slug)
    if business is None:
        raise NotFound("Business not found.")
    if business.owner_id != request.user.pk:
        raise PermissionDenied("You can only manage offers for your own business.")
    return business


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
        return Response(
            {
                "results": OfferSerializer(
                    business.offers.all(),
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
    return Response(
        {
            "result": OfferSerializer(
                offer, context={"request": request}
            ).data
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def offer_manage(request, business_slug, offer_id):
    business = _owned_business(request, business_slug)
    offer = Offer.objects.filter(pk=offer_id, business=business).first()
    if offer is None:
        raise NotFound("Offer not found.")

    if request.method == "DELETE":
        image_name = offer.image.name if offer.image else None
        image_storage = offer.image.storage if image_name else None
        with transaction.atomic():
            offer.delete()
            if image_name:
                transaction.on_commit(
                    lambda: image_storage.delete(image_name)
                )
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = OfferWriteSerializer(
        offer,
        data=request.data,
        partial=True,
        context={"request": request, "business": business},
    )
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        offer = serializer.save()
    return Response(
        {
            "result": OfferSerializer(
                offer, context={"request": request}
            ).data
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def offer_image_upload_create(request, business_slug, offer_id):
    business = _owned_business(request, business_slug)
    offer = Offer.objects.filter(pk=offer_id, business=business).first()
    if offer is None:
        raise NotFound("Offer not found.")
    if not settings.R2_ENABLED:
        return Response({"detail": "Direct uploads require R2_ENABLED."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    serializer = BusinessGalleryUploadCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    content_type = serializer.validated_data["content_type"]
    object_key = new_upload_key(f"offer-{offer.pk}", content_type)
    upload = BusinessGalleryUpload.objects.create(
        business=business, target_id=offer.pk, object_key=object_key,
        content_type=content_type, kind=BusinessGalleryUpload.Kind.OFFER,
    )
    return Response({"id": upload.pk, "upload_url": presign_upload(object_key, content_type), "content_type": content_type, "expires_in": 300}, status=status.HTTP_201_CREATED)
