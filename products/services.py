from django.core.paginator import Paginator
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Case, IntegerField, Q, When

from products.models import Product, ProductCategory


def order_products(queryset, sort_by="sort_order", sort_order="asc"):
    direction = "-" if sort_order == "desc" else ""
    if sort_by == "sort_order":
        return (
            queryset.annotate(
                sort_order_group=Case(
                    When(sort_order=0, then=1),
                    default=0,
                    output_field=IntegerField(),
                )
            )
            .order_by("sort_order_group", f"{direction}sort_order", "-created_at")
        )
    return queryset.order_by(f"{direction}{sort_by}", "id")


def list_public_products(business, filters):
    queryset = (
        Product.objects.filter(
            business=business,
            status=Product.Status.ACTIVE,
        )
        .prefetch_related("categories", "product_images__upload")
        .distinct()
    )

    if filters.get("category"):
        queryset = queryset.filter(categories__slug=filters["category"])

    if filters.get("search"):
        search = filters["search"]
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
            | Q(categories__name__icontains=search)
            | Q(categories__label__icontains=search)
            | Q(categories__display_name__icontains=search)
        )

    if filters.get("min_price") is not None:
        queryset = queryset.filter(price__gte=filters["min_price"])
    if filters.get("max_price") is not None:
        queryset = queryset.filter(price__lte=filters["max_price"])
    if filters.get("price_type"):
        queryset = queryset.filter(price_type=filters["price_type"])
    if "is_featured" in filters:
        queryset = queryset.filter(is_featured=filters["is_featured"])

    return order_products(queryset.distinct(), filters["sort_by"], filters["sort_order"])


def list_nearby_products(filters):
    user_location = Point(float(filters["lng"]), float(filters["lat"]), srid=4326)
    return (
        Product.objects.filter(
            status=Product.Status.ACTIVE,
            is_available=True,
            business__is_active=True,
            business__location__isnull=False,
            categories__slug=filters["category"],
            categories__is_active=True,
        )
        .filter(
            business__location__distance_lte=(
                user_location,
                D(km=filters["radius_km"]),
            )
        )
        .annotate(distance=Distance("business__location", user_location))
        .select_related(
            "business",
            "business__city",
            "business__city__state",
            "business__cover_image",
        )
        .prefetch_related("categories", "product_images__upload")
        .order_by("distance", "sort_order", "-created_at")
        .distinct()
    )


def find_active_product_category(slug):
    return ProductCategory.objects.filter(slug=slug, is_active=True).first()


def list_featured_product_categories(business):
    return (
        ProductCategory.objects.filter(
            products__business=business,
            products__status=Product.Status.ACTIVE,
            is_active=True,
            is_featured=True,
        )
        .select_related("parent")
        .distinct()
        .order_by("sort_order", "name", "id")
    )


def list_product_categories(filters):
    queryset = ProductCategory.objects.select_related("parent").all()

    if filters.get("id"):
        queryset = queryset.filter(pk=filters["id"])

    if filters.get("search"):
        search = filters["search"]
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(display_name__icontains=search)
            | Q(label__icontains=search)
            | Q(slug__icontains=search)
            | Q(aliases__icontains=search)
        )

    for field in ("name", "label", "display_name", "aliases"):
        if filters.get(field):
            queryset = queryset.filter(**{f"{field}__icontains": filters[field]})

    if filters.get("slug"):
        queryset = queryset.filter(slug=filters["slug"])

    if filters.get("parent"):
        queryset = queryset.filter(parent_id=filters["parent"])
    elif filters.get("parent_slug"):
        queryset = queryset.filter(parent__slug=filters["parent_slug"])
    elif "is_root" in filters:
        queryset = queryset.filter(parent__isnull=filters["is_root"])

    for field in ("is_active", "is_featured"):
        if field in filters:
            queryset = queryset.filter(**{field: filters[field]})

    for field in ("created", "updated"):
        if filters.get(f"{field}_after"):
            queryset = queryset.filter(**{f"{field}_at__gte": filters[f"{field}_after"]})
        if filters.get(f"{field}_before"):
            queryset = queryset.filter(**{f"{field}_at__lte": filters[f"{field}_before"]})

    sort_by = "parent_id" if filters["sort_by"] == "parent" else filters["sort_by"]
    direction = "-" if filters["sort_order"] == "desc" else ""
    return queryset.order_by(f"{direction}{sort_by}", "id")


def paginate_product_categories(queryset, page, page_size):
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    pagination = {
        "page": page_obj.number,
        "page_size": page_size,
        "total_pages": paginator.num_pages,
        "total_items": paginator.count,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
    }
    return page_obj.object_list, pagination


def paginate_products(queryset, page, page_size):
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    pagination = {
        "page": page_obj.number,
        "page_size": page_size,
        "total_pages": paginator.num_pages,
        "total_items": paginator.count,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
    }
    return page_obj.object_list, pagination
