from django.core.paginator import Paginator
from django.db.models import Prefetch, Q

from businesses.models import Business
from catalogs.models import Catalog, CatalogCategory, CatalogImage


def list_catalog_categories(filters):
    queryset = CatalogCategory.objects.select_related("parent")

    if filters.get("id"):
        queryset = queryset.filter(pk=filters["id"])

    if filters.get("search"):
        search = filters["search"]
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(label__icontains=search)
            | Q(slug__icontains=search)
            | Q(aliases__icontains=search)
        )

    for field in ("name", "label", "aliases"):
        if filters.get(field):
            queryset = queryset.filter(**{f"{field}__icontains": filters[field]})

    if filters.get("display_name"):
        display_name = filters["display_name"]
        queryset = queryset.filter(
            Q(label__icontains=display_name)
            | Q(label="", name__icontains=display_name)
        )

    for field in ("slug", "type"):
        if filters.get(field):
            queryset = queryset.filter(**{field: filters[field]})

    if "parent" in filters:
        queryset = queryset.filter(parent_id=filters["parent"])
    elif "parent_slug" in filters:
        queryset = queryset.filter(parent__slug=filters["parent_slug"])
    elif "is_root" in filters:
        queryset = queryset.filter(parent__isnull=filters["is_root"])

    for field in ("is_active", "is_featured", "is_display"):
        if field in filters:
            queryset = queryset.filter(**{field: filters[field]})

    for prefix in ("created", "updated"):
        if filters.get(f"{prefix}_after"):
            queryset = queryset.filter(
                **{f"{prefix}_at__gte": filters[f"{prefix}_after"]}
            )
        if filters.get(f"{prefix}_before"):
            queryset = queryset.filter(
                **{f"{prefix}_at__lte": filters[f"{prefix}_before"]}
            )

    sort_field = "parent_id" if filters["sort_by"] == "parent" else filters["sort_by"]
    direction = "-" if filters["sort_order"] == "desc" else ""
    return queryset.order_by(f"{direction}{sort_field}", "id")


def paginate_catalog_categories(queryset, page, page_size):
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    return page_obj.object_list, {
        "page": page_obj.number,
        "page_size": page_size,
        "total_pages": paginator.num_pages,
        "total_items": paginator.count,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
    }


def get_public_business(slug):
    return Business.objects.only("id", "name", "slug").filter(
        slug=slug,
        status=Business.Status.PUBLISHED,
        is_active=True,
    ).first()


def list_public_products(business, filters):
    category_queryset = CatalogCategory.objects.filter(is_active=True).only(
        "id", "name", "label", "slug", "image", "sort_order"
    )
    primary_image_queryset = CatalogImage.objects.filter(
        is_active=True, is_primary=True
    ).only("catalog_id", "image")
    queryset = Catalog.objects.filter(
        business=business,
        type=Catalog.TypeChoices.PRODUCT,
        is_active=True,
    ).prefetch_related(
        Prefetch("categories", queryset=category_queryset),
        Prefetch("images", queryset=primary_image_queryset, to_attr="_prefetched_primary_images"),
    )

    if filters.get("category"):
        queryset = queryset.filter(
            categories__slug=filters["category"], categories__is_active=True
        )
    if filters.get("search"):
        search = filters["search"]
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
        )
    if filters.get("min_price") is not None:
        queryset = queryset.filter(price__gte=filters["min_price"])
    if filters.get("max_price") is not None:
        queryset = queryset.filter(price__lte=filters["max_price"])
    if filters.get("price_type"):
        queryset = queryset.filter(price_type=filters["price_type"])
    if "is_featured" in filters:
        queryset = queryset.filter(is_featured=filters["is_featured"])

    direction = "-" if filters["sort_order"] == "desc" else ""
    return queryset.distinct().order_by(f"{direction}{filters['sort_by']}", "id")


def list_available_product_categories(business):
    return (
        CatalogCategory.objects.filter(
            catalog_items__business=business,
            catalog_items__type=Catalog.TypeChoices.PRODUCT,
            catalog_items__is_active=True,
            is_active=True,
            is_display=True,
        )
        .distinct()
        .order_by("sort_order", "name")
    )


def get_public_product_by_slug(slug):
    categories = CatalogCategory.objects.filter(is_active=True).order_by(
        "sort_order", "name"
    )
    images = CatalogImage.objects.filter(is_active=True).order_by(
        "-is_primary", "sort_order", "created_at"
    )
    return (
        Catalog.objects.filter(
            slug=slug,
            type=Catalog.TypeChoices.PRODUCT,
            is_active=True,
            business__status=Business.Status.PUBLISHED,
            business__is_active=True,
        )
        .select_related("business", "business__city", "business__city__state")
        .prefetch_related(
            Prefetch("categories", queryset=categories),
            Prefetch("images", queryset=images),
        )
        .first()
    )


def get_catalog_for_owner(business, slug):
    return (
        Catalog.objects.filter(business=business, slug=slug)
        .prefetch_related("categories")
        .first()
    )


def paginate_products(queryset, page, page_size):
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    return page_obj.object_list, {
        "page": page_obj.number,
        "page_size": page_size,
        "total_pages": paginator.num_pages,
        "total_items": paginator.count,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
    }
