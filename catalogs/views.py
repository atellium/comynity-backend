from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from businesses.services import get_business_for_update, get_public_business_by_slug
from catalogs.models import Catalog
from catalogs.serializers import (
    CatalogListQuerySerializer,
    CatalogSerializer,
    CatalogWriteSerializer,
)


def _owned_business(request, business_slug):
    business = get_business_for_update(business_slug)
    if business is None:
        raise NotFound("Business not found.")
    if business.owner_id != request.user.pk:
        raise PermissionDenied("You can only manage catalogs for your own business.")
    return business


def _owned_catalog(request, business_slug, catalog_slug):
    business = _owned_business(request, business_slug)
    catalog = (
        Catalog.objects
        .filter(business=business, slug=catalog_slug)
        .select_related("business")
        .prefetch_related("images")
        .first()
    )
    if catalog is None:
        raise NotFound("Catalog not found.")
    return catalog


@api_view(["GET"])
@permission_classes([AllowAny])
def public_business_catalog_list(request, business_slug):
    business = get_public_business_by_slug(business_slug)
    if business is None:
        raise NotFound("Business not found.")

    catalogs = (
        Catalog.objects
        .filter(
            business=business,
            is_active=True,
            is_available=True,
        )
        .select_related("business")
        .prefetch_related("images")
    )

    grouped_catalogs = {
        catalog_type: []
        for catalog_type, _label in Catalog.CatalogType.choices
    }

    serialized_catalogs = CatalogSerializer(
        catalogs,
        many=True,
        context={"request": request},
    ).data

    for catalog in serialized_catalogs:
        grouped_catalogs[catalog["type"]].append(catalog)

    return Response(
        {
            "business": {
                "id": business.pk,
                "name": business.name,
                "slug": business.slug,
            },
            "results": grouped_catalogs,
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def catalog_list_create(request, business_slug):
    business = _owned_business(request, business_slug)

    if request.method == "GET":
        query = CatalogListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        catalogs = (
            Catalog.objects
            .filter(business=business)
            .select_related("business")
            .prefetch_related("images")
        )

        catalog_type = query.validated_data.get("type")
        if catalog_type:
            catalogs = catalogs.filter(type=catalog_type)

        return Response(
            {
                "business": {
                    "id": business.pk,
                    "name": business.name,
                    "slug": business.slug,
                },
                "results": CatalogSerializer(
                    catalogs,
                    many=True,
                    context={"request": request},
                ).data,
            }
        )

    serializer = CatalogWriteSerializer(
        data=request.data,
        context={
            "request": request,
            "business": business,
        },
    )
    serializer.is_valid(raise_exception=True)

    with transaction.atomic():
        catalog = serializer.save()

    catalog = (
        Catalog.objects
        .filter(pk=catalog.pk)
        .select_related("business")
        .prefetch_related("images")
        .get()
    )
    return Response(
        {
            "result": CatalogSerializer(
                catalog,
                context={"request": request},
            ).data
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def catalog_detail(request, business_slug, catalog_slug):
    catalog = _owned_catalog(request, business_slug, catalog_slug)

    if request.method == "GET":
        return Response(
            {
                "result": CatalogSerializer(
                    catalog,
                    context={"request": request},
                ).data
            }
        )

    if request.method == "DELETE":
        catalog.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = CatalogWriteSerializer(
        catalog,
        data=request.data,
        partial=request.method == "PATCH",
        context={
            "request": request,
            "business": catalog.business,
        },
    )
    serializer.is_valid(raise_exception=True)

    with transaction.atomic():
        catalog = serializer.save()

    catalog = (
        Catalog.objects
        .filter(pk=catalog.pk)
        .select_related("business")
        .prefetch_related("images")
        .get()
    )
    return Response(
        {
            "result": CatalogSerializer(
                catalog,
                context={"request": request},
            ).data
        }
    )
