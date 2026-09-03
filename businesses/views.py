from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from businesses.models import BusinessGalleryImage
from businesses.serializers import BusinessDetailSerializer, BusinessGalleryBulkUploadSerializer, BusinessGalleryImageSerializer, BusinessGalleryImageWriteSerializer, BusinessGallerySyncSerializer, BusinessHourSerializer, BusinessHoursUpdateSerializer, BusinessListQuerySerializer, BusinessListSerializer, BusinessUpdateSerializer, CategoryFilterSerializer, OwnerBusinessDetailSerializer
from businesses.services import get_business_by_slug, get_public_business_by_slug, get_business_category, get_business_for_update, list_businesses, paginate_businesses, replace_business_hours


@api_view(["GET"])
@permission_classes([AllowAny])
def business_list(request):
    query = BusinessListQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    filters = query.validated_data
    filters["publication_status"] = "published"
    filters["is_active"] = True
    now = timezone.now()
    businesses, pagination = paginate_businesses(list_businesses(filters, now=now), filters["page"], filters["page_size"])
    category = get_business_category(filters.get("category"))
    serializer_context = {"request": request, "now": now}
    return Response({"pagination": pagination, "category": CategoryFilterSerializer(category).data if category else None, "results": BusinessListSerializer(businesses, many=True, context=serializer_context).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_business_list(request):
    query = BusinessListQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    filters = query.validated_data
    filters["owner_id"] = request.user.pk
    now = timezone.now()
    businesses, pagination = paginate_businesses(
        list_businesses(filters, now=now), filters["page"], filters["page_size"]
    )
    category = get_business_category(filters.get("category"))
    serializer_context = {"request": request, "now": now}
    return Response(
        {
            "pagination": pagination,
            "category": CategoryFilterSerializer(category).data if category else None,
            "results": BusinessListSerializer(
                businesses, many=True, context=serializer_context
            ).data,
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def business_detail(request, slug):
    now = timezone.now()
    business = get_public_business_by_slug(slug, now=now)
    if business is None:
        raise NotFound("Business not found.")
    serializer_context = {"request": request, "now": now}
    return Response({"result": BusinessDetailSerializer(business, context=serializer_context).data})


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def owner_business_detail(request, slug):
    business = _owned_business(request, slug)

    if request.method == "PATCH":
        serializer = BusinessUpdateSerializer(business, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()

    now = timezone.now()
    business = get_business_by_slug(business.slug, now=now)
    serializer_context = {"request": request, "now": now}
    return Response(
        {
            "result": OwnerBusinessDetailSerializer(
                business, context=serializer_context
            ).data
        }
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def business_hours_update(request, slug):
    business = get_business_for_update(slug)
    if business is None:
        raise NotFound("Business not found.")
    if business.owner_id != request.user.pk:
        raise PermissionDenied("You can only update hours for your own business.")

    serializer = BusinessHoursUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        hours = replace_business_hours(
            business, serializer.validated_data["business_hours"]
        )
        response_data = BusinessHourSerializer(hours, many=True).data
    return Response({"result": {"business_hours": response_data}})


def _owned_business(request, slug):
    business = get_business_for_update(slug)
    if business is None:
        raise NotFound("Business not found.")
    if business.owner_id != request.user.pk:
        raise PermissionDenied("You can only manage your own business.")
    return business


@api_view(["GET", "POST", "PATCH"])
@permission_classes([IsAuthenticated])
def business_gallery(request, slug):
    business = _owned_business(request, slug)

    if request.method == "GET":
        return Response(
            {
                "results": BusinessGalleryImageSerializer(
                    business.gallery_images.all(),
                    many=True,
                    context={"request": request},
                ).data
            }
        )

    images = request.FILES.getlist("images")
    if not images:
        images = request.FILES.getlist("image")

    if request.method == "POST":
        serializer = BusinessGalleryBulkUploadSerializer(
            data={"images": images}, context={"business": business}
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            created_images = [
                BusinessGalleryImage.objects.create(business=business, image=image)
                for image in serializer.validated_data["images"]
            ]
        return Response(
            {
                "results": BusinessGalleryImageSerializer(
                    created_images, many=True, context={"request": request}
                ).data
            },
            status=status.HTTP_201_CREATED,
        )

    if hasattr(request.data, "getlist"):
        existing_ids = request.data.getlist("existing_ids")
        if not existing_ids:
            existing_ids = request.data.getlist("existing_ids[]")
    else:
        existing_ids = request.data.get("existing_ids", [])

    serializer = BusinessGallerySyncSerializer(
        data={"existing_ids": existing_ids, "images": images},
        context={"business": business},
    )
    serializer.is_valid(raise_exception=True)
    retained_ids = set(serializer.validated_data["existing_ids"])
    existing_images = {image.pk: image for image in business.gallery_images.all()}
    missing_ids = retained_ids - existing_images.keys()
    if missing_ids:
        raise NotFound(
            f"Business gallery images not found: {', '.join(map(str, sorted(missing_ids, key=str)))}."
        )

    images_to_delete = [
        image for image_id, image in existing_images.items() if image_id not in retained_ids
    ]
    with transaction.atomic():
        for image in images_to_delete:
            stored_image = image.image
            image.delete()
            transaction.on_commit(
                lambda stored_image=stored_image: stored_image.delete(save=False)
            )
        for image in serializer.validated_data["images"]:
            BusinessGalleryImage.objects.create(business=business, image=image)

    return Response(
        {
            "results": BusinessGalleryImageSerializer(
                business.gallery_images.all(), many=True, context={"request": request}
            ).data
        }
    )


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def business_gallery_image_detail(request, slug, image_id):
    business = _owned_business(request, slug)
    gallery_image = BusinessGalleryImage.objects.filter(
        pk=image_id, business=business
    ).first()
    if gallery_image is None:
        raise NotFound("Gallery image not found.")

    if request.method == "DELETE":
        stored_image = gallery_image.image
        gallery_image.delete()
        stored_image.delete(save=False)
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = BusinessGalleryImageWriteSerializer(
        gallery_image,
        data=request.data,
        partial=True,
        context={"business": business},
    )
    serializer.is_valid(raise_exception=True)
    gallery_image = serializer.save()
    return Response(
        {
            "result": BusinessGalleryImageSerializer(
                gallery_image, context={"request": request}
            ).data
        }
    )
