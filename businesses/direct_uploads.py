from pathlib import PurePosixPath
from uuid import uuid4

import boto3
from botocore.config import Config
from django.conf import settings


ALLOWED_CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def storage_key(relative_key):
    return str(PurePosixPath(settings.R2_LOCATION, relative_key)) if settings.R2_LOCATION else relative_key


def new_upload_key(business_id, content_type):
    return f"businesses/gallery/pending/{business_id}/{uuid4().hex}{ALLOWED_CONTENT_TYPES[content_type]}"


def new_webp_key(folder, owner_id):
    return f"{folder}/{owner_id}/{uuid4().hex}.webp"


def presign_upload(relative_key, content_type):
    return r2_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.R2_BUCKET_NAME, "Key": storage_key(relative_key), "ContentType": content_type},
        ExpiresIn=300,
    )
