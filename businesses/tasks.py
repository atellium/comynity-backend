from uuid import uuid4

from celery import shared_task
from django.core.files.storage import default_storage
from django.db import transaction

from businesses.models import BusinessGalleryImage, BusinessGalleryUpload
from core.image_service import compress_image


@shared_task(bind=True, autoretry_for=(OSError,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def process_business_gallery_upload(self, upload_id):
    upload = BusinessGalleryUpload.objects.select_related("business").get(pk=upload_id)
    if upload.status == BusinessGalleryUpload.Status.READY:
        return
    upload.status = BusinessGalleryUpload.Status.PROCESSING
    upload.error = ""
    upload.save(update_fields=("status", "error", "updated_at"))
    try:
        with default_storage.open(upload.object_key, "rb") as source:
            processed = compress_image(source, max_width=1600, quality=84)
        folder = {
            BusinessGalleryUpload.Kind.GALLERY: "businesses/gallery",
            BusinessGalleryUpload.Kind.THUMBNAIL: "businesses/thumbnails",
            BusinessGalleryUpload.Kind.OFFER: "offers",
        }[upload.kind]
        final_key = f"{folder}/{upload.business_id}/{uuid4().hex}.webp"
        saved_key = default_storage.save(final_key, processed)
        with transaction.atomic():
            if upload.kind == BusinessGalleryUpload.Kind.GALLERY:
                image = BusinessGalleryImage.objects.create(business=upload.business, image=saved_key)
                upload.gallery_image = image
            elif upload.kind == BusinessGalleryUpload.Kind.THUMBNAIL:
                old_image = upload.business.thumbnail
                upload.business.thumbnail = saved_key
                upload.business.save(update_fields=("thumbnail", "updated_at"))
                if old_image:
                    transaction.on_commit(lambda: old_image.delete(save=False))
            else:
                offer = upload.business.offers.get(pk=upload.target_id)
                old_image = offer.image
                offer.image = saved_key
                offer.save(update_fields=("image", "updated_at"))
                if old_image:
                    transaction.on_commit(lambda: old_image.delete(save=False))
            upload.status = BusinessGalleryUpload.Status.READY
            upload.save(update_fields=("gallery_image", "status", "updated_at"))
        default_storage.delete(upload.object_key)
    except Exception as exc:
        upload.status = BusinessGalleryUpload.Status.FAILED
        upload.error = str(exc)[:500]
        upload.save(update_fields=("status", "error", "updated_at"))
        raise
