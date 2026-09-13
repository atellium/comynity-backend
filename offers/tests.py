from django.test import TestCase

# Create your tests here.
from django.contrib import admin
from django.core.management.base import CommandError
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from offers.admin import OfferAdmin
from offers.models import Offer
from offers.serializers import NearbyOfferListQuerySerializer, OfferWriteSerializer
from offers.management.commands.seed_dummy_offers import validate_offer_count


class OfferAdminTests(SimpleTestCase):
    def test_offer_uses_custom_admin(self):
        self.assertIsInstance(admin.site._registry[Offer], OfferAdmin)

    def test_business_uses_autocomplete(self):
        self.assertIn("business", admin.site._registry[Offer].autocomplete_fields)


class OfferEndpointContractTests(SimpleTestCase):
    def test_nearby_list_url(self):
        self.assertEqual(
            reverse("offers:nearby-offer-list"),
            "/api/offers/nearby/",
        )

    def test_nearby_list_requires_coordinates(self):
        serializer = NearbyOfferListQuerySerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), {"lat", "lng"})

    def test_nearby_list_uses_business_radius_and_pagination_parameters(self):
        serializer = NearbyOfferListQuerySerializer(
            data={
                "lat": "22.5726",
                "lng": "88.3639",
                "radius_km": "10",
                "page": "2",
                "page_size": "5",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["radius_km"], 10.0)
        self.assertEqual(serializer.validated_data["page"], 2)

    def test_create_url_is_scoped_to_owned_business(self):
        self.assertEqual(
            reverse(
                "offers:offer-create",
                kwargs={"business_slug": "royal-store"},
            ),
            "/api/businesses/mine/royal-store/offers/",
        )

    def test_collection_view_supports_get_and_post(self):
        from offers.views import offer_create

        self.assertEqual(set(offer_create.cls.http_method_names), {"get", "post", "options"})

    def test_manage_url_uses_offer_uuid(self):
        offer = Offer()
        self.assertEqual(
            reverse(
                "offers:offer-manage",
                kwargs={
                    "business_slug": "royal-store",
                    "offer_id": offer.pk,
                },
            ),
            f"/api/businesses/mine/royal-store/offers/{offer.pk}/",
        )

    def test_create_requires_title_only(self):
        serializer = OfferWriteSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), {"title"})

    def test_rejects_expiry_before_start(self):
        starts_at = timezone.now()
        serializer = OfferWriteSerializer(
            data={
                "title": "Weekend deal",
                "starts_at": starts_at,
                "expires_at": starts_at - timedelta(hours=1),
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("expires_at", serializer.errors)


class SeedDummyOffersCommandTests(SimpleTestCase):
    def test_rejects_count_outside_supported_range(self):
        for count in (49, 61):
            with self.subTest(count=count), self.assertRaisesMessage(
                CommandError, "--count must be between 50 and 60."
            ):
                validate_offer_count(count)
