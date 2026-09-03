from django.core.paginator import Paginator
from django.db.models import Q

from categories.models import BusinessCategory, ProductCategory


def list_business_categories(filters):
    """Return business categories matching validated API filters."""
    queryset = BusinessCategory.objects.all()

    if filters.get("search"):
        search = filters["search"]
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(display_name__icontains=search)
            | Q(label__icontains=search)
            | Q(slug__icontains=search)
            | Q(aliases__icontains=search)
        )

    for field in ("name", "label", "display_name"):
        if filters.get(field):
            queryset = queryset.filter(**{f"{field}__icontains": filters[field]})

    if filters.get("slug"):
        queryset = queryset.filter(slug=filters["slug"])

    for field in ("is_active", "is_featured"):
        if field in filters:
            queryset = queryset.filter(**{field: filters[field]})

    for field in ("created", "updated"):
        if filters.get(f"{field}_after"):
            queryset = queryset.filter(**{f"{field}_at__gte": filters[f"{field}_after"]})
        if filters.get(f"{field}_before"):
            queryset = queryset.filter(**{f"{field}_at__lte": filters[f"{field}_before"]})

    direction = "-" if filters["sort_order"] == "desc" else ""
    return queryset.order_by(f"{direction}{filters['sort_by']}", "id")


def list_product_categories(filters):
    """Return product categories matching validated API filters."""
    queryset = ProductCategory.objects.select_related("parent")

    if filters.get("search"):
        search = filters["search"]
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(display_name__icontains=search)
            | Q(label__icontains=search)
            | Q(slug__icontains=search)
            | Q(aliases__icontains=search)
        )

    for field in ("name", "label", "display_name"):
        if filters.get(field):
            queryset = queryset.filter(**{f"{field}__icontains": filters[field]})

    if filters.get("slug"):
        queryset = queryset.filter(slug=filters["slug"])
    if "parent" in filters:
        queryset = queryset.filter(parent_id=filters["parent"])
    if "is_root" in filters:
        queryset = queryset.filter(parent__isnull=filters["is_root"])

    for field in ("is_active", "is_featured"):
        if field in filters:
            queryset = queryset.filter(**{field: filters[field]})

    for field in ("created", "updated"):
        if filters.get(f"{field}_after"):
            queryset = queryset.filter(**{f"{field}_at__gte": filters[f"{field}_after"]})
        if filters.get(f"{field}_before"):
            queryset = queryset.filter(**{f"{field}_at__lte": filters[f"{field}_before"]})

    direction = "-" if filters["sort_order"] == "desc" else ""
    return queryset.order_by(f"{direction}{filters['sort_by']}", "id")


def paginate_categories(queryset, page, page_size):
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


def list_visible_categories():
    """Return active categories in their configured display order."""
    return BusinessCategory.objects.filter(is_active=True).only(
        "id",
        "name",
        "label",
        "display_name",
        "slug",
        "aliases",
        "image",
        "sort_order",
    )
