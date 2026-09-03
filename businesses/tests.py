from contextlib import nullcontext
from datetime import date, datetime, time
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock, patch

from django import forms
from django.contrib import admin
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import SimpleTestCase
from django.http import QueryDict
from django.urls import resolve, reverse
from PIL import Image
from rest_framework.test import APIRequestFactory, force_authenticate

from businesses.models import Business, BusinessCategoryAssignment, BusinessGalleryImage, BusinessHoliday, BusinessHour
from businesses.admin import BusinessAdmin, BusinessAdminForm
from businesses.serializers import BusinessDetailSerializer, BusinessGalleryImageWriteSerializer, BusinessGallerySyncSerializer, BusinessHoursUpdateSerializer, BusinessListQuerySerializer, BusinessListSerializer, BusinessLocationSerializer, BusinessUpdateSerializer, CatalogProductSerializer, CategoryFilterSerializer, OwnerBusinessDetailSerializer
from businesses.services import BUSINESS_HOUR_PATTERNS, get_business_hours_status, normalize_business, paginate_businesses, prepare_business_for_save, save_business
from businesses.management.commands.seed_dummy_businesses import BUSINESS_NAMES, CENTER_LATITUDE, CENTER_LONGITUDE, RADIUS_KM
from businesses.validators import validate_alternate_numbers, validate_established_year, validate_social_urls
from businesses.views import business_detail, business_hours_update, my_business_list, owner_business_detail
from categories.models import BusinessCategory
from catalogs.models import Catalog, CatalogCategory
from locations.models import City, State
from offers.models import Offer


class BusinessModelTests(SimpleTestCase):
    def test_supported_fields_default_to_independent_lists(self):
        first = Business()
        second = Business()

        first.supported_sections.append("doctors")

        self.assertEqual(first.supported_sections, ["doctors"])
        self.assertEqual(second.supported_sections, [])
        self.assertEqual(second.supported_quick_info, [])

    def test_rejects_unsupported_section_and_quick_info_values(self):
        business = Business(
            supported_sections=["doctors", "unknown"],
            supported_quick_info=["parking", "unknown"],
        )

        with self.assertRaises(ValidationError) as context:
            business._validate_supported_options()

        self.assertIn("supported_sections", context.exception.message_dict)
        self.assertIn("supported_quick_info", context.exception.message_dict)

    def test_supported_quick_info_exposes_all_allowed_values(self):
        self.assertEqual(
            set(Business.SupportedQuickInfo.values),
            {
                "experience",
                "price_range",
                "service_area",
                "languages",
                "home_service",
                "home_delivery",
                "payment_methods",
                "emi_available",
                "amenities",
                "ambience",
                "insurance_accepted",
                "warranty_available",
                "return_available",
                "exchange_available",
                "delivery",
                "parking",
            },
        )

    def test_rejects_non_list_and_duplicate_supported_values(self):
        business = Business(
            supported_sections="doctors",
            supported_quick_info=["parking", "parking"],
        )

        with self.assertRaises(ValidationError) as context:
            business._validate_supported_options()

        self.assertIn("supported_sections", context.exception.message_dict)
        self.assertIn("supported_quick_info", context.exception.message_dict)

    def test_categories_use_ordered_through_model(self):
        field = Business._meta.get_field("categories")
        self.assertIs(field.remote_field.through, BusinessCategoryAssignment)
        self.assertEqual(
            BusinessCategoryAssignment._meta.ordering,
            ("sort_order", "id"),
        )

    def test_normalizes_public_fields(self):
        business = Business(name="  Cafe  ", address="  Main Road  ", email=" OWNER@EXAMPLE.COM ", phone=" +919876543210 ")
        normalize_business(business)
        self.assertEqual((business.name, business.address, business.email, business.phone), ("Cafe", "Main Road", "owner@example.com", "+919876543210"))

    def test_rejects_whitespace_only_required_fields(self):
        with self.assertRaises(ValidationError):
            normalize_business(Business(name="  ", address=" "))

    def test_generates_postgis_point_from_complete_coordinates(self):
        business = Business(name="Cafe", address="Main Road", latitude=22.5726, longitude=88.3639)
        prepare_business_for_save(business)
        self.assertEqual((business.location.x, business.location.y), (88.3639, 22.5726))

    def test_exposes_expected_lifecycle_states(self):
        self.assertEqual(set(Business.Status.values), {"draft", "pending", "published", "rejected", "suspended"})

    def test_retries_a_generated_slug_after_a_concurrent_collision(self):
        business = Business(name="Cafe", address="Main Road")
        callback = Mock(side_effect=[IntegrityError(), "saved"])
        with patch("businesses.services.generate_unique_slug", side_effect=["cafe", "cafe-2"]), patch("businesses.services.transaction.atomic", return_value=nullcontext()), patch.object(Business.objects, "using") as manager:
            manager.return_value.filter.return_value.exclude.return_value.exists.return_value = True
            self.assertEqual(save_business(business, callback, (), {}), "saved")
        self.assertEqual(business.slug, "cafe-2")
        self.assertEqual(callback.call_count, 2)

    def test_coordinate_update_also_updates_location(self):
        business = Business(name="Cafe", slug="cafe", address="Main Road", latitude=22.5726, longitude=88.3639)
        callback = Mock(return_value="saved")
        with patch("businesses.services.transaction.atomic", return_value=nullcontext()):
            save_business(business, callback, (), {"update_fields": {"latitude", "longitude"}})
        self.assertIn("location", callback.call_args.kwargs["update_fields"])

    def test_json_and_established_year_validators(self):
        validate_alternate_numbers(["+919876543210"])
        validate_social_urls({"instagram": "https://instagram.com/example"})
        validate_established_year(date.today().year)
        for validator, value in ((validate_alternate_numbers, "not-a-list"), (validate_social_urls, []), (validate_established_year, date.today().year + 1)):
            with self.subTest(validator=validator.__name__), self.assertRaises(ValidationError):
                validator(value)


class BusinessHourModelTests(SimpleTestCase):
    def test_stores_same_slot_days_in_one_row(self):
        hours = BusinessHour(business=Business(name="Cafe"), days=[4, 0, 2, 1, 3], opens_at=time(9), closes_at=time(17))
        hours.clean()
        self.assertEqual(hours.days, [0, 1, 2, 3, 4])
        self.assertEqual(hours.day_names, ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])

    def test_rejects_invalid_days_and_time_window(self):
        for days in ([], [-1], [7], [1, 1], [True]):
            with self.subTest(days=days), self.assertRaises(ValidationError):
                BusinessHour(business=Business(name="Cafe"), days=days, opens_at=time(9), closes_at=time(17)).clean()
        with self.assertRaises(ValidationError):
            BusinessHour(business=Business(name="Cafe"), days=[1], opens_at=time(17), closes_at=time(9)).clean()


class BusinessHoursUpdateSerializerTests(SimpleTestCase):
    def test_normalizes_valid_schedule(self):
        serializer = BusinessHoursUpdateSerializer(
            data={
                "business_hours": [
                    {"days": [4, 0, 2], "opens_at": "09:00", "closes_at": "17:00"},
                    {"days": [0], "opens_at": "18:00", "closes_at": "21:00"},
                ]
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["business_hours"][0]["days"], [0, 2, 4])

    def test_rejects_invalid_or_overlapping_schedule(self):
        invalid_payloads = (
            {"business_hours": [{"days": [0, 0], "opens_at": "09:00", "closes_at": "17:00"}]},
            {"business_hours": [{"days": [7], "opens_at": "09:00", "closes_at": "17:00"}]},
            {"business_hours": [{"days": [0], "opens_at": "17:00", "closes_at": "09:00"}]},
            {
                "business_hours": [
                    {"days": [0], "opens_at": "09:00", "closes_at": "17:00"},
                    {"days": [0, 1], "opens_at": "16:00", "closes_at": "20:00"},
                ]
            },
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                serializer = BusinessHoursUpdateSerializer(data=payload)
                self.assertFalse(serializer.is_valid())

    def test_seed_patterns_are_valid_and_non_overlapping(self):
        for pattern in BUSINESS_HOUR_PATTERNS:
            occupied = {}
            for days, opens_at, closes_at in pattern:
                self.assertTrue(days)
                self.assertLess(opens_at, closes_at)
                for day in days:
                    slots = occupied.setdefault(day, [])
                    self.assertFalse(any(opens_at < other_close and closes_at > other_open for other_open, other_close in slots))
                    slots.append((opens_at, closes_at))


class BusinessHoursStatusTests(SimpleTestCase):
    def setUp(self):
        self.hours = [BusinessHour(days=[0, 1, 2, 3, 4], opens_at=time(10), closes_at=time(23))]

    def test_reports_open_and_next_closing_time(self):
        result = get_business_hours_status(self.hours, now=datetime.fromisoformat("2026-08-17T18:00:00+05:30"))
        self.assertEqual(result, {"status": "open", "next_closing_time": None, "remark": "Open until 11 PM"})

    def test_reports_closing_soon_with_less_than_one_hour_remaining(self):
        result = get_business_hours_status(self.hours, now=datetime.fromisoformat("2026-08-17T22:01:00+05:30"))
        self.assertEqual(result["status"], "closing_soon")
        self.assertEqual(result["next_closing_time"], "2026-08-17T23:00:00+05:30")

    def test_exactly_one_hour_remaining_is_open(self):
        result = get_business_hours_status(self.hours, now=datetime.fromisoformat("2026-08-17T22:00:00+05:30"))
        self.assertEqual(result["status"], "open")
        self.assertIsNone(result["next_closing_time"])

    def test_reports_next_opening_for_closed_business(self):
        result = get_business_hours_status(self.hours, now=datetime.fromisoformat("2026-08-16T12:00:00+05:30"))
        self.assertEqual(result, {"status": "closed", "next_closing_time": None, "remark": "Opens tomorrow at 10 AM"})

    def test_reports_later_same_day_opening(self):
        result = get_business_hours_status(self.hours, now=datetime.fromisoformat("2026-08-17T09:00:00+05:30"))
        self.assertEqual(result["remark"], "Opens today at 10 AM")

    def test_reports_unavailable_hours(self):
        self.assertEqual(get_business_hours_status([], now=datetime.fromisoformat("2026-08-17T09:00:00+05:30")), {"status": "closed", "next_closing_time": None, "remark": "Hours unavailable"})

    def test_holiday_takes_precedence_over_hours(self):
        holiday = BusinessHoliday(start_date=date(2026, 8, 17), end_date=date(2026, 8, 18), reason="Festival")
        result = get_business_hours_status(
            self.hours,
            holidays=[holiday],
            now=datetime.fromisoformat("2026-08-17T12:00:00+05:30"),
        )
        self.assertEqual(
            result,
            {
                "status": "closed",
                "next_closing_time": None,
                "remark": "Closed for holiday: Festival",
            },
        )

    def test_future_holiday_is_skipped_when_finding_next_opening(self):
        holiday = BusinessHoliday(start_date=date(2026, 8, 17), end_date=date(2026, 8, 18))
        result = get_business_hours_status(
            self.hours,
            holidays=[holiday],
            now=datetime.fromisoformat("2026-08-16T12:00:00+05:30"),
        )
        self.assertEqual(result["remark"], "Opens Wednesday at 10 AM")


class BusinessVisibilityTests(SimpleTestCase):
    def test_hidden_full_address_keeps_only_general_location(self):
        business = Business(address="12 Main Road", landmark="Clock Tower", locality="Central", postal_code="700001", latitude=22.5, longitude=88.3, display_full_address=False)
        serializer = BusinessLocationSerializer()
        self.assertIsNone(serializer.get_address(business))
        self.assertIsNone(serializer.get_landmark(business))
        self.assertIsNone(serializer.get_postal_code(business))
        self.assertEqual(serializer.get_coordinates(business), {"latitude": None, "longitude": None, "distance_km": None})

    def test_hidden_business_status_returns_null(self):
        business = Business(display_business_status=False)
        serializer = BusinessListSerializer()
        self.assertIsNone(serializer.get_business_hours_status(business))


class BusinessAdminTests(SimpleTestCase):
    def test_supported_fields_use_checkbox_widgets(self):
        self.assertIsInstance(
            BusinessAdminForm.base_fields["supported_sections"].widget,
            forms.CheckboxSelectMultiple,
        )
        self.assertIsInstance(
            BusinessAdminForm.base_fields["supported_quick_info"].widget,
            forms.CheckboxSelectMultiple,
        )

    def test_uses_structured_admin(self):
        model_admin = admin.site._registry[Business]
        self.assertIsInstance(model_admin, BusinessAdmin)
        self.assertNotIn("Services", [title for title, _ in model_admin.fieldsets])
        self.assertEqual(model_admin.form, BusinessAdminForm)

    def test_json_fields_have_guided_textareas(self):
        self.assertEqual(BusinessAdminForm.base_fields["alt_numbers"].widget.attrs["rows"], 3)
        self.assertEqual(BusinessAdminForm.base_fields["social_urls"].widget.attrs["rows"], 4)


class BusinessSeedTests(SimpleTestCase):
    def test_command_defines_100_businesses_near_requested_center(self):
        self.assertEqual(len(BUSINESS_NAMES), 100)
        self.assertEqual((CENTER_LATITUDE, CENTER_LONGITUDE), (22.467324, 88.403916))
        self.assertEqual(RADIUS_KM, 10.0)


class BusinessListAPITests(SimpleTestCase):
    def test_response_includes_publication_status_and_last_updated(self):
        serializer = BusinessListSerializer()
        self.assertEqual(serializer.fields["publication_status"].source, "status")
        self.assertEqual(serializer.fields["last_updated"].source, "updated_at")

    def test_url_and_filter_defaults(self):
        self.assertEqual(reverse("businesses:business-list"), "/api/businesses/")
        query = BusinessListQuerySerializer(data={})
        self.assertTrue(query.is_valid())
        self.assertEqual((query.validated_data["page"], query.validated_data["page_size"], query.validated_data["sort_by"]), (1, 20, "name"))

    def test_absent_boolean_query_parameters_do_not_filter_results(self):
        query = BusinessListQuerySerializer(data=QueryDict(""))
        self.assertTrue(query.is_valid(), query.errors)
        self.assertNotIn("is_active", query.validated_data)
        self.assertNotIn("is_verified", query.validated_data)
        self.assertNotIn("open_now", query.validated_data)

    def test_open_now_accepts_explicit_boolean_values(self):
        for raw_value, expected in (("true", True), ("false", False)):
            with self.subTest(raw_value=raw_value):
                query = BusinessListQuerySerializer(data=QueryDict(f"open_now={raw_value}"))
                self.assertTrue(query.is_valid(), query.errors)
                self.assertIs(query.validated_data["open_now"], expected)

    def test_rejects_invalid_filters(self):
        query = BusinessListQuerySerializer(data={"page_size": 101, "sort_by": "invalid", "publication_status": "deleted"})
        self.assertFalse(query.is_valid())
        self.assertEqual(set(query.errors), {"page_size", "sort_by", "publication_status"})

    def test_category_and_city_are_slugs_and_coordinates_are_paired(self):
        query = BusinessListQuerySerializer(data={"category": "grocery-stores", "city": "kolkata", "lat": 22.5726, "lng": 88.3639})
        self.assertTrue(query.is_valid(), query.errors)
        self.assertEqual((query.validated_data["category"], query.validated_data["city"]), ("grocery-stores", "kolkata"))
        invalid = BusinessListQuerySerializer(data={"lat": 22.5726})
        self.assertFalse(invalid.is_valid())
        self.assertIn("location", invalid.errors)

    def test_pagination_contains_metadata_without_urls(self):
        records, pagination = paginate_businesses(list(range(25)), page=2, page_size=10)
        self.assertEqual(list(records), list(range(10, 20)))
        self.assertEqual(pagination, {"page": 2, "page_size": 10, "total_pages": 3, "total_items": 25, "has_next": True, "has_previous": True})
        self.assertNotIn("next", pagination)
        self.assertNotIn("previous", pagination)

    def test_category_filter_summary_fields(self):
        category = CategoryFilterSerializer(BusinessCategory(name="Grocery Store", display_name="Grocery", label="Grocery Stores"))
        self.assertEqual(category.data, {"name": "Grocery Store", "display_name": "Grocery", "label": "Grocery Stores"})


class MyBusinessListAPITests(SimpleTestCase):
    def test_url(self):
        self.assertEqual(
            reverse("businesses:my-business-list"),
            "/api/businesses/mine/",
        )

    def test_url_resolves_to_owner_list_instead_of_public_slug_detail(self):
        self.assertIs(resolve("/api/businesses/mine/").func, my_business_list)

    def test_requires_authentication(self):
        response = self.client.get(reverse("businesses:my-business-list"))
        self.assertEqual(response.status_code, 401)

    @patch("businesses.views.list_businesses", return_value=[])
    def test_uses_authenticated_user_as_owner_filter(self, list_businesses_mock):
        owner_id = uuid4()
        request = APIRequestFactory().get("/api/businesses/mine/")
        force_authenticate(
            request,
            user=SimpleNamespace(
                pk=owner_id, is_active=True, is_authenticated=True
            ),
        )

        response = my_business_list(request)

        self.assertEqual(response.status_code, 200)
        filters = list_businesses_mock.call_args.args[0]
        self.assertEqual(filters["owner_id"], owner_id)


class BusinessGalleryAPITests(SimpleTestCase):
    def test_gallery_urls(self):
        self.assertEqual(
            reverse("businesses:business-gallery", kwargs={"slug": "cafe"}),
            "/api/businesses/mine/cafe/gallery/",
        )

    def test_gallery_sync_accepts_empty_final_gallery(self):
        serializer = BusinessGallerySyncSerializer(data={})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["existing_ids"], [])
        self.assertEqual(serializer.validated_data["images"], [])

    def test_gallery_sync_rejects_duplicate_existing_ids(self):
        image_id = uuid4()
        serializer = BusinessGallerySyncSerializer(
            data={"existing_ids": [image_id, image_id]}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("existing_ids", serializer.errors)

    def test_upload_requires_authentication(self):
        response = self.client.post(
            reverse("businesses:business-gallery", kwargs={"slug": "cafe"}),
            data={},
        )
        self.assertEqual(response.status_code, 401)

    def test_gallery_is_returned_as_urls_inside_media(self):
        business = Business()
        business._prefetched_gallery_images = [
            BusinessGalleryImage(image="businesses/gallery/example.webp")
        ]

        media = BusinessDetailSerializer().get_media(business)

        self.assertIsNone(media["thumbnail"])
        self.assertEqual(len(media["gallery"]), 1)
        self.assertTrue(
            media["gallery"][0].endswith(
                "/media/businesses/gallery/example.webp"
            )
        )
        self.assertNotIn("gallery", BusinessDetailSerializer.Meta.fields)

    @patch("django.db.models.Model.save", return_value=None)
    def test_gallery_upload_is_compressed_and_gets_unique_name(self, model_save):
        content = BytesIO()
        Image.new("RGB", (2400, 1200), "navy").save(content, format="PNG")
        upload = SimpleUploadedFile(
            "gallery.png", content.getvalue(), content_type="image/png"
        )
        gallery_image = BusinessGalleryImage(business=Business(), image=upload)

        gallery_image.save()

        self.assertRegex(gallery_image.image.name, r"^[0-9a-f]{32}\.webp$")
        with Image.open(gallery_image.image) as result:
            self.assertEqual(result.size, (2400, 1200))
            self.assertEqual(result.format, "WEBP")
        model_save.assert_called_once()


class BusinessDetailAPITests(SimpleTestCase):
    def test_detail_includes_prefetched_offers(self):
        business = Business()
        business._prefetched_offers = [
            Offer(
                title="Weekend Deal",
                description="Save this weekend.",
                is_active=True,
                sort_order=1,
                terms=["Subject to availability"],
            )
        ]

        data = BusinessDetailSerializer().get_offers(business)

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "Weekend Deal")
        self.assertEqual(data[0]["status"], "active")
        self.assertIn("offers", BusinessDetailSerializer.Meta.fields)
        self.assertIn("offers", OwnerBusinessDetailSerializer.Meta.fields)

    def test_supported_fields_are_returned_as_string_arrays(self):
        business = Business(
            supported_sections=["doctors", "educators"],
            supported_quick_info=["delivery", "parking"],
        )

        data = BusinessListSerializer(business).data

        self.assertEqual(data["supported_sections"], ["doctors", "educators"])
        self.assertEqual(data["supported_quick_info"], ["delivery", "parking"])

    def test_detail_url_uses_slug(self):
        self.assertEqual(reverse("businesses:business-detail", kwargs={"slug": "royal-grocery-store"}), "/api/businesses/royal-grocery-store/")

    def test_detail_keeps_list_groups_and_adds_description(self):
        fields = set(BusinessDetailSerializer.Meta.fields)
        self.assertTrue({"media", "location", "contact", "publication", "seo", "metadata"}.issubset(fields))
        self.assertIn("description", fields)
        self.assertIn("features", fields)
        self.assertIn("business_hours", fields)
        self.assertIn("product", fields)
        self.assertNotIn("products", fields)

    def test_detail_product_groups_categories_and_limits_items_to_ten(self):
        business = Business()
        business._prefetched_catalog_products = [
            Catalog(
                name=f"Product {index}",
                public_id=f"p{index:07d}",
                slug=f"product-{index}-p{index:07d}",
            )
            for index in range(11)
        ]
        for product in business._prefetched_catalog_products:
            product._prefetched_primary_images = []
        business._prefetched_catalog_products[0].variants = [
            {"name": "Size", "options": ["S", "M", "L"]}
        ]
        business._prefetched_catalog_products[0].specifications = {
            "material": "Cotton"
        }
        business._prefetched_catalog_products[0].is_featured = True
        business._prefetched_product_categories = [
            CatalogCategory(
                id=4,
                name="Clothing",
                label="Apparel",
                slug="clothing",
                type="product",
            ),
            CatalogCategory(
                id=5,
                name="Hidden",
                slug="hidden",
                type="product",
                is_display=False,
            ),
        ]

        product = BusinessDetailSerializer().get_product(business)

        self.assertEqual(len(product["items"]), 10)
        self.assertEqual(
            product["items"][0]["id"],
            str(business._prefetched_catalog_products[0].id),
        )
        self.assertEqual(product["items"][0]["public_id"], "p0000000")
        self.assertEqual(product["items"][-1]["public_id"], "p0000009")
        self.assertEqual(
            product["items"][0]["variants"],
            [{"name": "Size", "options": ["S", "M", "L"]}],
        )
        self.assertEqual(
            product["items"][0]["specifications"],
            {"material": "Cotton"},
        )
        self.assertTrue(product["items"][0]["is_featured"])
        self.assertEqual(
            product["categories"],
            [
                {
                    "id": 4,
                    "name": "Clothing",
                    "label": "Apparel",
                    "slug": "clothing",
                    "type": "product",
                    "display_name": "Apparel",
                    "image": None,
                }
            ],
        )

    def test_display_business_status_is_in_list_public_and_owner_contracts(self):
        self.assertIn("display_business_status", BusinessListSerializer.Meta.fields)
        self.assertIn("display_business_status", BusinessDetailSerializer.Meta.fields)
        self.assertIn("display_business_status", OwnerBusinessDetailSerializer.Meta.fields)

    def test_features_are_returned_by_public_and_owner_details(self):
        business = Business()
        business.profile = SimpleNamespace(features={"parking": True})

        public_field = BusinessDetailSerializer().fields["features"]
        owner_field = OwnerBusinessDetailSerializer().fields["features"]

        self.assertEqual(public_field.get_attribute(business), {"parking": True})
        self.assertEqual(owner_field.get_attribute(business), {"parking": True})

        business = Business(display_business_status=False)
        self.assertFalse(
            BusinessListSerializer().fields[
                "display_business_status"
            ].to_representation(business.display_business_status)
        )

    def test_is_active_is_in_list_public_and_owner_detail_contracts(self):
        self.assertIn("is_active", BusinessListSerializer.Meta.fields)
        self.assertIn("is_active", BusinessDetailSerializer.Meta.fields)
        self.assertIn("is_active", OwnerBusinessDetailSerializer.Meta.fields)

        business = Business(is_active=True)
        self.assertTrue(BusinessListSerializer(business).data["is_active"])

    def test_category_summary_includes_id(self):
        category = BusinessCategory(
            id=7,
            name="Medical Store",
            display_name="Medical Stores",
            slug="medical-stores",
        )
        business = Business()
        business._prefetched_objects_cache = {"categories": [category]}

        data = BusinessDetailSerializer().fields["categories"].to_representation(
            [category]
        )

        self.assertEqual(
            data,
            [
                {
                    "id": 7,
                    "name": "Medical Store",
                    "slug": "medical-stores",
                    "display_name": "Medical Stores",
                }
            ],
        )

    def test_public_location_nests_state_in_city(self):
        state = State(id=4, name="West Bengal")
        city = City(id=7, name="Kolkata", state=state)
        business = Business(city=city)

        data = BusinessDetailSerializer().fields["location"].to_representation(
            business
        )

        self.assertEqual(
            data["city"],
            {
                "id": 7,
                "name": "Kolkata",
                "state_id": 4,
                "state": "West Bengal",
            },
        )
        self.assertNotIn("state", data)

    def test_business_hours_are_grouped_into_all_weekdays(self):
        business = Business()
        business._prefetched_business_hours = [
            BusinessHour(days=[0, 2], opens_at=time(9), closes_at=time(13)),
            BusinessHour(days=[0], opens_at=time(16), closes_at=time(20)),
        ]
        schedule = BusinessDetailSerializer().get_business_hours(business)
        self.assertEqual(list(schedule), ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])
        self.assertEqual(schedule["monday"], [{"opens_at": time(9), "closes_at": time(13)}, {"opens_at": time(16), "closes_at": time(20)}])
        self.assertEqual(schedule["wednesday"], [{"opens_at": time(9), "closes_at": time(13)}])
        self.assertEqual(schedule["sunday"], [])

    def test_today_holiday_clears_only_response_slots(self):
        business = Business()
        recurring = BusinessHour(days=[0], opens_at=time(9), closes_at=time(20))
        business._prefetched_business_hours = [recurring]
        business._prefetched_business_holidays = [
            BusinessHoliday(start_date=date(2026, 8, 17), end_date=date(2026, 8, 18), reason="Festival")
        ]
        serializer = BusinessDetailSerializer(
            context={"now": datetime.fromisoformat("2026-08-17T12:00:00+05:30")}
        )

        schedule = serializer.get_business_hours(business)

        self.assertEqual(schedule["monday"], [])
        self.assertEqual(recurring.opens_at, time(9))

    @patch("businesses.views.get_public_business_by_slug", return_value=None)
    def test_unknown_slug_returns_404(self, get_business):
        response = self.client.get(reverse("businesses:business-detail", kwargs={"slug": "missing-business"}))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Business not found."})
        get_business.assert_called_once()
        self.assertEqual(get_business.call_args.args, ("missing-business",))
        self.assertIn("now", get_business.call_args.kwargs)


class BusinessUpdateAPITests(SimpleTestCase):
    def test_public_endpoint_is_read_only_and_owner_endpoint_supports_patch(self):
        self.assertNotIn("patch", business_detail.cls.http_method_names)
        self.assertIn("patch", owner_business_detail.cls.http_method_names)
        self.assertNotIn("put", owner_business_detail.cls.http_method_names)

    def test_owner_detail_uses_separate_url(self):
        self.assertEqual(
            reverse(
                "businesses:owner-business-detail",
                kwargs={"slug": "royal-grocery-store"},
            ),
            "/api/businesses/mine/royal-grocery-store/",
        )

    def test_patch_requires_authentication(self):
        response = self.client.patch(
            reverse(
                "businesses:owner-business-detail",
                kwargs={"slug": "royal-grocery-store"},
            ),
            data={},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_owner_detail_returns_unmasked_location_and_visibility(self):
        state = State(id=4, name="West Bengal")
        city = City(id=7, name="Kolkata", state=state)
        business = Business(
            id=uuid4(),
            owner_id=uuid4(),
            name="Private Address Business",
            address="12 Hidden Lane",
            landmark="Near Park",
            locality="Salt Lake",
            city=city,
            postal_code="700091",
            latitude=Decimal("22.586700000"),
            longitude=Decimal("88.417100000"),
            display_full_address=False,
            display_business_status=False,
        )

        data = OwnerBusinessDetailSerializer().fields["location"].to_representation(
            business
        )

        self.assertEqual(data["address"], "12 Hidden Lane")
        self.assertEqual(data["city"]["id"], 7)
        self.assertEqual(data["city"]["state_id"], 4)
        self.assertEqual(data["city"]["state"], "West Bengal")
        self.assertFalse(data["display_full_address"])
        self.assertEqual(data["coordinates"]["latitude"], Decimal("22.586700000"))

    def test_update_fields_allow_enabled_but_exclude_other_server_controlled_state(self):
        fields = set(BusinessUpdateSerializer.Meta.fields)
        self.assertIn("is_active", fields)
        self.assertFalse({"owner", "slug", "status", "is_verified", "published_at", "created_at", "updated_at"} & fields)

    def test_is_active_accepts_boolean_patch_value(self):
        serializer = BusinessUpdateSerializer(data={"is_active": True}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIs(serializer.validated_data["is_active"], True)

    def test_update_fields_exclude_legacy_profile_services(self):
        self.assertNotIn("services", BusinessUpdateSerializer.Meta.fields)

    def test_features_accepts_json_patch_value(self):
        serializer = BusinessUpdateSerializer(
            data={"features": {"parking": True, "payment_methods": ["cash", "upi"]}},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["profile"]["features"],
            {"parking": True, "payment_methods": ["cash", "upi"]},
        )

    def test_supported_fields_accept_string_array_patch_values(self):
        serializer = BusinessUpdateSerializer(
            data={
                "supported_sections": ["doctors", "property"],
                "supported_quick_info": ["experience", "price_range"],
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["supported_sections"],
            ["doctors", "property"],
        )
        self.assertEqual(
            serializer.validated_data["supported_quick_info"],
            ["experience", "price_range"],
        )

    def test_supported_fields_reject_unknown_and_duplicate_values(self):
        serializer = BusinessUpdateSerializer(
            data={
                "supported_sections": ["doctors", "unknown"],
                "supported_quick_info": ["parking", "parking"],
            },
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("supported_sections", serializer.errors)
        self.assertIn("supported_quick_info", serializer.errors)


class BusinessHoursUpdateAPITests(SimpleTestCase):
    def test_url_and_method(self):
        self.assertEqual(
            reverse(
                "businesses:business-hours-update",
                kwargs={"slug": "royal-grocery-store"},
            ),
            "/api/businesses/royal-grocery-store/hours/",
        )

    def test_endpoint_requires_authentication(self):
        response = self.client.patch(
            reverse(
                "businesses:business-hours-update",
                kwargs={"slug": "royal-grocery-store"},
            ),
            data={"business_hours": []},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    @patch("businesses.views.get_business_for_update")
    def test_rejects_user_who_does_not_own_business(self, get_business):
        get_business.return_value = Business(owner_id=uuid4())
        request = APIRequestFactory().patch(
            "/api/businesses/cafe/hours/",
            {"business_hours": []},
            format="json",
        )
        force_authenticate(
            request,
            user=SimpleNamespace(pk=uuid4(), is_active=True, is_authenticated=True),
        )

        response = business_hours_update(request, slug="cafe")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.data,
            {"detail": "You can only update hours for your own business."},
        )


class BusinessHolidayAPITests(SimpleTestCase):
    def test_create_and_detail_urls(self):
        holiday_id = uuid4()
        self.assertEqual(
            reverse("businesses:business-holiday-create", kwargs={"slug": "cafe"}),
            "/api/businesses/cafe/holidays/",
        )
        self.assertEqual(
            reverse(
                "businesses:business-holiday-detail",
                kwargs={"slug": "cafe", "holiday_id": holiday_id},
            ),
            f"/api/businesses/cafe/holidays/{holiday_id}/",
        )
