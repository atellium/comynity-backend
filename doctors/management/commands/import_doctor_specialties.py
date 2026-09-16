import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_slug
from django.db import transaction

from doctors.models import DoctorSpecialty


DEFAULT_FILE = Path(__file__).resolve().parents[2] / "data" / "doctor_specialty.json"
ALLOWED_FIELDS = {"name", "label", "slug", "aliases", "body_part", "sort_order", "is_active", "is_featured"}


class Command(BaseCommand):
    help = "Create or update doctor specialties from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=Path,
            default=DEFAULT_FILE,
            help="Path to a JSON array containing doctor specialty objects.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        specialties = self._load_file(options["file"])
        created_count = 0
        updated_count = 0
        seen_slugs = set()

        for index, item in enumerate(specialties, start=1):
            specialty = self._validate_item(item, index, seen_slugs)
            _, created = DoctorSpecialty.objects.update_or_create(
                slug=specialty["slug"],
                defaults={
                    "name": specialty["name"],
                    "label": specialty["label"],
                    "aliases": specialty["aliases"],
                    "body_part": specialty["body_part"],
                    "sort_order": specialty["sort_order"],
                    "is_active": specialty["is_active"],
                    "is_featured": specialty["is_featured"],
                },
            )
            created_count += int(created)
            updated_count += int(not created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(specialties)} doctor specialties: "
                f"{created_count} created, {updated_count} updated."
            )
        )

    @staticmethod
    def _load_file(file_path):
        try:
            with file_path.open(encoding="utf-8") as source:
                data = json.load(source)
        except FileNotFoundError as exc:
            raise CommandError(f"Doctor specialty file does not exist: {file_path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read doctor specialty JSON: {exc}") from exc

        if not isinstance(data, list):
            raise CommandError("Doctor specialty JSON must contain an array of objects.")
        return data

    @staticmethod
    def _validate_item(item, index, seen_slugs):
        if not isinstance(item, dict):
            raise CommandError(f"Doctor specialty #{index} must be a JSON object.")

        unsupported = set(item) - ALLOWED_FIELDS
        if unsupported:
            fields = ", ".join(sorted(unsupported))
            raise CommandError(
                f"Doctor specialty #{index} has unsupported fields: {fields}."
            )

        name = _required_string(item, "name", index, max_length=100)
        label = _required_string(item, "label", index, max_length=120)
        slug = _required_string(item, "slug", index, max_length=120)
        try:
            validate_slug(slug)
        except ValidationError as exc:
            raise CommandError(f"Doctor specialty #{index} has an invalid slug.") from exc

        if slug in seen_slugs:
            raise CommandError(f"Doctor specialty #{index} repeats slug {slug!r}.")
        seen_slugs.add(slug)

        aliases = item.get("aliases", "")
        if not isinstance(aliases, str):
            raise CommandError(f"Doctor specialty #{index} aliases must be a string.")
        aliases = aliases.strip()
        if len(aliases) > 255:
            raise CommandError(
                f"Doctor specialty #{index} aliases cannot exceed 255 characters."
            )

        body_part = item.get("body_part", "")
        if not isinstance(body_part, str):
            raise CommandError(f"Doctor specialty #{index} body_part must be a string.")
        body_part = body_part.strip()
        body_part_values = {choice.value for choice in DoctorSpecialty.BodyPartChoices}
        if body_part and body_part not in body_part_values:
            raise CommandError(
                f"Doctor specialty #{index} has unsupported body_part {body_part!r}."
            )

        sort_order = item.get("sort_order", 0)
        if isinstance(sort_order, bool) or not isinstance(sort_order, int) or sort_order < 0:
            raise CommandError(
                f"Doctor specialty #{index} sort_order must be a non-negative integer."
            )
        if sort_order > 32767:
            raise CommandError(
                f"Doctor specialty #{index} sort_order cannot exceed 32767."
            )

        is_active = _optional_bool(item, "is_active", index, default=True)
        is_featured = _optional_bool(item, "is_featured", index, default=False)

        return {
            "name": name,
            "label": label,
            "slug": slug,
            "aliases": aliases,
            "body_part": body_part,
            "sort_order": sort_order,
            "is_active": is_active,
            "is_featured": is_featured,
        }


def _required_string(item, field_name, index, *, max_length):
    value = item.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise CommandError(
            f"Doctor specialty #{index} requires a non-empty {field_name}."
        )
    value = value.strip()
    if len(value) > max_length:
        raise CommandError(
            f"Doctor specialty #{index} {field_name} cannot exceed {max_length} characters."
        )
    return value


def _optional_bool(item, field_name, index, *, default):
    value = item.get(field_name, default)
    if not isinstance(value, bool):
        raise CommandError(f"Doctor specialty #{index} {field_name} must be a boolean.")
    return value
