from django.contrib import admin
from django.contrib.gis.geos import Point
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from locations.admin import CityAdmin, LocalityAdmin, StateAdmin
from locations.models import City, Locality, State


class LocationAdminTests(SimpleTestCase):
    def test_all_location_models_use_custom_admins(self):
        self.assertIsInstance(admin.site._registry[State], StateAdmin)
        self.assertIsInstance(admin.site._registry[City], CityAdmin)
        self.assertIsInstance(admin.site._registry[Locality], LocalityAdmin)

    def test_related_fields_use_autocomplete(self):
        self.assertIn("state", admin.site._registry[City].autocomplete_fields)
        self.assertIn("city", admin.site._registry[Locality].autocomplete_fields)


class NearestLocalityEndpointTests(APITestCase):
    def setUp(self):
        state = State.objects.create(name="West Bengal", slug="west-bengal", code="WB")
        kolkata = City.objects.create(name="Kolkata", slug="kolkata", state=state)
        howrah = City.objects.create(name="Howrah", slug="howrah", state=state)
        Locality.objects.create(
            name="Salt Lake",
            slug="salt-lake",
            city=kolkata,
            center=Point(88.4171, 22.5867, srid=4326),
        )
        Locality.objects.create(
            name="Shibpur",
            slug="shibpur",
            city=howrah,
            center=Point(88.3069, 22.5575, srid=4326),
        )

    def test_returns_nearest_locality_and_city(self):
        response = self.client.post(
            reverse("locations:nearest-locality"),
            {"lat": 22.58, "lng": 88.41},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()["name"],
            "Salt Lake",
        )
        self.assertEqual(response.json()["city"], "Kolkata")
        self.assertEqual(response.json()["city_slug"], "kolkata")
        self.assertNotIn("state", response.json())
        self.assertNotIn("distance_km", response.json())

    def test_rejects_coordinates_outside_valid_ranges(self):
        response = self.client.post(
            reverse("locations:nearest-locality"),
            {"lat": 91, "lng": 181},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CityListEndpointTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        west_bengal = State.objects.create(
            name="West Bengal", slug="west-bengal", code="WB"
        )
        karnataka = State.objects.create(
            name="Karnataka", slug="karnataka", code="KA"
        )
        cls.bengaluru = City.objects.create(
            name="Bengaluru", slug="bengaluru", state=karnataka, tier=1
        )
        cls.kolkata = City.objects.create(
            name="Kolkata", slug="kolkata", state=west_bengal, tier=1
        )

    def test_lists_all_cities_with_state_metadata(self):
        response = self.client.get(reverse("locations:city-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": self.bengaluru.id,
                    "name": "Bengaluru",
                    "slug": "bengaluru",
                    "tier": 1,
                    "state": {
                        "id": self.bengaluru.state_id,
                        "name": "Karnataka",
                        "slug": "karnataka",
                        "code": "KA",
                    },
                },
                {
                    "id": self.kolkata.id,
                    "name": "Kolkata",
                    "slug": "kolkata",
                    "tier": 1,
                    "state": {
                        "id": self.kolkata.state_id,
                        "name": "West Bengal",
                        "slug": "west-bengal",
                        "code": "WB",
                    },
                },
            ],
        )

    def test_filters_city_names_case_insensitively(self):
        response = self.client.get(
            reverse("locations:city-list"), {"search": "KAT"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [city["slug"] for city in response.json()],
            ["kolkata"],
        )

    def test_rejects_blank_search(self):
        response = self.client.get(reverse("locations:city-list"), {"search": " "})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class SearchLocalitiesEndpointTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        state = State.objects.create(name="West Bengal", slug="west-bengal", code="WB")
        city = City.objects.create(name="Kolkata", slug="kolkata", state=state)
        cls.salt_lake = Locality.objects.create(
            name="Salt Lake",
            slug="salt-lake",
            city=city,
            center=Point(88.4171, 22.5867, srid=4326),
        )
        cls.saltora = Locality.objects.create(
            name="Saltora", slug="saltora", city=city
        )
        Locality.objects.create(name="New Town", slug="new-town", city=city)

    def test_returns_localities_whose_names_start_with_query(self):
        response = self.client.get(
            reverse("locations:search-localities"),
            {"query": "salt"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": self.salt_lake.id,
                    "name": "Salt Lake",
                    "slug": "salt-lake",
                    "city": "Kolkata",
                    "city_slug": "kolkata",
                    "latitude": 22.5867,
                    "longitude": 88.4171,
                },
                {
                    "id": self.saltora.id,
                    "name": "Saltora",
                    "slug": "saltora",
                    "city": "Kolkata",
                    "city_slug": "kolkata",
                    "latitude": None,
                    "longitude": None,
                },
            ],
        )

    def test_requires_a_non_empty_query(self):
        for params in ({}, {"query": "   "}):
            with self.subTest(params=params):
                response = self.client.get(
                    reverse("locations:search-localities"), params
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
