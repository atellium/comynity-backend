import json
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework import serializers
from rest_framework.test import APIRequestFactory, force_authenticate

from . import views
from .models import Catalog, CatalogCategory, CatalogImage, generate_catalog_public_id
from .services import list_public_catalogs, list_public_products
from .serializers import (
    CatalogWriteSerializer,
    CatalogDetailSerializer,
    CatalogCategoryListQuerySerializer,
    CatalogImageSerializer,
    CatalogGallerySyncSerializer,
    CatalogImageBulkUploadSerializer,
    CatalogImageWriteSerializer,
    OwnerCatalogListQuerySerializer,
    ProductDetailSerializer,
    ProductListQuerySerializer,
    ProductListSerializer,
    PublicCatalogListQuerySerializer,
)


class ProductListEndpointTests(SimpleTestCase):
    def test_product_list_serializer_includes_variants(self):
        product_id = uuid4()
        product = type(
            "ProductResult",
            (),
            {
                "id": product_id,
                "public_id": "a1b2c3d4",
                "name": "Premium Shirt",
                "slug": "premium-shirt-a1b2c3d4",
                "price_type": "fixed",
                "price": Decimal("999.00"),
                "max_price": None,
                "original_price": None,
                "variants": [{"name": "Size", "options": ["S", "M", "L"]}],
                "specifications": {"material": "Cotton"},
                "categories": [],
                "is_featured": True,
                "sort_order": 4,
                "_prefetched_primary_images": [],
            },
        )()

        data = ProductListSerializer(product).data

        self.assertEqual(data["id"], str(product_id))
        self.assertEqual(
            data["variants"],
            [{"name": "Size", "options": ["S", "M", "L"]}],
        )
        self.assertEqual(data["specifications"], {"material": "Cotton"})
        self.assertTrue(data["is_featured"])
        self.assertEqual(data["sort_order"], 4)

    def test_product_detail_serializer_includes_id(self):
        self.assertIn("id", ProductDetailSerializer.Meta.fields)

    def test_product_detail_serializer_includes_sort_order(self):
        self.assertIn("sort_order", ProductDetailSerializer.Meta.fields)

    def test_url_uses_business_slug(self):
        self.assertEqual(
            reverse(
                "catalogs:business-product-list",
                kwargs={"slug": "royal-grocery-store"},
            ),
            "/api/businesses/royal-grocery-store/catalogs/products/",
        )

    def test_product_detail_url_uses_product_slug(self):
        self.assertEqual(
            reverse(
                "catalogs:product-detail",
                kwargs={"slug": "premium-shirt-a1b2c3d4"},
            ),
            "/api/r/products/premium-shirt-a1b2c3d4/",
        )

    def test_catalog_product_detail_url_is_supported(self):
        self.assertEqual(
            reverse(
                "catalogs:catalog-product-detail",
                kwargs={"slug": "premium-shirt-a1b2c3d4"},
            ),
            "/api/catalogs/products/premium-shirt-a1b2c3d4/",
        )

    def test_legacy_product_detail_url_is_supported(self):
        self.assertEqual(
            reverse(
                "catalogs:product-detail-legacy",
                kwargs={"slug": "premium-shirt-a1b2c3d4"},
            ),
            "/api/products/premium-shirt-a1b2c3d4/",
        )

    @patch("catalogs.views.get_public_product_by_slug", return_value=None)
    def test_unknown_or_unavailable_product_returns_404(self, get_product):
        response = self.client.get(
            reverse(
                "catalogs:product-detail",
                kwargs={"slug": "missing-product-a1b2c3d4"},
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Product not found."})
        get_product.assert_called_once_with("missing-product-a1b2c3d4")

    def test_query_accepts_supported_filters(self):
        query = ProductListQuerySerializer(
            data={
                "category": "clothing",
                "search": "shirt",
                "min_price": "100.00",
                "max_price": "999.00",
                "price_type": "fixed",
                "is_featured": "false",
                "sort_by": "price",
                "sort_order": "desc",
                "page": 2,
                "page_size": 50,
            }
        )

        self.assertTrue(query.is_valid(), query.errors)
        self.assertEqual(query.validated_data["min_price"], Decimal("100.00"))
        self.assertEqual(query.validated_data["max_price"], Decimal("999.00"))
        self.assertFalse(query.validated_data["is_featured"])

    def test_query_rejects_inverted_price_range(self):
        query = ProductListQuerySerializer(
            data={"min_price": "1000.00", "max_price": "100.00"}
        )

        self.assertFalse(query.is_valid())
        self.assertIn("max_price", query.errors)

    def test_public_catalog_list_url(self):
        self.assertEqual(
            reverse(
                "catalogs:business-catalog-list",
                kwargs={"slug": "royal-grocery-store"},
            ),
            "/api/businesses/royal-grocery-store/catalogs/",
        )

    def test_public_catalog_list_query_requires_type(self):
        query = PublicCatalogListQuerySerializer(data={})

        self.assertFalse(query.is_valid())
        self.assertEqual(set(query.errors), {"type"})

    def test_public_catalog_list_query_accepts_supported_type(self):
        query = PublicCatalogListQuerySerializer(data={"type": "doctor"})

        self.assertTrue(query.is_valid(), query.errors)
        self.assertEqual(query.validated_data["type"], "doctor")

    @patch("catalogs.views.paginate_products")
    @patch("catalogs.views.list_public_catalogs")
    @patch("catalogs.views.list_available_catalog_categories")
    @patch("catalogs.views.get_public_business")
    def test_public_catalog_list_filters_by_required_type(
        self,
        get_business,
        list_categories,
        list_catalogs,
        paginate_products,
    ):
        get_business.return_value = type(
            "BusinessResult",
            (),
            {"pk": uuid4(), "name": "Royal Store", "slug": "royal-store"},
        )()
        list_categories.return_value = []
        list_catalogs.return_value = []
        paginate_products.return_value = (
            [],
            {
                "page": 1,
                "page_size": 20,
                "total_pages": 1,
                "total_items": 0,
                "has_next": False,
                "has_previous": False,
            },
        )

        response = self.client.get(
            reverse(
                "catalogs:business-catalog-list",
                kwargs={"slug": "royal-store"},
            ),
            {"type": "doctor"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
        list_catalogs.assert_called_once()
        self.assertEqual(list_catalogs.call_args.args[1]["type"], "doctor")
        list_categories.assert_called_once_with(get_business.return_value, "doctor")

    @patch("catalogs.views.paginate_products")
    @patch("catalogs.views.list_public_products")
    @patch("catalogs.views.list_available_product_categories")
    @patch("catalogs.views.get_public_business")
    def test_response_includes_all_available_product_categories(
        self,
        get_business,
        list_categories,
        list_products,
        paginate_products,
    ):
        get_business.return_value = type(
            "BusinessResult",
            (),
            {"pk": uuid4(), "name": "Royal Store", "slug": "royal-store"},
        )()
        list_categories.return_value = [
            CatalogCategory(
                id=4,
                name="Clothing",
                label="Apparel",
                slug="clothing",
            )
        ]
        list_products.return_value = []
        paginate_products.return_value = (
            [],
            {
                "page": 1,
                "page_size": 20,
                "total_pages": 1,
                "total_items": 0,
                "has_next": False,
                "has_previous": False,
            },
        )

        response = self.client.get(
            reverse(
                "catalogs:business-product-list",
                kwargs={"slug": "royal-store"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["categories"],
            [
                {
                    "id": 4,
                    "name": "Clothing",
                    "label": "Apparel",
                    "slug": "clothing",
                    "display_name": "Apparel",
                    "image": None,
                }
            ],
        )


class PublicCatalogOrderingTests(TestCase):
    def setUp(self):
        from businesses.models import Business

        self.business = Business.objects.create(
            name="Royal Store",
            address="12 Market Road",
            slug="royal-store",
            status=Business.Status.PUBLISHED,
            is_active=True,
        )

    def _catalog(self, name, *, catalog_type="product", featured=False, sort_order=0, price="10.00"):
        return Catalog.objects.create(
            business=self.business,
            name=name,
            type=catalog_type,
            is_featured=featured,
            sort_order=sort_order,
            price=Decimal(price),
        )

    def test_products_return_featured_first_by_sort_order_then_normal_current_sort(self):
        self._catalog("Normal Cheap", featured=False, sort_order=1, price="10.00")
        self._catalog("Featured Later", featured=True, sort_order=2, price="30.00")
        self._catalog("Normal Expensive", featured=False, sort_order=0, price="40.00")
        self._catalog("Featured Unordered", featured=True, sort_order=0, price="50.00")
        self._catalog("Featured Earlier", featured=True, sort_order=1, price="20.00")

        products = list(
            list_public_products(
                self.business,
                {
                    "sort_by": "price",
                    "sort_order": "desc",
                },
            )
        )

        self.assertEqual(
            [product.name for product in products],
            [
                "Featured Earlier",
                "Featured Later",
                "Featured Unordered",
                "Normal Expensive",
                "Normal Cheap",
            ],
        )

    def test_catalogs_return_featured_first_for_requested_type(self):
        self._catalog("Normal A", catalog_type="doctor", featured=False, sort_order=0)
        self._catalog("Featured B", catalog_type="doctor", featured=True, sort_order=2)
        self._catalog("Featured A", catalog_type="doctor", featured=True, sort_order=1)

        catalogs = list(
            list_public_catalogs(
                self.business,
                {
                    "type": "doctor",
                    "sort_by": "name",
                    "sort_order": "asc",
                },
            )
        )

        self.assertEqual(
            [catalog.name for catalog in catalogs],
            ["Featured A", "Featured B", "Normal A"],
        )


class CatalogManagementContractTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_create_url_is_scoped_to_owned_business(self):
        self.assertEqual(
            reverse(
                "catalogs:catalog-create",
                kwargs={"business_slug": "royal-store"},
            ),
            "/api/businesses/mine/royal-store/catalogs/",
        )

    def test_manage_url_uses_business_and_catalog_slugs(self):
        self.assertEqual(
            reverse(
                "catalogs:catalog-manage",
                kwargs={
                    "business_slug": "royal-store",
                    "catalog_slug": "premium-shirt-a1b2c3d4",
                },
            ),
            "/api/businesses/mine/royal-store/catalogs/premium-shirt-a1b2c3d4/",
        )

    def test_edit_url_uses_business_and_catalog_slugs(self):
        self.assertEqual(
            reverse(
                "catalogs:catalog-edit",
                kwargs={
                    "business_slug": "royal-store",
                    "catalog_slug": "premium-shirt-a1b2c3d4",
                },
            ),
            "/api/businesses/mine/royal-store/catalogs/"
            "premium-shirt-a1b2c3d4/edit/",
        )

    def test_edit_view_supports_patch_and_put(self):
        self.assertEqual(
            set(views.catalog_edit.cls.http_method_names),
            {"patch", "put", "options"},
        )

    def test_detail_url_uses_business_and_catalog_slugs(self):
        self.assertEqual(
            reverse(
                "catalogs:catalog-detail",
                kwargs={
                    "business_slug": "royal-store",
                    "catalog_slug": "premium-shirt-a1b2c3d4",
                },
            ),
            "/api/businesses/mine/royal-store/catalogs/"
            "premium-shirt-a1b2c3d4/details/",
        )

    def test_detail_view_supports_get(self):
        self.assertEqual(
            set(views.catalog_detail.cls.http_method_names),
            {"get", "options"},
        )

    def test_create_requires_name_and_type(self):
        serializer = CatalogWriteSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), {"name", "type"})

    def test_every_other_create_field_is_optional(self):
        serializer = CatalogWriteSerializer(
            data={"name": "Premium Shirt", "type": "product"}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_create_accepts_sort_order(self):
        serializer = CatalogWriteSerializer(
            data={"name": "Premium Shirt", "type": "product", "sort_order": 7}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["sort_order"], 7)

    def test_create_rejects_negative_sort_order(self):
        serializer = CatalogWriteSerializer(
            data={"name": "Premium Shirt", "type": "product", "sort_order": -1}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("sort_order", serializer.errors)

    def test_list_query_requires_type(self):
        serializer = OwnerCatalogListQuerySerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), {"type"})

    def test_list_query_accepts_supported_owner_types(self):
        for catalog_type in ("product", "service", "doctor"):
            serializer = OwnerCatalogListQuerySerializer(data={"type": catalog_type})

            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertEqual(serializer.validated_data["type"], catalog_type)

    def test_list_query_rejects_unsupported_type(self):
        serializer = OwnerCatalogListQuerySerializer(data={"type": "property"})

        self.assertFalse(serializer.is_valid())
        self.assertIn("type", serializer.errors)

    @patch("catalogs.views.list_catalogs_for_owner", return_value=[])
    @patch("catalogs.views._owned_business")
    def test_list_catalogs_filters_by_required_type(self, owned_business, list_catalogs):
        business = type("BusinessResult", (), {"pk": uuid4(), "owner_id": uuid4()})()
        owned_business.return_value = business
        request = self.factory.get(
            reverse(
                "catalogs:catalog-create",
                kwargs={"business_slug": "royal-store"},
            ),
            {"type": "service"},
        )
        force_authenticate(request, user=type("UserResult", (), {"pk": business.owner_id})())

        response = views.catalog_create(request, business_slug="royal-store")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"results": []})
        self.assertEqual(owned_business.call_args.args[1], "royal-store")
        list_catalogs.assert_called_once_with(business, "service")

    def test_partial_update_does_not_require_name_or_type(self):
        catalog = Catalog(name="Premium Shirt", type="product")
        serializer = CatalogWriteSerializer(
            catalog,
            data={"description": "Updated description"},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_partial_update_accepts_sort_order(self):
        catalog = Catalog(name="Premium Shirt", type="product")
        serializer = CatalogWriteSerializer(
            catalog,
            data={"sort_order": 3},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["sort_order"], 3)

    def test_detail_serializer_returns_expanded_categories(self):
        category = CatalogCategory(
            id=4,
            name="Homeopathy",
            label="Homeopathy",
            slug="homeopathy",
            type="specialty",
        )
        catalog = type(
            "CatalogResult",
            (),
            {
                "id": uuid4(),
                "public_id": "a1b2c3d4",
                "name": "Consultation",
                "slug": "consultation-a1b2c3d4",
                "type": "doctor",
                "description": "",
                "price_type": "fixed",
                "price": None,
                "max_price": None,
                "original_price": None,
                "variants": [],
                "specifications": {},
                "custom_fields": [],
                "categories": [category],
                "is_featured": False,
                "is_active": True,
                "sort_order": 0,
            },
        )()

        data = CatalogDetailSerializer(catalog).data

        self.assertEqual(data["categories"][0]["id"], 4)
        self.assertEqual(data["categories"][0]["name"], "Homeopathy")
        self.assertEqual(data["categories"][0]["slug"], "homeopathy")
        self.assertEqual(data["sort_order"], 0)


class CatalogCategoryListContractTests(SimpleTestCase):
    def test_list_url(self):
        self.assertEqual(
            reverse("catalogs:catalog-category-list"),
            "/api/catalogs/categories/",
        )

    def test_accepts_all_supported_filters_and_pagination(self):
        query = CatalogCategoryListQuerySerializer(
            data={
                "id": 4,
                "search": "phone",
                "name": "mobile",
                "label": "phones",
                "display_name": "mobile phones",
                "slug": "mobile-phones",
                "aliases": "devices",
                "type": "product",
                "parent_slug": "electronics",
                "is_active": "true",
                "is_featured": "false",
                "is_display": "true",
                "created_after": "2026-01-01T00:00:00Z",
                "created_before": "2026-12-31T23:59:59Z",
                "updated_after": "2026-01-01T00:00:00Z",
                "updated_before": "2026-12-31T23:59:59Z",
                "sort_by": "name",
                "sort_order": "desc",
                "page": 2,
                "page_size": 50,
            }
        )

        self.assertTrue(query.is_valid(), query.errors)
        self.assertEqual(query.validated_data["page"], 2)
        self.assertEqual(query.validated_data["page_size"], 50)

    def test_rejects_conflicting_hierarchy_filters(self):
        query = CatalogCategoryListQuerySerializer(
            data={"parent": 1, "is_root": "true"}
        )

        self.assertFalse(query.is_valid())
        self.assertIn("parent", query.errors)

    def test_rejects_invalid_page_and_sort_parameters(self):
        query = CatalogCategoryListQuerySerializer(
            data={"page": 0, "page_size": 101, "sort_by": "unknown"}
        )

        self.assertFalse(query.is_valid())
        self.assertEqual(set(query.errors), {"page", "page_size", "sort_by"})

class CatalogPublicIdTests(SimpleTestCase):
    def test_generated_public_id_is_eight_alphanumeric_characters(self):
        public_id = generate_catalog_public_id()

        self.assertEqual(len(public_id), 8)
        self.assertTrue(public_id.isalnum())

    def test_slug_ends_with_public_id(self):
        catalog = Catalog(name="Premium Cotton Shirt", public_id="a1b2c3d4")

        self.assertEqual(catalog.build_slug(), "premium-cotton-shirt-a1b2c3d4")

    def test_long_name_slug_respects_field_length(self):
        catalog = Catalog(name="A" * 300, public_id="a1b2c3d4")

        self.assertEqual(len(catalog.build_slug()), 200)
        self.assertTrue(catalog.build_slug().endswith("-a1b2c3d4"))


class CatalogImageCompressionTests(SimpleTestCase):
    @patch("django.db.models.Model.save")
    @patch("core.image_service.compress_image")
    def test_new_upload_is_compressed_before_save(self, compress_image, model_save):
        upload = SimpleUploadedFile("item.jpg", b"image", content_type="image/jpeg")
        compressed = SimpleUploadedFile(
            "compressed.webp",
            b"compressed",
            content_type="image/webp",
        )
        compress_image.return_value = compressed
        catalog_image = CatalogImage(image=upload)

        catalog_image.save(update_fields={"alt_text"})

        compress_image.assert_called_once_with(upload, max_width=1024, quality=80)
        self.assertIs(catalog_image.image.file, compressed)
        self.assertEqual(model_save.call_args.kwargs["update_fields"], {"alt_text", "image"})

    @patch("django.db.models.Model.save")
    @patch("core.image_service.compress_image")
    def test_committed_image_is_not_compressed_again(self, compress_image, model_save):
        catalog_image = CatalogImage(image="catalog/items/existing.webp")

        catalog_image.save()

        compress_image.assert_not_called()
        model_save.assert_called_once()


class CatalogImageEndpointContractTests(SimpleTestCase):
    def test_create_url(self):
        self.assertEqual(
            reverse(
                "catalogs:catalog-image-create",
                kwargs={
                    "business_slug": "royal-store",
                    "catalog_slug": "premium-shirt-a1b2c3d4",
                },
            ),
            "/api/businesses/mine/royal-store/catalogs/"
            "premium-shirt-a1b2c3d4/images/",
        )

    def test_manage_url_uses_integer_image_id(self):
        self.assertEqual(
            reverse(
                "catalogs:catalog-image-manage",
                kwargs={
                    "business_slug": "royal-store",
                    "catalog_slug": "premium-shirt-a1b2c3d4",
                    "image_id": 12,
                },
            ),
            "/api/businesses/mine/royal-store/catalogs/"
            "premium-shirt-a1b2c3d4/images/12/",
        )

    def test_create_requires_image_only(self):
        serializer = CatalogImageBulkUploadSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), {"images"})

    def test_bulk_upload_rejects_an_empty_image_list(self):
        serializer = CatalogImageBulkUploadSerializer(data={"images": []})

        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), {"images"})

    def test_gallery_sync_requires_final_order(self):
        serializer = CatalogGallerySyncSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertIn("order", serializer.errors)

    def test_gallery_sync_accepts_existing_images_in_final_order(self):
        serializer = CatalogGallerySyncSerializer(
            data={"order": ["existing:12", "existing:13"]}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["parsed_order"],
            [("existing", 12), ("existing", 13)],
        )

    def test_gallery_sync_rejects_missing_new_image_position(self):
        serializer = CatalogGallerySyncSerializer()

        with self.assertRaisesMessage(
            serializers.ValidationError,
            "Every uploaded image must appear exactly once",
        ):
            serializer.validate(
                {"images": [object(), object()], "order": ["new:0"]}
            )

    def test_bulk_upload_requires_one_sort_order_per_image(self):
        serializer = CatalogImageBulkUploadSerializer()

        with self.assertRaisesMessage(
            serializers.ValidationError,
            "Provide one sort order for every uploaded image.",
        ):
            serializer.validate({"images": [object(), object()], "sort_orders": [5]})

    def test_partial_update_accepts_metadata_only(self):
        image = CatalogImage(image="catalog/items/existing.webp")
        serializer = CatalogImageWriteSerializer(
            image,
            data={"alt_text": "Updated description", "is_primary": True},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_response_contains_image_metadata(self):
        self.assertEqual(
            CatalogImageSerializer.Meta.fields,
            (
                "id",
                "image",
                "alt_text",
                "is_primary",
                "is_active",
                "sort_order",
                "created_at",
                "updated_at",
            ),
        )


class SeedCatalogCategoriesCommandTests(TestCase):
    def run_seed(self, categories, **options):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "catalog_categories.json"
            source.write_text(json.dumps(categories), encoding="utf-8")
            call_command("seed_catalog_categories", file=source, **options)

    def test_seeds_categories_as_roots_by_default(self):
        self.run_seed(
            [
                {
                    "name": " Clothing ",
                    "label": " Apparel ",
                    "type": "product",
                    "aliases": " fashion, clothes ",
                    "sort_order": 2,
                    "is_active": True,
                    "is_featured": True,
                }
            ]
        )

        category = CatalogCategory.objects.get(name="Clothing", type="product")
        self.assertIsNone(category.parent)
        self.assertEqual(category.label, "Apparel")
        self.assertEqual(category.aliases, "fashion, clothes")
        self.assertEqual(category.sort_order, 2)
        self.assertTrue(category.is_featured)

    def test_attaches_categories_to_supplied_parent_id(self):
        parent = CatalogCategory.objects.create(name="Electronics", type="product")

        self.run_seed(
            [{"name": "Mobile Phones", "type": "product"}],
            parent_id=parent.pk,
        )

        child = CatalogCategory.objects.get(name="Mobile Phones")
        self.assertEqual(child.parent, parent)

    def test_repeat_run_updates_existing_category_and_can_make_it_root(self):
        parent = CatalogCategory.objects.create(name="Electronics", type="product")
        category = CatalogCategory.objects.create(
            name="Mobile Phones",
            type="product",
            parent=parent,
            label="Old label",
        )

        self.run_seed([{"name": "Mobile Phones", "label": "Phones"}])

        category.refresh_from_db()
        self.assertEqual(CatalogCategory.objects.count(), 2)
        self.assertIsNone(category.parent)
        self.assertEqual(category.label, "Phones")

    def test_repeat_run_updates_existing_category_by_slug(self):
        category = CatalogCategory.objects.create(
            name="Old Mobile",
            slug="mobile-phones",
            type="product",
            label="Old label",
            aliases="old",
            sort_order=10,
            is_active=False,
            is_featured=True,
            is_display=False,
        )

        self.run_seed(
            [
                {
                    "name": "Mobile Phones",
                    "label": "Phones",
                    "slug": "mobile-phones",
                    "type": "product",
                    "aliases": "smartphone",
                }
            ]
        )

        category.refresh_from_db()
        self.assertEqual(CatalogCategory.objects.count(), 1)
        self.assertEqual(category.name, "Mobile Phones")
        self.assertEqual(category.label, "Phones")
        self.assertEqual(category.aliases, "smartphone")
        self.assertEqual(category.sort_order, 0)
        self.assertTrue(category.is_active)
        self.assertFalse(category.is_featured)
        self.assertTrue(category.is_display)

    def test_rejects_parent_with_a_different_type(self):
        parent = CatalogCategory.objects.create(name="Services", type="service")

        with self.assertRaisesMessage(CommandError, "has type 'service'"):
            self.run_seed(
                [{"name": "Mobile Phones", "type": "product"}],
                parent_id=parent.pk,
            )

# Create your tests here.
