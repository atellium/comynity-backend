from django.core.cache import cache
from django.db import connection
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from categories.models import BusinessCategory
from doctors.models import DoctorSpecialty
from products.models import ProductCategory


SEARCH_TYPE_BUSINESS = "business"
SEARCH_TYPE_DOCTOR = "doctor"
SEARCH_TYPE_PRODUCT = "product"
SEARCH_TYPES = (SEARCH_TYPE_BUSINESS, SEARCH_TYPE_DOCTOR, SEARCH_TYPE_PRODUCT)


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def health(request):
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def readiness(request):
    checks = {"database": False, "cache": False}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks["database"] = cursor.fetchone() == (1,)
    except Exception:
        pass
    try:
        cache_key = "health:readiness"
        cache.set(cache_key, "ok", timeout=10)
        checks["cache"] = cache.get(cache_key) == "ok"
    except Exception:
        pass
    ready = all(checks.values())
    return Response(
        {"status": "ok" if ready else "unavailable", "checks": checks},
        status=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def search(request):
    query = (request.query_params.get("q") or "").strip()
    search_type = (request.query_params.get("type") or "").strip()

    if search_type and search_type not in SEARCH_TYPES:
        return Response(
            {
                "type": [
                    "Invalid type. Expected one of: "
                    + ", ".join(SEARCH_TYPES)
                    + "."
                ]
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    results = []
    if not search_type or search_type == SEARCH_TYPE_BUSINESS:
        results.extend(_business_category_results(query))
    if not search_type or search_type == SEARCH_TYPE_DOCTOR:
        results.extend(_doctor_specialty_results(query))
    if not search_type or search_type == SEARCH_TYPE_PRODUCT:
        results.extend(_product_category_results(query))

    results.sort(key=lambda item: (item["sort_order"], item["name"].lower(), item["type"]))

    return Response([_public_search_item(item) for item in results])


def _business_category_results(query):
    categories = BusinessCategory.objects.filter(is_active=True)
    if query:
        categories = categories.filter(_category_search_filter(query))

    return [
        _category_item(category, SEARCH_TYPE_BUSINESS)
        for category in categories.order_by("sort_order", "name", "id")
    ]


def _doctor_specialty_results(query):
    specialties = DoctorSpecialty.objects.filter(is_active=True)
    if query:
        specialties = specialties.filter(
            Q(name__icontains=query)
            | Q(label__icontains=query)
            | Q(slug__icontains=query)
            | Q(aliases__icontains=query)
            | Q(body_part__icontains=query)
        )

    return [
        {
            "id": specialty.id,
            "type": SEARCH_TYPE_DOCTOR,
            "name": specialty.name,
            "label": specialty.label,
            "display_name": specialty.label or specialty.name,
            "slug": specialty.slug,
            "aliases": specialty.aliases,
            "sort_order": specialty.sort_order,
        }
        for specialty in specialties.order_by("sort_order", "name", "id")
    ]


def _product_category_results(query):
    categories = ProductCategory.objects.filter(is_active=True)
    if query:
        categories = categories.filter(_category_search_filter(query))

    return [
        _category_item(category, SEARCH_TYPE_PRODUCT)
        for category in categories.order_by("sort_order", "name", "id")
    ]


def _category_search_filter(query):
    return (
        Q(name__icontains=query)
        | Q(label__icontains=query)
        | Q(display_name__icontains=query)
        | Q(slug__icontains=query)
        | Q(aliases__icontains=query)
    )


def _category_item(category, item_type):
    return {
        "id": category.id,
        "type": item_type,
        "name": category.name,
        "label": category.label,
        "display_name": category.public_name,
        "slug": category.slug,
        "aliases": category.aliases,
        "sort_order": category.sort_order,
    }


def _public_search_item(item):
    item = item.copy()
    item.pop("sort_order", None)
    return item
