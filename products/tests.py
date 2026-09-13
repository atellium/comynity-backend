from unittest.mock import patch
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from products.product import Product, generate_product_public_id
from products.serializers import ProductCategoryListQuerySerializer
from products.views import product_list_create


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
    def test_category_list_url(self):
        self.assertEqual(
            reverse("products:product-category-list"),
            "/api/products/categories/",
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
