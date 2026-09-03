import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase

from categories.models import BusinessCategory


class SeedCategoriesCommandTests(TestCase):
    def run_seed(self, categories):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "categories.json"
            source.write_text(json.dumps(categories), encoding="utf-8")
            call_command("seed_categories", file=source)

    def test_seeds_only_four_supported_fields_and_uses_model_defaults(self):
        self.run_seed(
            [
                {
                    "name": " Grocery Store ",
                    "display_name": " Grocery ",
                    "label": " Grocery Stores ",
                    "aliases": " grocery,kirana ",
                    "icon": "should-be-ignored",
                    "sort_order": 99,
                    "is_active": False,
                }
            ]
        )

        category = BusinessCategory.objects.get(name="Grocery Store")
        self.assertEqual(category.display_name, "Grocery")
        self.assertEqual(category.label, "Grocery Stores")
        self.assertEqual(category.aliases, "grocery,kirana")
        self.assertIsNone(category.icon)
        self.assertEqual(category.sort_order, 0)
        self.assertTrue(category.is_active)
        self.assertFalse(category.is_featured)
        self.assertFalse(category.is_popular)

    def test_is_idempotent_and_updates_seeded_fields(self):
        category = BusinessCategory.objects.create(
            name="Grocery Store",
            display_name="Old name",
            label="Old label",
            aliases="old",
            icon="fa-shop",
            sort_order=10,
            is_featured=True,
        )

        self.run_seed(
            [
                {
                    "name": "Grocery Store",
                    "display_name": "Grocery",
                    "label": "Grocery Stores",
                    "aliases": "grocery,kirana",
                }
            ]
        )

        category.refresh_from_db()
        self.assertEqual(BusinessCategory.objects.count(), 1)
        self.assertEqual(category.display_name, "Grocery")
        self.assertEqual(category.label, "Grocery Stores")
        self.assertEqual(category.aliases, "grocery,kirana")
        self.assertEqual(category.icon, "fa-shop")
        self.assertEqual(category.sort_order, 10)
        self.assertTrue(category.is_featured)
