import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from locations.models import City, Locality, State


class ImportLocalitiesCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        state = State.objects.create(name="Karnataka", slug="karnataka", code="KA")
        cls.city = City.objects.create(
            name="Bengaluru",
            slug="bengaluru",
            state=state,
            tier=City.CityTier.TIER_1,
        )

    def run_import(self, data):
        with TemporaryDirectory() as directory:
            file_path = Path(directory) / "localities.json"
            file_path.write_text(json.dumps(data), encoding="utf-8")
            output = StringIO()
            call_command(
                "import_localities",
                city_id=self.city.id,
                file=file_path,
                stdout=output,
            )
            return output.getvalue()

    def test_creates_and_updates_localities_for_the_selected_city(self):
        data = [
            {
                "name": "Indiranagar",
                "slug": "indiranagar",
                "aliases": "Indira Nagar",
                "latitude": 12.9784,
                "longitude": 77.6408,
            }
        ]

        first_output = self.run_import(data)
        data[0]["name"] = "Indira Nagar"
        second_output = self.run_import(data)

        locality = Locality.objects.get(city=self.city, slug="indiranagar")
        self.assertEqual(locality.name, "Indira Nagar")
        self.assertAlmostEqual(locality.latitude, 12.9784, places=4)
        self.assertAlmostEqual(locality.longitude, 77.6408, places=4)
        self.assertIn("1 created, 0 updated", first_output)
        self.assertIn("0 created, 1 updated", second_output)

    def test_rejects_incomplete_coordinates_without_writing_data(self):
        with self.assertRaises(CommandError):
            self.run_import(
                [
                    {
                        "name": "Indiranagar",
                        "slug": "indiranagar",
                        "latitude": 12.9784,
                        "longitude": None,
                    }
                ]
            )

        self.assertFalse(Locality.objects.exists())
