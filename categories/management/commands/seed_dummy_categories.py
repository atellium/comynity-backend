import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from categories.models import BusinessCategory


DEFAULT_CATEGORIES_FILE = Path(__file__).resolve().parents[3] / "categories.json"
CATEGORY_FIELDS = (
    "label",
    "display_name",
    "aliases",
    "icon",
    "sort_order",
    "is_active",
    "is_featured",
    "is_popular",
)


class Command(BaseCommand):
    help = "Create or update dummy business categories from categories.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=Path,
            default=DEFAULT_CATEGORIES_FILE,
            help="Path to the categories JSON file (defaults to categories.json in the project root).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        source = options["file"].resolve()

        try:
            categories = json.loads(source.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CommandError(f"Categories file not found: {source}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read categories from {source}: {exc}") from exc

        if not isinstance(categories, list):
            raise CommandError("The categories JSON must contain a list of category objects.")

        created_count = 0
        updated_count = 0

        for index, category in enumerate(categories, start=1):
            if not isinstance(category, dict):
                raise CommandError(f"Category #{index} must be a JSON object.")

            name = str(category.get("name", "")).strip()
            if not name:
                raise CommandError(f"Category #{index} is missing a non-empty name.")

            defaults = {
                field: category[field]
                for field in CATEGORY_FIELDS
                if field in category
            }
            _, created = BusinessCategory.objects.update_or_create(
                name=name,
                defaults=defaults,
            )
            created_count += created
            updated_count += not created

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(categories)} categories from {source} "
                f"({created_count} created, {updated_count} updated)."
            )
        )
