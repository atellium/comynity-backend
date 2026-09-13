from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction

from locations.models import City, Locality, State


LOCATIONS = (
    ("Indiranagar", "indiranagar", 12.9784, 77.6408),
    ("Koramangala", "koramangala", 12.9352, 77.6245),
    ("Jayanagar", "jayanagar", 12.9250, 77.5938),
    ("Whitefield", "whitefield", 12.9698, 77.7500),
    ("Yelahanka", "yelahanka", 13.1005, 77.5940),
)


class Command(BaseCommand):
    help = "Create or update a repeatable dummy state, city, and locality dataset."

    @transaction.atomic
    def handle(self, *args, **options):
        state, _ = State.objects.update_or_create(
            code="KA",
            defaults={"name": "Karnataka", "slug": "karnataka"},
        )
        city, _ = City.objects.update_or_create(
            slug="bengaluru",
            defaults={
                "name": "Bengaluru",
                "state": state,
                "tier": City.CityTier.TIER_1,
            },
        )
        for name, slug, latitude, longitude in LOCATIONS:
            Locality.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "city": city,
                    "aliases": "",
                    "center": Point(longitude, latitude, srid=4326),
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded 1 state, 1 city, and {len(LOCATIONS)} localities."
            )
        )
