from io import BytesIO
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from core.image_service import _encode_webp, compress_image


class ImageCompressionTests(SimpleTestCase):
    @staticmethod
    def image_upload(width, height, image_format="JPEG"):
        content = BytesIO()
        Image.new("RGB", (width, height), "navy").save(content, format=image_format)
        return SimpleUploadedFile(
            f"test.{image_format.lower()}",
            content.getvalue(),
            content_type=f"image/{image_format.lower()}",
        )

    def test_converts_image_below_maximum_width_without_resizing(self):
        upload = self.image_upload(50, 25)

        result = compress_image(upload)

        self.assertIsNot(result, upload)
        self.assertRegex(result.name, r"^[0-9a-f]{32}\.webp$")
        self.assertEqual(result.content_type, "image/webp")
        with Image.open(result) as converted:
            self.assertEqual(converted.format, "WEBP")
            self.assertEqual(converted.size, (50, 25))

    def test_preserves_dimensions_for_large_images(self):
        upload = self.image_upload(200, 100)

        result = compress_image(upload)

        with Image.open(result) as compressed:
            self.assertEqual(compressed.size, (200, 100))
            self.assertEqual(compressed.format, "WEBP")
        self.assertTrue(result.name.endswith(".webp"))

    def test_resizes_to_maximum_width_while_preserving_aspect_ratio(self):
        upload = self.image_upload(400, 200)

        result = compress_image(upload, max_width=100)

        with Image.open(result) as compressed:
            self.assertEqual(compressed.size, (100, 50))

    def test_can_preserve_the_source_format(self):
        upload = self.image_upload(50, 25, image_format="PNG")

        result = compress_image(upload, convert_to_webp=False)

        self.assertTrue(result.name.endswith(".png"))
        self.assertEqual(result.content_type, "image/png")
        with Image.open(result) as compressed:
            self.assertEqual(compressed.format, "PNG")

    def test_rejects_invalid_maximum_width(self):
        upload = self.image_upload(50, 25)

        with self.assertRaises(ValueError):
            compress_image(upload, max_width=0)

    def test_supports_custom_webp_quality(self):
        upload = self.image_upload(50, 25)

        with patch("core.image_service._encode_webp", wraps=_encode_webp) as encode:
            compress_image(upload, quality=90)

        encode.assert_called_once()
        self.assertEqual(encode.call_args.kwargs["quality"], 90)

    def test_removes_metadata_and_generates_a_unique_object_name(self):
        content = BytesIO()
        image = Image.new("RGB", (50, 50), "navy")
        exif = Image.Exif()
        exif[270] = "sensitive location metadata"
        image.save(content, format="JPEG", exif=exif)
        first_upload = SimpleUploadedFile("photo.jpg", content.getvalue())
        second_upload = SimpleUploadedFile("photo.jpg", content.getvalue())

        first = compress_image(first_upload)
        second = compress_image(second_upload)

        self.assertNotEqual(first.name, second.name)
        with Image.open(first) as compressed:
            self.assertEqual(len(compressed.getexif()), 0)



class HealthEndpointTests(APITestCase):
    def test_health_endpoint_is_public(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_endpoint_rejects_post(self):
        response = self.client.post(reverse("core:health"))

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @override_settings(CORS_ALLOWED_ORIGINS=["https://app.example.com"])
    def test_api_response_allows_configured_origin(self):
        response = self.client.get(
            reverse("core:health"),
            HTTP_ORIGIN="https://app.example.com",
        )

        self.assertEqual(
            response["Access-Control-Allow-Origin"], "https://app.example.com"
        )
