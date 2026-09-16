from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase
from django.urls import reverse

from bookmarks.models import SavedItem
from bookmarks.serializers import SavedItemListSerializer, SavedItemSerializer
from bookmarks.services import resolve_saved_items


class SavedItemSerializerTests(SimpleTestCase):
    @patch("bookmarks.serializers.Product.objects.filter")
    def test_accepts_existing_product(self, product_filter):
        product_filter.return_value.exists.return_value = True
        product_id = uuid4()

        serializer = SavedItemSerializer(
            data={"item_type": "product", "object_id": product_id}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        product_filter.assert_called_once_with(pk=product_id)

    @patch("bookmarks.serializers.Product.objects.filter")
    def test_rejects_unknown_product(self, product_filter):
        product_filter.return_value.exists.return_value = False

        serializer = SavedItemSerializer(
            data={"item_type": "product", "object_id": uuid4()}
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors["object_id"][0],
            "The referenced object does not exist.",
        )

    @patch("bookmarks.serializers.Doctor.objects.filter")
    def test_accepts_existing_doctor(self, doctor_filter):
        doctor_filter.return_value.exists.return_value = True
        doctor_id = uuid4()

        serializer = SavedItemSerializer(
            data={"item_type": "doctor", "object_id": doctor_id}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        doctor_filter.assert_called_once_with(pk=doctor_id)

    @patch("bookmarks.serializers.Doctor.objects.filter")
    def test_rejects_unknown_doctor(self, doctor_filter):
        doctor_filter.return_value.exists.return_value = False

        serializer = SavedItemSerializer(
            data={"item_type": "doctor", "object_id": uuid4()}
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

    @patch("bookmarks.serializers.PublicProductListSerializer")
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

    @patch("bookmarks.serializers.DoctorListItemSerializer")
    def test_list_uses_doctor_listing_serializer(self, serializer):
        object_id = uuid4()
        saved_item = SavedItem(
            id=uuid4(), item_type="doctor", object_id=object_id
        )
        doctor = object()
        serializer.return_value.data = {"name": "Dr. Ananya Sen"}
        context = {"resolved_items": {"doctor": {object_id: doctor}}}

        data = SavedItemListSerializer(saved_item, context=context).data

        self.assertEqual(data["item"], {"name": "Dr. Ananya Sen"})
        serializer.assert_called_once_with(doctor, context=context)


class SavedItemServiceTests(SimpleTestCase):
    @patch("bookmarks.services.Product")
    @patch("bookmarks.services.business_response_queryset")
    @patch("bookmarks.services.Doctor")
    def test_resolves_doctor_saved_items(self, doctor_model, business_queryset, product_model):
        object_id = uuid4()
        doctor = SimpleDoctor(pk=object_id)
        saved_item = SavedItem(item_type="doctor", object_id=object_id)
        business_queryset.return_value.filter.return_value = []
        product_model.objects.filter.return_value.prefetch_related.return_value = []
        doctor_model.objects.filter.return_value.select_related.return_value.prefetch_related.return_value = [
            doctor
        ]

        resolved_items = resolve_saved_items([saved_item])

        self.assertEqual(
            resolved_items["doctor"],
            {object_id: doctor},
        )
        doctor_model.objects.filter.assert_called_once_with(
            pk__in=[object_id],
            is_active=True,
            business__is_active=True,
        )


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


class SimpleDoctor:
    def __init__(self, *, pk):
        self.pk = pk
