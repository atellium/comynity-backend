import json
from uuid import UUID
from unittest.mock import patch
from types import SimpleNamespace

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from products.product import Product, generate_product_public_id
from products.serializers import (
    NearbyProductListQuerySerializer,
    ProductCategoryBulkImportSerializer,
    ProductBusinessSerializer,
    ProductCategoryListQuerySerializer,
    ProductSerializer,
)
from products.services import list_featured_product_categories
from products.views import nearby_product_list, product_list_create


class ProductIdentityTests(SimpleTestCase):
    def test_generated_public_id_is_eight_alphanumeric_characters(self):
        public_id = generate_product_public_id()

        self.assertEqual(len(public_id), 8)
        self.assertTrue(public_id.isalnum())

    def test_slug_ends_with_public_id(self):
        product = Product(name="Premium Cotton Shirt", public_id="a1b2c3d4")

        self.assertEqual(product.build_slug(), "premium-cotton-shirt-a1b2c3d4")

    def test_long_name_slug_respects_field_length(self):
        product = Product(name="A" * 300, public_id="a1b2c3d4")

        self.assertEqual(len(product.build_slug()), 255)
        self.assertTrue(product.build_slug().endswith("-a1b2c3d4"))

    def test_save_rebuilds_slug_from_current_name(self):
        product = Product(name="Premium Cotton Shirt", public_id="a1b2c3d4")
        product.slug = "old-name-a1b2c3d4"
        product.name = "Linen Shirt"

        with patch("django.db.models.Model.save", return_value=None):
            product.save(update_fields={"name"})

        self.assertEqual(product.slug, "linen-shirt-a1b2c3d4")


class ProductEndpointTests(SimpleTestCase):
    def test_nearby_product_list_url(self):
        self.assertEqual(
            reverse("products:nearby-product-list"),
            "/api/products/",
        )

    def test_category_list_url(self):
        self.assertEqual(
            reverse("products:product-category-list"),
            "/api/products/categories/",
        )

    def test_category_bulk_import_url(self):
        self.assertEqual(
            reverse("products:product-category-bulk-import"),
            "/api/products/categories/import/",
        )

    def test_create_url_uses_business_slug(self):
        self.assertEqual(
            reverse(
                "products:product-list-create",
                kwargs={"business_slug": "royal-store"},
            ),
            "/api/businesses/mine/royal-store/products/",
        )

    def test_public_business_product_list_url_uses_business_slug(self):
        self.assertEqual(
            reverse(
                "products:business-product-list",
                kwargs={"business_slug": "royal-store"},
            ),
            "/api/businesses/royal-store/products/",
        )

    def test_public_product_detail_url_uses_product_slug(self):
        self.assertEqual(
            reverse(
                "products:public-product-detail",
                kwargs={"product_slug": "linen-shirt-a1b2c3d4"},
            ),
            "/api/products/linen-shirt-a1b2c3d4/",
        )

    def test_detail_url_uses_business_and_product_slugs(self):
        self.assertEqual(
            reverse(
                "products:product-detail",
                kwargs={
                    "business_slug": "royal-store",
                    "product_slug": "linen-shirt-a1b2c3d4",
                },
            ),
            "/api/businesses/mine/royal-store/products/linen-shirt-a1b2c3d4/",
        )

    def test_product_detail_serializer_includes_business_information(self):
        self.assertIn("business", ProductSerializer.Meta.fields)

        business = SimpleNamespace(
            id=UUID("6fa5af1f-07fd-4513-af73-8ece22d7af51"),
            name="Royal Store",
            slug="royal-store",
            locality="Park Street",
            city_id=12,
            city=SimpleNamespace(
                name="Kolkata",
                state_id=3,
                state=SimpleNamespace(name="West Bengal"),
            ),
            cover_image_id=None,
        )

        self.assertEqual(
            ProductBusinessSerializer(business).data,
            {
                "id": "6fa5af1f-07fd-4513-af73-8ece22d7af51",
                "name": "Royal Store",
                "slug": "royal-store",
                "locality": "Park Street",
                "city": {
                    "id": 12,
                    "name": "Kolkata",
                    "state_id": 3,
                    "state": "West Bengal",
                },
                "media": {"cover_image": None},
            },
        )

    @patch("products.views.ProductSerializer")
    @patch("products.views.order_products")
    @patch("products.views.Product")
    @patch("products.views._owned_business")
    def test_owner_product_list_includes_business_information(
        self,
        owned_business,
        product_model,
        order_products,
        product_serializer,
    ):
        business = SimpleNamespace(
            pk="6fa5af1f-07fd-4513-af73-8ece22d7af51",
            name="Royal Store",
            slug="royal-store",
        )
        products = object()
        ordered_products = object()
        user = SimpleNamespace(pk="owner-id", is_authenticated=True)
        request = APIRequestFactory().get(
            reverse(
                "products:product-list-create",
                kwargs={"business_slug": "royal-store"},
            )
        )
        force_authenticate(request, user=user)
        owned_business.return_value = business
        product_model.objects.filter.return_value.prefetch_related.return_value = products
        order_products.return_value = ordered_products
        product_serializer.return_value.data = [{"id": 1, "name": "Linen Shirt"}]

        response = product_list_create(request, business_slug="royal-store")

        self.assertEqual(
            response.data["business"],
            {
                "id": business.pk,
                "name": "Royal Store",
                "slug": "royal-store",
            },
        )
        self.assertEqual(response.data["results"], [{"id": 1, "name": "Linen Shirt"}])
        product_model.objects.filter.assert_called_once_with(business=business)
        order_products.assert_called_once_with(products)

    @patch("products.views.ProductSerializer")
    @patch("products.views.ProductCategorySerializer")
    @patch("products.views.paginate_products")
    @patch("products.views.list_nearby_products")
    @patch("products.views.find_active_product_category")
    def test_nearby_product_list_includes_category_information(
        self,
        find_category,
        list_products,
        paginate_products,
        category_serializer,
        product_serializer,
    ):
        category = SimpleNamespace(slug="stethoscopes")
        products = object()
        page_products = object()
        request = APIRequestFactory().get(
            reverse("products:nearby-product-list"),
            {
                "lat": "22.467778888332326",
                "lng": "88.40233304308231",
                "category": "stethoscopes",
            },
        )
        find_category.return_value = category
        list_products.return_value = products
        paginate_products.return_value = (
            page_products,
            {"page": 1, "page_size": 20, "total_pages": 1},
        )
        category_serializer.return_value.data = {"slug": "stethoscopes"}
        product_serializer.return_value.data = [{"name": "Classic Stethoscope"}]

        response = nearby_product_list(request)

        self.assertEqual(response.data["category"], {"slug": "stethoscopes"})
        self.assertEqual(response.data["results"], [{"name": "Classic Stethoscope"}])
        find_category.assert_called_once_with("stethoscopes")
        list_products.assert_called_once()
        paginate_products.assert_called_once_with(products, 1, 20)

    def test_category_bulk_import_accepts_json_file_contract(self):
        upload = SimpleUploadedFile(
            "categories.json",
            json.dumps(
                [
                    {
                        "name": "Mobile Phone",
                        "slug": "mobile-phones",
                        "label": "Mobile Phones",
                        "display_name": "Mobiles",
                        "aliases": "smartphones,cell phones",
                        "sort_order": 5,
                        "is_active": True,
                        "is_featured": False,
                    }
                ]
            ).encode("utf-8"),
            content_type="application/json",
        )

        serializer = ProductCategoryBulkImportSerializer(data={"file": upload})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["categories"][0],
            {
                "name": "Mobile Phone",
                "slug": "mobile-phones",
                "label": "Mobile Phones",
                "display_name": "Mobiles",
                "aliases": "smartphones,cell phones",
                "sort_order": 5,
                "is_active": True,
                "is_featured": False,
            },
        )

    def test_category_bulk_import_rejects_duplicate_slugs_in_file(self):
        upload = SimpleUploadedFile(
            "categories.json",
            json.dumps(
                [
                    {"name": "Mobile Phone", "slug": "mobile-phones"},
                    {"name": "Smartphone", "slug": "mobile-phones"},
                ]
            ).encode("utf-8"),
            content_type="application/json",
        )

        serializer = ProductCategoryBulkImportSerializer(data={"file": upload})

        self.assertFalse(serializer.is_valid())
        self.assertIn("file", serializer.errors)


class ProductServiceTests(SimpleTestCase):
    @patch("products.services.ProductCategory")
    def test_featured_product_categories_require_featured_categories_with_active_products(
        self,
        product_category,
    ):
        business = SimpleNamespace(pk="business-id")
        ordered_categories = object()
        product_category.objects.filter.return_value.select_related.return_value.distinct.return_value.order_by.return_value = (
            ordered_categories
        )

        result = list_featured_product_categories(business)

        self.assertIs(result, ordered_categories)
        product_category.objects.filter.assert_called_once_with(
            products__business=business,
            products__status=Product.Status.ACTIVE,
            is_active=True,
            is_featured=True,
        )


class ProductCategoryListQuerySerializerTests(SimpleTestCase):
    def test_rejects_multiple_hierarchy_filters(self):
        serializer = ProductCategoryListQuerySerializer(
            data={"parent": 1, "parent_slug": "shirts"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("parent", serializer.errors)

    def test_rejects_inverted_date_range(self):
        serializer = ProductCategoryListQuerySerializer(
            data={
                "created_after": "2026-09-12T10:00:00Z",
                "created_before": "2026-09-11T10:00:00Z",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("created_before", serializer.errors)


class NearbyProductListQuerySerializerTests(SimpleTestCase):
    def test_requires_location_and_category(self):
        serializer = NearbyProductListQuerySerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertIn("lat", serializer.errors)
        self.assertIn("lng", serializer.errors)
        self.assertIn("category", serializer.errors)

    def test_defaults_radius_to_five_km(self):
        serializer = NearbyProductListQuerySerializer(
            data={
                "lat": "22.467778888332326",
                "lng": "88.40233304308231",
                "category": "stethoscopes",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["radius_km"], 5)

    def test_accepts_radius_alias(self):
        serializer = NearbyProductListQuerySerializer(
            data={
                "lat": "22.467778888332326",
                "lng": "88.40233304308231",
                "category": "stethoscopes",
                "radius": "10",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["radius_km"], 10)
