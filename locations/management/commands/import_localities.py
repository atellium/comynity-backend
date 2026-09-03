import json
from pathlib import Path

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_slug
from django.db import transaction

from locations.models import City, Locality


ALLOWED_FIELDS = {"name", "slug", "aliases", "latitude", "longitude"}


class Command(BaseCommand):
    help = "Create or update localities for one city from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--city-id",
            type=int,
            required=True,
            help="Database ID of the city that owns every imported locality.",
        )
        parser.add_argument(
            "--file",
            type=Path,
            required=True,
            help="Path to a JSON array containing locality objects.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        city = City.objects.filter(pk=options["city_id"]).first()
        if city is None:
            raise CommandError(f"City with ID {options['city_id']} does not exist.")

        localities = self._load_file(options["file"])
        created_count = 0
        updated_count = 0
        seen_slugs = set()

        for index, item in enumerate(localities, start=1):
            locality = self._validate_item(item, index, seen_slugs)
            center = None
            if locality["latitude"] is not None:
                center = Point(
                    locality["longitude"],
                    locality["latitude"],
                    srid=4326,
                )

            _, created = Locality.objects.update_or_create(
                city=city,
                slug=locality["slug"],
                defaults={
                    "name": locality["name"],
                    "aliases": locality["aliases"],
                    "center": center,
                },
            )
            created_count += int(created)
            updated_count += int(not created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(localities)} localities for {city.name}: "
                f"{created_count} created, {updated_count} updated."
            )
        )

    @staticmethod
    def _load_file(file_path):
        try:
            with file_path.open(encoding="utf-8") as source:
                data = json.load(source)
        except FileNotFoundError as exc:
            raise CommandError(f"Locality file does not exist: {file_path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read locality JSON: {exc}") from exc

        if not isinstance(data, list):
            raise CommandError("Locality JSON must contain an array of objects.")
        return data

    @staticmethod
    def _validate_item(item, index, seen_slugs):
        if not isinstance(item, dict):
            raise CommandError(f"Locality #{index} must be a JSON object.")

        unsupported = set(item) - ALLOWED_FIELDS
        if unsupported:
            fields = ", ".join(sorted(unsupported))
            raise CommandError(f"Locality #{index} has unsupported fields: {fields}.")

        name = item.get("name")
        slug = item.get("slug")
        if not isinstance(name, str) or not name.strip():
            raise CommandError(f"Locality #{index} requires a non-empty name.")
        if not isinstance(slug, str) or not slug.strip():
            raise CommandError(f"Locality #{index} requires a non-empty slug.")

        name = name.strip()
        slug = slug.strip()
        if len(name) > 100:
            raise CommandError(f"Locality #{index} name cannot exceed 100 characters.")
        if len(slug) > 100:
            raise CommandError(f"Locality #{index} slug cannot exceed 100 characters.")
        try:
            validate_slug(slug)
        except ValidationError as exc:
            raise CommandError(f"Locality #{index} has an invalid slug.") from exc
        aliases = item.get("aliases", "")
        if not isinstance(aliases, str):
            raise CommandError(f"Locality #{index} aliases must be a string.")
        aliases = aliases.strip()
        if len(aliases) > 300:
            raise CommandError(f"Locality #{index} aliases cannot exceed 300 characters.")

        if slug in seen_slugs:
            raise CommandError(f"Locality #{index} repeats slug {slug!r}.")
        seen_slugs.add(slug)

        latitude = item.get("latitude")
        longitude = item.get("longitude")
        if (latitude is None) != (longitude is None):
            raise CommandError(
                f"Locality #{index} must provide both latitude and longitude or neither."
            )
        if latitude is not None:
            if isinstance(latitude, bool) or not isinstance(latitude, (int, float)):
                raise CommandError(f"Locality #{index} latitude must be a number.")
            if isinstance(longitude, bool) or not isinstance(longitude, (int, float)):
                raise CommandError(f"Locality #{index} longitude must be a number.")
            if not -90 <= latitude <= 90:
                raise CommandError(f"Locality #{index} latitude must be between -90 and 90.")
            if not -180 <= longitude <= 180:
                raise CommandError(
                    f"Locality #{index} longitude must be between -180 and 180."
                )

        return {
            "name": name,
            "slug": slug,
            "aliases": aliases,
            "latitude": latitude,
            "longitude": longitude,
        }
