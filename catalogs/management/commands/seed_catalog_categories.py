import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify

from catalogs.models import CatalogCategory


DEFAULT_CATEGORIES_FILE = (
    Path(__file__).resolve().parents[2] / "data" / "categories.json"
)


class Command(BaseCommand):
    help = "Create or update catalog categories from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=Path,
            default=DEFAULT_CATEGORIES_FILE,
            help="Path to the categories JSON file.",
        )
        parser.add_argument(
            "--parent-id",
            type=int,
            help=(
                "Attach every imported category to this catalog category. "
                "When omitted, imported categories are saved as roots."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        source = options["file"].resolve()
        parent = self._get_parent(options.get("parent_id"))
        categories = self._read_categories(source)

        created_count = 0
        updated_count = 0

        for index, category in enumerate(categories, start=1):
            values = self._validated_values(category, index, parent)
            name = values.pop("name")
            category_type = values.pop("type")
            slug = values.pop("slug")

            catalog_category = self._find_existing_category(
                category_type=category_type,
                name=name,
                slug=slug,
                index=index,
            )
            if catalog_category is None:
                catalog_category = CatalogCategory(
                    type=category_type,
                    name=name,
                    slug=slug,
                )
                created = True
            else:
                created = False
                catalog_category.type = category_type
                catalog_category.name = name
                catalog_category.slug = slug

            for field, value in values.items():
                setattr(catalog_category, field, value)
            catalog_category.parent = parent
            catalog_category.save()

            created_count += int(created)
            updated_count += int(not created)

        parent_description = f"parent ID {parent.pk}" if parent else "root"
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(categories)} catalog categories from {source} "
                f"as {parent_description} categories "
                f"({created_count} created, {updated_count} updated)."
            )
        )

    def _get_parent(self, parent_id):
        if parent_id is None:
            return None

        try:
            return CatalogCategory.objects.get(pk=parent_id)
        except CatalogCategory.DoesNotExist as exc:
            raise CommandError(
                f"Catalog category parent with ID {parent_id} does not exist."
            ) from exc

    def _read_categories(self, source):
        try:
            categories = json.loads(source.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CommandError(f"Categories file not found: {source}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read categories from {source}: {exc}") from exc

        if not isinstance(categories, list):
            raise CommandError("The categories JSON must contain a list of objects.")
        return categories

    def _find_existing_category(self, *, category_type, name, slug, index):
        matches = list(
            CatalogCategory.objects.filter(
                Q(slug=slug) | Q(name=name),
                type=category_type,
            )[:2]
        )
        if len(matches) > 1:
            raise CommandError(
                f"Category #{index} matches multiple existing categories by "
                "name and slug. Make name and slug point to the same category."
            )
        return matches[0] if matches else None

    def _validated_values(self, category, index, parent):
        if not isinstance(category, dict):
            raise CommandError(f"Category #{index} must be a JSON object.")

        name = str(category.get("name", "")).strip()
        if not name:
            raise CommandError(f"Category #{index} is missing a non-empty name.")

        category_type = str(
            category.get("type", CatalogCategory.TypeChoices.PRODUCT)
        ).strip()
        valid_types = set(CatalogCategory.TypeChoices.values)
        if category_type not in valid_types:
            raise CommandError(
                f"Category #{index} has unsupported type {category_type!r}."
            )
        if parent and parent.type != category_type:
            raise CommandError(
                f"Category #{index} has type {category_type!r}, but parent "
                f"ID {parent.pk} has type {parent.type!r}."
            )

        sort_order = category.get("sort_order", 0)
        if isinstance(sort_order, bool) or not isinstance(sort_order, int) or sort_order < 0:
            raise CommandError(
                f"Category #{index} sort_order must be a non-negative integer."
            )

        boolean_values = {}
        for field, default in (
            ("is_active", True),
            ("is_featured", False),
            ("is_display", True),
        ):
            value = category.get(field, default)
            if not isinstance(value, bool):
                raise CommandError(f"Category #{index} {field} must be a boolean.")
            boolean_values[field] = value

        slug = str(category.get("slug") or slugify(category.get("label") or name)).strip()
        if not slug:
            raise CommandError(f"Category #{index} slug could not be generated.")

        return {
            "name": name,
            "type": category_type,
            "slug": slug,
            "label": str(category.get("label", "")).strip(),
            "aliases": str(category.get("aliases", "")).strip(),
            "sort_order": sort_order,
            **boolean_values,
        }
