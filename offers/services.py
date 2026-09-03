from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.core.paginator import Paginator
from django.db.models import ExpressionWrapper, FloatField

from businesses.services import list_businesses
from offers.models import Offer


def list_nearby_offers(filters, *, now=None):
    """Return current offers for businesses accepted by the public nearby query."""

    business_filters = dict(filters)
    business_filters["publication_status"] = "published"
    business_filters["is_active"] = True
    nearby_businesses = list_businesses(business_filters, now=now)
    origin = Point(filters["lng"], filters["lat"], srid=4326)
    direction = "-" if filters["sort_order"] == "desc" else ""

    return (
        Offer.objects.active()
        .filter(business_id__in=nearby_businesses.order_by().values("pk"))
        .select_related("business", "business__city", "business__city__state")
        .annotate(
            distance_km=ExpressionWrapper(
                Distance("business__location", origin) / 1000.0,
                output_field=FloatField(),
            )
        )
        .order_by(f"{direction}distance_km", "sort_order", "-created_at", "id")
    )


def paginate_offers(queryset, page, page_size):
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
