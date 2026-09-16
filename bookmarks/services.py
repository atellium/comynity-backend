from bookmarks.models import SavedItem
from businesses.models import Business
from businesses.services import business_response_queryset
from doctors.models import Doctor
from products.models import Product


def resolve_saved_items(saved_items):
    """Bulk-fetch saved targets and return them keyed by type and object ID."""
    ids_by_type = {
        SavedItem.ItemType.BUSINESS: [],
        SavedItem.ItemType.PRODUCT: [],
        SavedItem.ItemType.DOCTOR: [],
    }
    for saved_item in saved_items:
        if saved_item.item_type in ids_by_type:
            ids_by_type[saved_item.item_type].append(saved_item.object_id)

    businesses = business_response_queryset().filter(
        pk__in=ids_by_type[SavedItem.ItemType.BUSINESS],
        status=Business.Status.PUBLISHED,
        is_active=True,
    )

    products = Product.objects.filter(
        pk__in=ids_by_type[SavedItem.ItemType.PRODUCT],
        status=Product.Status.ACTIVE,
        is_available=True,
        business__status=Business.Status.PUBLISHED,
        business__is_active=True,
    ).prefetch_related(
        "categories",
        "product_images__upload",
    )

    doctors = (
        Doctor.objects.filter(
            pk__in=ids_by_type[SavedItem.ItemType.DOCTOR],
            is_active=True,
            business__is_active=True,
        )
        .select_related(
            "business",
            "business__city",
            "business__profile",
            "business__cover_image",
        )
        .prefetch_related(
            "specialties",
            "schedules",
            "business__categories",
            "business__business_hours",
        )
    )

    return {
        SavedItem.ItemType.BUSINESS: {item.pk: item for item in businesses},
        SavedItem.ItemType.PRODUCT: {item.pk: item for item in products},
        SavedItem.ItemType.DOCTOR: {item.pk: item for item in doctors},
    }
