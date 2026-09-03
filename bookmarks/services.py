from django.db.models import Prefetch

from bookmarks.models import SavedItem
from businesses.models import Business
from businesses.services import business_response_queryset
from catalogs.models import Catalog, CatalogCategory, CatalogImage


def resolve_saved_items(saved_items):
    """Bulk-fetch saved targets and return them keyed by type and object ID."""
    ids_by_type = {
        SavedItem.ItemType.BUSINESS: [],
        SavedItem.ItemType.PRODUCT: [],
    }
    for saved_item in saved_items:
        if saved_item.item_type in ids_by_type:
            ids_by_type[saved_item.item_type].append(saved_item.object_id)

    businesses = business_response_queryset().filter(
        pk__in=ids_by_type[SavedItem.ItemType.BUSINESS],
        status=Business.Status.PUBLISHED,
        is_active=True,
    )

    categories = CatalogCategory.objects.filter(is_active=True).only(
        "id", "name", "label", "slug", "image", "sort_order"
    )
    primary_images = CatalogImage.objects.filter(
        is_active=True, is_primary=True
    ).only("catalog_id", "image")
    products = Catalog.objects.filter(
        pk__in=ids_by_type[SavedItem.ItemType.PRODUCT],
        type=Catalog.TypeChoices.PRODUCT,
        is_active=True,
        business__status=Business.Status.PUBLISHED,
        business__is_active=True,
    ).prefetch_related(
        Prefetch("categories", queryset=categories),
        Prefetch(
            "images",
            queryset=primary_images,
            to_attr="_prefetched_primary_images",
        ),
    )

    return {
        SavedItem.ItemType.BUSINESS: {item.pk: item for item in businesses},
        SavedItem.ItemType.PRODUCT: {item.pk: item for item in products},
    }
