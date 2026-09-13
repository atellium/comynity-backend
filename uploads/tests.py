from django.test import SimpleTestCase

from uploads.serializers import UploadCompleteSerializer, UploadCreateSerializer


class UploadSerializerTests(SimpleTestCase):
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
