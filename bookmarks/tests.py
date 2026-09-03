from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase
from django.urls import reverse

from bookmarks.models import SavedItem
from bookmarks.serializers import SavedItemListSerializer, SavedItemSerializer


class SavedItemSerializerTests(SimpleTestCase):
    @patch("bookmarks.serializers.Catalog.objects.filter")
    def test_accepts_existing_product(self, catalog_filter):
        catalog_filter.return_value.exists.return_value = True
        product_id = uuid4()

        serializer = SavedItemSerializer(
            data={"item_type": "product", "object_id": product_id}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        catalog_filter.assert_called_once_with(pk=product_id)

    @patch("bookmarks.serializers.Catalog.objects.filter")
    def test_rejects_unknown_product(self, catalog_filter):
        catalog_filter.return_value.exists.return_value = False

        serializer = SavedItemSerializer(
            data={"item_type": "product", "object_id": uuid4()}
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors["object_id"][0],
            "The referenced object does not exist.",
        )

    @patch("bookmarks.serializers.BusinessListSerializer")
    def test_list_keeps_saved_item_fields_and_adds_business_item(self, serializer):
        object_id = uuid4()
        saved_item = SavedItem(
            id=uuid4(), item_type="business", object_id=object_id
        )
        business = object()
        serializer.return_value.data = {"name": "Royal Store"}

        data = SavedItemListSerializer(
            saved_item,
            context={"resolved_items": {"business": {object_id: business}}},
        ).data

        self.assertEqual(data["id"], str(saved_item.id))
        self.assertEqual(data["item_type"], "business")
        self.assertEqual(data["object_id"], str(object_id))
        self.assertEqual(data["item"], {"name": "Royal Store"})
        serializer.assert_called_once_with(business, context={"resolved_items": {"business": {object_id: business}}})

    @patch("bookmarks.serializers.ProductListSerializer")
    def test_list_uses_product_listing_serializer(self, serializer):
        object_id = uuid4()
        saved_item = SavedItem(
            id=uuid4(), item_type="product", object_id=object_id
        )
        product = object()
        serializer.return_value.data = {"name": "Premium Shirt"}
        context = {"resolved_items": {"product": {object_id: product}}}

        data = SavedItemListSerializer(saved_item, context=context).data

        self.assertEqual(data["item"], {"name": "Premium Shirt"})
        serializer.assert_called_once_with(product, context=context)


class SavedItemUrlTests(SimpleTestCase):
    def test_detail_url_uses_object_id(self):
        object_id = uuid4()

        self.assertEqual(
            reverse(
                "bookmarks:saved-item-detail",
                kwargs={"object_id": object_id},
            ),
            f"/api/saved-items/{object_id}/",
        )
