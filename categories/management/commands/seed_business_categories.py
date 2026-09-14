import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from categories.models import BusinessCategory


DEFAULT_CATEGORIES_FILE = (
    Path(__file__).resolve().parents[2] / "data" / "business_categories.json"
)


class Command(BaseCommand):
    help = "Create or update business categories from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=Path,
            default=DEFAULT_CATEGORIES_FILE,
            help="Path to the business categories JSON file.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        source = options["file"].resolve()
        categories = self._read_categories(source)

        created_count = 0
        updated_count = 0

        for index, category in enumerate(categories, start=1):
            values = self._validated_values(category, index)
            slug = values.pop("slug")
            parent_id = values.pop("parent_id")

            business_category = BusinessCategory.objects.filter(slug=slug).first()
            created = business_category is None

            if created:
                business_category = BusinessCategory(slug=slug)

            for field, value in values.items():
                setattr(business_category, field, value)

            business_category.parent_id = parent_id
            business_category.full_clean()
            business_category.save()

            created_count += int(created)
            updated_count += int(not created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(categories)} business categories from {source} "
                f"({created_count} created, {updated_count} updated)."
            )
        )

    def _read_categories(self, source):
        try:
            categories = json.loads(source.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CommandError(f"Business categories file not found: {source}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(
                f"Could not read business categories from {source}: {exc}"
            ) from exc

        if not isinstance(categories, list):
            raise CommandError(
                "The business categories JSON must contain a list of objects."
            )
        return categories

    def _validated_values(self, category, index):
        if not isinstance(category, dict):
            raise CommandError(f"Category #{index} must be a JSON object.")

        name = str(category.get("name", "")).strip()
        if not name:
            raise CommandError(f"Category #{index} is missing a non-empty name.")

        label = str(category.get("label", "")).strip()
        slug = str(category.get("slug") or slugify(label or name)).strip()
        if not slug:
            raise CommandError(f"Category #{index} slug could not be generated.")

        display_name = str(category.get("display_name", "")).strip()
        aliases = str(category.get("aliases", "")).strip()

        default_sort_order = BusinessCategory._meta.get_field("sort_order").default
        sort_order = category.get("sort_order", default_sort_order)
        if isinstance(sort_order, bool) or not isinstance(sort_order, int) or sort_order < 0:
            raise CommandError(
                f"Category #{index} sort_order must be a non-negative integer."
            )

        boolean_values = {}
        for field, default in (
            ("is_active", True),
            ("is_featured", False),
        ):
            value = category.get(field, default)
            if not isinstance(value, bool):
                raise CommandError(f"Category #{index} {field} must be a boolean.")
            boolean_values[field] = value

        parent_id = category.get("parent")
        if parent_id in ("", None):
            parent_id = None
        elif isinstance(parent_id, bool) or not isinstance(parent_id, int):
            raise CommandError(
                f"Category #{index} parent must be null or an existing category ID."
            )
        elif not BusinessCategory.objects.filter(pk=parent_id).exists():
            raise CommandError(
                f"Category #{index} parent with ID {parent_id} does not exist."
            )

        return {
            "slug": slug,
            "name": name,
            "display_name": display_name,
            "label": label,
            "aliases": aliases,
            "parent_id": parent_id,
            "sort_order": sort_order,
            **boolean_values,
        }
