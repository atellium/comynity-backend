from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from categories.cache import CATEGORY_CACHE_TIMEOUT, category_cache_key
from categories.serializers import (
    BusinessCategoryListQuerySerializer,
    BusinessCategoryListSerializer,
    CategorySearchSerializer,
    ProductCategoryListQuerySerializer,
    ProductCategoryListSerializer,
)
from categories.services import list_business_categories, list_product_categories, list_visible_categories, paginate_categories


@api_view(["GET"])
@permission_classes([AllowAny])
def business_category_list(request):
    query = BusinessCategoryListQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    filters = query.validated_data
    cache_key = None
    if filters.get("is_featured") is True:
        cache_key = category_cache_key(
            "business-list:featured",
            request.query_params,
        )
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            return Response(cached_response)

    categories, pagination = paginate_categories(
        list_business_categories(filters), filters["page"], filters["page_size"]
    )
    response_data = {
        "pagination": pagination,
        "results": BusinessCategoryListSerializer(
            categories, many=True, context={"request": request}
        ).data,
    }
    if cache_key:
        cache.set(cache_key, response_data, timeout=CATEGORY_CACHE_TIMEOUT)
    return Response(response_data)


@api_view(["GET"])
@permission_classes([AllowAny])
def product_category_list(request):
    query = ProductCategoryListQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    filters = query.validated_data
    cache_key = None
    if filters.get("is_featured") is True:
        cache_key = category_cache_key(
            "product-list:featured",
            request.query_params,
        )
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            return Response(cached_response)

    categories, pagination = paginate_categories(
        list_product_categories(filters), filters["page"], filters["page_size"]
    )
    response_data = {
        "pagination": pagination,
        "results": ProductCategoryListSerializer(
            categories, many=True, context={"request": request}
        ).data,
    }
    if cache_key:
        cache.set(cache_key, response_data, timeout=CATEGORY_CACHE_TIMEOUT)
    return Response(response_data)


@api_view(["GET"])
@permission_classes([AllowAny])
def search_categories(request):
    cache_key = category_cache_key("search")
    cached_response = cache.get(cache_key)
    if cached_response is not None:
        return Response(cached_response)

    categories = list_visible_categories()
    response_data = CategorySearchSerializer(categories, many=True).data
    cache.set(cache_key, response_data, timeout=CATEGORY_CACHE_TIMEOUT)
    return Response(response_data)
