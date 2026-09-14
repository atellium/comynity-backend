from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from businesses.services import get_business_for_update, get_public_business_by_slug
from products.models import Product
from products.serializers import (
    ProductCategoryListQuerySerializer,
    ProductCategoryBulkImportSerializer,
    ProductCategorySerializer,
    ProductSerializer,
    ProductWriteSerializer,
    PublicProductListSerializer,
    PublicProductListQuerySerializer,
)
from products.services import (
    list_featured_product_categories,
    list_product_categories,
    list_public_products,
    order_products,
    paginate_product_categories,
    paginate_products,
)


def _owned_business(request, business_slug):
    business = get_business_for_update(business_slug)
    if business is None:
        raise NotFound("Business not found.")
    if business.owner_id != request.user.pk:
        raise PermissionDenied("You can only manage products for your own business.")
    return business


def _owned_product(request, business_slug, product_slug):
    business = _owned_business(request, business_slug)
    product = (
        Product.objects.filter(business=business, slug=product_slug)
        .select_related(
            "business",
            "business__city",
            "business__city__state",
            "business__cover_image",
        )
        .prefetch_related("categories", "product_images__upload")
        .first()
    )
    if product is None:
        raise NotFound("Product not found.")
    return product


@api_view(["GET"])
@permission_classes([AllowAny])
def product_category_list(request):
    query = ProductCategoryListQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    filters = query.validated_data
    categories, pagination = paginate_product_categories(
        list_product_categories(filters),
        filters["page"],
        filters["page_size"],
    )
    return Response(
        {
            "pagination": pagination,
            "results": ProductCategorySerializer(
                categories,
                many=True,
                context={"request": request},
            ).data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAdminUser])
@parser_classes([MultiPartParser, FormParser])
def product_category_bulk_import(request):
    serializer = ProductCategoryBulkImportSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    result = serializer.save()
    return Response(
        {
            "created": result["created"],
            "updated": result["updated"],
            "total": result["total"],
            "results": ProductCategorySerializer(
                result["categories"],
                many=True,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def business_product_list(request, business_slug):
    business = get_public_business_by_slug(business_slug)
    if business is None:
        raise NotFound("Business not found.")

    query = PublicProductListQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    filters = query.validated_data
    products, pagination = paginate_products(
        list_public_products(business, filters),
        filters["page"],
        filters["page_size"],
    )
    return Response(
        {
            "business": {
                "id": business.pk,
                "name": business.name,
                "slug": business.slug,
            },
            "categories": ProductCategorySerializer(
                list_featured_product_categories(business),
                many=True,
                context={"request": request},
            ).data,
            "pagination": pagination,
            "results": PublicProductListSerializer(
                products,
                many=True,
                context={"request": request},
            ).data,
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def public_product_detail(request, product_slug):
    product = (
        Product.objects.filter(
            slug=product_slug,
            status=Product.Status.ACTIVE,
        )
        .select_related(
            "business",
            "business__city",
            "business__city__state",
            "business__cover_image",
        )
        .prefetch_related("categories", "product_images__upload")
        .first()
    )
    if product is None:
        raise NotFound("Product not found.")

    return Response(
        {
            "result": ProductSerializer(
                product,
                context={"request": request},
            ).data
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def product_list_create(request, business_slug):
    business = _owned_business(request, business_slug)

    if request.method == "GET":
        products = (
            Product.objects.filter(business=business)
            .prefetch_related("categories", "product_images__upload")
        )
        products = order_products(products)
        return Response(
            {
                "business": {
                    "id": business.pk,
                    "name": business.name,
                    "slug": business.slug,
                },
                "results": ProductSerializer(
                    products,
                    many=True,
                    context={"request": request},
                ).data
            }
        )

    serializer = ProductWriteSerializer(
        data=request.data,
        context={"request": request, "business": business},
    )
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        product = serializer.save()
    product = (
        Product.objects.filter(pk=product.pk)
        .prefetch_related("categories", "product_images__upload")
        .get()
    )
    return Response(
        {
            "result": ProductSerializer(
                product,
                context={"request": request},
            ).data
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def product_detail(request, business_slug, product_slug):
    product = _owned_product(request, business_slug, product_slug)

    if request.method == "GET":
        return Response(
            {
                "result": ProductSerializer(
                    product,
                    context={"request": request},
                ).data
            }
        )

    if request.method == "DELETE":
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = ProductWriteSerializer(
        product,
        data=request.data,
        partial=request.method == "PATCH",
        context={"request": request, "business": product.business},
    )
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        product = serializer.save()
    product = (
        Product.objects.filter(pk=product.pk)
        .prefetch_related("categories", "product_images__upload")
        .get()
    )
    return Response(
        {
            "result": ProductSerializer(
                product,
                context={"request": request},
            ).data
        }
    )
