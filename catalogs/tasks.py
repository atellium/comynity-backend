from uuid import uuid4

from celery import shared_task
from django.core.files.storage import default_storage

from catalogs.models import CatalogImage, CatalogImageUpload
from core.image_service import compress_image


@shared_task(bind=True, autoretry_for=(OSError,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def process_catalog_image_upload(self, upload_id):
    upload = CatalogImageUpload.objects.select_related("catalog").get(pk=upload_id)
    if upload.status == CatalogImageUpload.Status.READY:
        return
    upload.status = CatalogImageUpload.Status.PROCESSING
    upload.error = ""
    upload.save(update_fields=("status", "error", "updated_at"))
    try:
        with default_storage.open(upload.object_key, "rb") as source:
            processed = compress_image(source, max_width=1600, quality=84)
        final_key = f"catalog/items/{upload.catalog_id}/{uuid4().hex}.webp"
        saved_key = default_storage.save(final_key, processed)
        image = CatalogImage.objects.create(catalog=upload.catalog, image=saved_key)
        upload.catalog_image = image
        upload.status = CatalogImageUpload.Status.READY
        upload.save(update_fields=("catalog_image", "status", "updated_at"))
        default_storage.delete(upload.object_key)
    except Exception as exc:
        upload.status = CatalogImageUpload.Status.FAILED
        upload.error = str(exc)[:500]
        upload.save(update_fields=("status", "error", "updated_at"))
        raise
