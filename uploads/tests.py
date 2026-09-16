from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate
from unittest.mock import MagicMock, patch
from uuid import UUID

from uploads.models import Upload
from uploads.serializers import (
    UploadCompleteSerializer,
    UploadCreateSerializer,
    UploadDeleteSerializer,
    UploadSerializer,
)
from uploads.views import upload_delete


class UploadSerializerTests(SimpleTestCase):
    def test_upload_response_contains_only_public_fields(self):
        upload = Upload(
            object_key="uploads/example.webp",
            mime_type="image/webp",
            size=1024,
            title="Example",
            status=Upload.Status.READY,
        )

        self.assertEqual(
            set(UploadSerializer(upload).data),
            {"id", "object_key", "url", "title"},
        )

    def test_create_accepts_multiple_supported_images(self):
        serializer = UploadCreateSerializer(
            data={
                "files": [
                    {"mime_type": "image/jpeg", "size": 1024},
                    {"mime_type": "image/png"},
                ]
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(len(serializer.validated_data["files"]), 2)

    def test_create_rejects_unsupported_mime_type(self):
        serializer = UploadCreateSerializer(
            data={"files": [{"mime_type": "video/mp4"}]}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("files", serializer.errors)

    def test_complete_rejects_duplicate_ids(self):
        upload_id = "11111111-1111-1111-1111-111111111111"
        serializer = UploadCompleteSerializer(
            data={"upload_ids": [upload_id, upload_id]}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("upload_ids", serializer.errors)

    def test_delete_rejects_duplicate_ids(self):
        upload_id = "11111111-1111-1111-1111-111111111111"
        serializer = UploadDeleteSerializer(
            data={"upload_ids": [upload_id, upload_id]}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("upload_ids", serializer.errors)


class UploadUrlTests(SimpleTestCase):
    def test_delete_url(self):
        self.assertEqual(
            reverse("uploads:upload-delete"),
            "/api/uploads/delete/",
        )


class UploadDeleteViewTests(SimpleTestCase):
    @patch("uploads.views.timezone")
    @patch("uploads.views.r2_client")
    @patch("uploads.views.Upload")
    @patch("uploads.views.settings")
    def test_deletes_owned_uploads_from_r2_and_database(
        self,
        settings,
        upload_model,
        r2_client,
        timezone,
    ):
        upload_id = UUID("11111111-1111-1111-1111-111111111111")
        upload = Upload(id=upload_id, object_key="uploads/example.webp")
        user = SimpleUser(pk="user-id")
        request = APIRequestFactory().delete(
            reverse("uploads:upload-delete"),
            {"upload_ids": [str(upload_id)]},
            format="json",
        )
        force_authenticate(request, user=user)
        settings.R2_ENABLED = True
        settings.R2_BUCKET_NAME = "bucket"
        settings.R2_LOCATION = ""
        timezone.now.return_value = "now"
        delete_queryset = MagicMock()
        upload_model.objects.filter.side_effect = ([upload], delete_queryset)
        r2_client.return_value.delete_objects.return_value = {}

        response = upload_delete(request)

        self.assertEqual(response.data["deleted"], 1)
        self.assertEqual(response.data["upload_ids"], [upload_id])
        upload_model.objects.filter.assert_any_call(
            uploaded_by=user,
            pk__in=[upload_id],
        )
        r2_client.return_value.delete_objects.assert_called_once_with(
            Bucket="bucket",
            Delete={
                "Objects": [{"Key": "uploads/example.webp"}],
                "Quiet": True,
            },
        )
        upload_model.objects.filter.assert_any_call(pk__in=[upload_id])
        delete_queryset.delete.assert_called_once()


class SimpleUser:
    def __init__(self, *, pk):
        self.pk = pk
        self.is_authenticated = True
