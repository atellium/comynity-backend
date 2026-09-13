from io import BytesIO
from uuid import uuid4

from django.core.files.base import ContentFile
from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError


ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image_upload(image_file):
    """Validate encoded size, actual format, dimensions, and decoded pixel count."""
    if image_file.size > settings.MAX_IMAGE_UPLOAD_BYTES:
        raise ValidationError("Image file is too large.")
    try:
        image_file.seek(0)
        with Image.open(image_file) as image:
            if image.format not in ALLOWED_IMAGE_FORMATS:
                raise ValidationError("Upload a JPEG, PNG, or WebP image.")
            if image.width * image.height > settings.MAX_IMAGE_PIXELS:
                raise ValidationError("Image dimensions are too large.")
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError("Upload a valid image file.") from exc
    finally:
        image_file.seek(0)
    return image_file


def compress_image(
    image_file,
    *,
    quality: int = 80,
    max_width: int | None = None,
    convert_to_webp: bool = True,
):
    """Resize, strip metadata, and optionally convert an image to WebP."""
    if not 1 <= quality <= 100:
        raise ValueError("Image quality must be between 1 and 100.")
    if max_width is not None and (
        isinstance(max_width, bool) or not isinstance(max_width, int) or max_width < 1
    ):
        raise ValueError("max_width must be a positive integer or None.")
    if not isinstance(convert_to_webp, bool):
        raise TypeError("convert_to_webp must be a boolean.")

    validate_image_upload(image_file)
    image_file.seek(0)
    with Image.open(image_file) as source:
        source_format = source.format
        source.load()
        image = ImageOps.exif_transpose(source).copy()

    if max_width is not None and image.width > max_width:
        height = max(1, round(image.height * max_width / image.width))
        image = image.resize((max_width, height), Image.Resampling.LANCZOS)

    # Re-encoding every upload strips EXIF, including GPS metadata.
    output_format = "WEBP" if convert_to_webp else source_format
    if output_format == "WEBP":
        content = _encode_webp(image, quality=quality)
    else:
        content = _encode_image(image, image_format=output_format, quality=quality)
    extension, content_type = {
        "JPEG": ("jpg", "image/jpeg"),
        "PNG": ("png", "image/png"),
        "WEBP": ("webp", "image/webp"),
    }[output_format]

    result = ContentFile(content, name=f"{uuid4().hex}.{extension}")
    # django-storages forwards this value to S3/R2 as the object's
    # Content-Type instead of relying on platform-specific MIME guessing.
    result.content_type = content_type
    return result


def _encode_webp(image: Image.Image, quality: int) -> bytes:
    return _encode_image(image, image_format="WEBP", quality=quality)


def _encode_image(image: Image.Image, *, image_format: str, quality: int) -> bytes:
    output = BytesIO()
    options = {"optimize": True}
    if image_format == "WEBP":
        options.update(quality=quality, method=6)
    elif image_format == "JPEG":
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        options.update(quality=quality, progressive=True)
    image.save(output, format=image_format, **options)
    return output.getvalue()
