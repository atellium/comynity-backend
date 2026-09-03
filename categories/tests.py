from django.contrib import admin
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from categories import views
from categories.admin import BusinessCategoryAdmin, ProductCategoryAdmin
from categories.models import BusinessCategory, ProductCategory


class CategoryImageCompressionTests(SimpleTestCase):
    @patch("core.models.AutoSlugModel.save", return_value=None)
    @patch("core.image_service.compress_image")
    def test_new_business_category_images_are_compressed(
        self, compress_image, model_save
    ):
        compressed = SimpleUploadedFile(
            "compressed.webp", b"compressed", content_type="image/webp"
        )
        compress_image.return_value = compressed

        upload = SimpleUploadedFile(
            "category.png", b"original", content_type="image/png"
        )
        category = BusinessCategory(name="Category", image=upload)

        category.save(update_fields={"name"})

        compress_image.assert_called_once()
        self.assertEqual(compress_image.call_args.args[0].name, "category.png")
        self.assertEqual(category.image.name, "compressed.webp")
        self.assertEqual(
            model_save.call_args.kwargs["update_fields"],
            {"name", "image"},
        )


class BusinessCategoryAdminTests(SimpleTestCase):
    def test_model_uses_custom_admin(self):
        self.assertIsInstance(
            admin.site._registry[BusinessCategory],
            BusinessCategoryAdmin,
        )

    def test_admin_does_not_reference_removed_fields(self):
        model_admin = admin.site._registry[BusinessCategory]
        self.assertNotIn("parent", model_admin.list_display)
        self.assertNotIn("is_hidden", model_admin.list_display)
        self.assertNotIn("is_popular", model_admin.list_display)

    def test_slug_is_prepopulated_from_label(self):
        model_admin = admin.site._registry[BusinessCategory]
        self.assertEqual(model_admin.prepopulated_fields, {"slug": ("label",)})

        url_fields = next(
            options["fields"]
            for title, options in model_admin.fieldsets
            if title == "URL"
        )
        self.assertEqual(url_fields, ("label", "slug"))

    def test_admin_supports_category_state_fields(self):
        model_admin = admin.site._registry[BusinessCategory]
        for field in ("is_active", "is_featured"):
            with self.subTest(field=field):
                self.assertIn(field, model_admin.list_filter)
                self.assertIn(field, model_admin.list_editable)


class ProductCategoryAdminTests(SimpleTestCase):
    def test_model_uses_custom_admin(self):
        self.assertIsInstance(
            admin.site._registry[ProductCategory],
            ProductCategoryAdmin,
        )

    def test_admin_supports_hierarchy_and_category_state_fields(self):
        model_admin = admin.site._registry[ProductCategory]
        self.assertIn("parent", model_admin.list_display)
        self.assertIn("parent", model_admin.list_filter)
        for field in ("is_active", "is_featured"):
            with self.subTest(field=field):
                self.assertIn(field, model_admin.list_filter)
                self.assertIn(field, model_admin.list_editable)

    def test_slug_is_prepopulated_from_label(self):
        model_admin = admin.site._registry[ProductCategory]
        self.assertEqual(model_admin.prepopulated_fields, {"slug": ("label",)})


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class SearchCategoriesEndpointTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.visible = BusinessCategory.objects.create(
            name="Restaurant",
            label="Restaurants",
            slug="restaurants",
            aliases="food,dining",
            sort_order=1,
        )
        cls.inactive = BusinessCategory.objects.create(
            name="Closed Venue",
            label="Closed Venues",
            slug="closed-venues",
            sort_order=2,
            is_active=False,
        )
    def setUp(self):
        cache.clear()

    def test_returns_only_active_categories_with_public_fields(self):
        response = self.client.get(reverse("categories:search-categories"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": self.visible.id,
                    "name": "Restaurant",
                    "display_name": "",
                    "label": "Restaurants",
                    "slug": "restaurants",
                    "aliases": "food,dining",
                    "image": None,
                },
            ],
        )

    def test_cache_is_refreshed_after_category_update(self):
        url = reverse("categories:search-categories")
        self.client.get(url)
        self.visible.label = "Food and restaurants"
        with self.captureOnCommitCallbacks(execute=True):
            self.visible.save(update_fields=("label",))

        response = self.client.get(url)

        self.assertEqual(response.data[0]["label"], "Food and restaurants")

    def test_cache_is_refreshed_after_category_create(self):
        url = reverse("categories:search-categories")
        initial_response = self.client.get(url)

        with self.captureOnCommitCallbacks(execute=True):
            category = BusinessCategory.objects.create(
                name="Bakery",
                label="Bakeries",
                slug="bakeries",
                sort_order=3,
            )

        response = self.client.get(url)

        self.assertEqual(len(response.data), len(initial_response.data) + 1)
        self.assertEqual(response.data[-1]["id"], category.id)
        self.assertEqual(response.data[-1]["label"], "Bakeries")


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class CategoryListEndpointTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.featured = BusinessCategory.objects.create(
            name="Food",
            label="Food",
            slug="food",
            sort_order=1,
            is_featured=True,
        )
        cls.restaurant = BusinessCategory.objects.create(
            name="Restaurant",
            display_name="Restaurants",
            label="Places to eat",
            slug="restaurants",
            aliases="food,dining",
            sort_order=2,
        )
        BusinessCategory.objects.create(
            name="Inactive cafe",
            label="Inactive cafe",
            slug="inactive-cafe",
            is_active=False,
            sort_order=3,
        )

    def setUp(self):
        cache.clear()

    def test_lists_categories_with_pagination(self):
        response = self.client.get(
            reverse("categories:business-category-list"), {"page_size": 2}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            reverse("categories:business-category-list"),
            "/api/categories/business/",
        )
        self.assertEqual(response.data["pagination"]["total_items"], 3)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIn("image", response.data["results"][0])
        self.assertIn("created_at", response.data["results"][0])

    def test_supports_search_state_and_sort_filters(self):
        response = self.client.get(
            reverse("categories:business-category-list"),
            {
                "search": "dining",
                "is_active": "true",
                "is_featured": "false",
                "sort_by": "name",
                "sort_order": "desc",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [category["slug"] for category in response.data["results"]],
            ["restaurants"],
        )

    def test_rejects_invalid_page_size(self):
        response = self.client.get(
            reverse("categories:business-category-list"),
            {"page_size": 101},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_supports_sort_field_and_descending_order(self):
        response = self.client.get(
            reverse("categories:business-category-list"),
            {"sort_by": "name", "sort_order": "desc"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [category["name"] for category in response.data["results"]],
            ["Restaurant", "Inactive cafe", "Food"],
        )

    def test_rejects_invalid_sort_parameters(self):
        response = self.client.get(
            reverse("categories:business-category-list"),
            {"sort_by": "unknown", "sort_order": "sideways"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_featured_list_response_is_cached(self):
        url = reverse("categories:business-category-list")
        with patch(
            "categories.views.list_business_categories",
            wraps=views.list_business_categories,
        ) as list_categories:
            first = self.client.get(url, {"is_featured": "true"})
            second = self.client.get(url, {"is_featured": "true"})

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data, first.data)
        self.assertEqual(list_categories.call_count, 1)

    def test_non_featured_list_response_is_not_cached(self):
        url = reverse("categories:business-category-list")
        with patch(
            "categories.views.list_business_categories",
            wraps=views.list_business_categories,
        ) as list_categories:
            self.client.get(url, {"is_featured": "false"})
            self.client.get(url, {"is_featured": "false"})

        self.assertEqual(list_categories.call_count, 2)


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class ProductCategoryListEndpointTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = ProductCategory.objects.create(
            name="Electronics",
            label="Electronics",
            slug="electronics",
            aliases="devices,gadgets",
            is_featured=True,
        )
        cls.child = ProductCategory.objects.create(
            name="Mobile Phone",
            display_name="Phones",
            label="Mobile Phones",
            slug="mobile-phones",
            parent=cls.root,
        )
        ProductCategory.objects.create(
            name="Inactive Accessory",
            label="Inactive Accessories",
            slug="inactive-accessories",
            parent=cls.root,
            is_active=False,
        )

    def setUp(self):
        cache.clear()

    def test_lists_product_categories_with_pagination(self):
        response = self.client.get(
            reverse("categories:product-category-list"),
            {"page_size": 2},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            reverse("categories:product-category-list"),
            "/api/categories/product/",
        )
        self.assertEqual(response.data["pagination"]["total_items"], 3)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIn("parent", response.data["results"][0])
        self.assertIn("image", response.data["results"][0])

    def test_supports_search_state_hierarchy_and_sort_filters(self):
        response = self.client.get(
            reverse("categories:product-category-list"),
            {
                "search": "phone",
                "parent": self.root.pk,
                "is_root": "false",
                "is_active": "true",
                "is_featured": "false",
                "sort_by": "name",
                "sort_order": "desc",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [category["slug"] for category in response.data["results"]],
            ["mobile-phones"],
        )

    def test_supports_root_category_filter(self):
        response = self.client.get(
            reverse("categories:product-category-list"),
            {"is_root": "true"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [category["slug"] for category in response.data["results"]],
            ["electronics"],
        )

    def test_rejects_invalid_parameters(self):
        response = self.client.get(
            reverse("categories:product-category-list"),
            {
                "page_size": 101,
                "sort_by": "unknown",
                "sort_order": "sideways",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            set(response.data),
            {"page_size", "sort_by", "sort_order"},
        )

    def test_rejects_parent_with_root_filter(self):
        response = self.client.get(
            reverse("categories:product-category-list"),
            {"parent": self.root.pk, "is_root": "true"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parent", response.data)

    def test_supports_created_and_updated_date_ranges(self):
        response = self.client.get(
            reverse("categories:product-category-list"),
            {
                "created_before": self.root.created_at.isoformat(),
                "updated_after": self.root.updated_at.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data["results"], list)
