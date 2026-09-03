from django.contrib.gis.db.models.functions import Distance, GeometryDistance
from django.contrib.gis.geos import Point

from locations.models import Locality


def find_nearest_locality(lat, lng):
    """Return the closest locality using PostGIS nearest-neighbor ordering."""
    user_location = Point(float(lng), float(lat), srid=4326)
    return (
        Locality.objects.filter(center__isnull=False)
        .select_related("city__state")
        .annotate(distance=Distance("center", user_location))
        .order_by(GeometryDistance("center", user_location), "pk")
        .first()
    )
