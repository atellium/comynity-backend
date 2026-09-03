import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from categories.models import BusinessCategory


DEFAULT_CATEGORIES_FILE = Path(__file__).resolve().parents[3] / "seed_categories.json"
SEEDED_FIELDS = ("name", "display_name", "label", "aliases")


class Command(BaseCommand):
    help = "Create or update production business categories from seed_categories.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=Path,
            default=DEFAULT_CATEGORIES_FILE,
            help=(
                "Path to the categories JSON file "
                "(defaults to seed_categories.json in the project root)."
            ),
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

            values = {
                field: str(category.get(field, "")).strip()
                for field in SEEDED_FIELDS
            }
            if not values["name"]:
                raise CommandError(f"Category #{index} is missing a non-empty name.")

            name = values.pop("name")
            _, created = BusinessCategory.objects.update_or_create(
                name=name,
                defaults=values,
            )
            created_count += created
            updated_count += not created

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(categories)} categories from {source} "
                f"({created_count} created, {updated_count} updated)."
            )
        )
