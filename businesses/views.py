from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from businesses.serializers import BusinessDetailSerializer, BusinessHourSerializer, BusinessHoursUpdateSerializer, BusinessListQuerySerializer, BusinessListSerializer, BusinessUpdateSerializer, CategoryFilterSerializer, OwnerBusinessDetailSerializer
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
        serializer = BusinessUpdateSerializer(
            business,
            data=request.data,
            partial=True,
            context={"request": request},
        )
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
