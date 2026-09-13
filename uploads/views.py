from botocore.exceptions import ClientError
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from uploads.direct_uploads import (
    UPLOAD_URL_EXPIRES_IN,
    new_upload_key,
    presign_upload,
    r2_client,
    storage_key,
)
from uploads.models import Upload
from uploads.serializers import (
    UploadCompleteSerializer,
    UploadCreateSerializer,
    UploadSerializer,
)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def upload_list_create(request):
    if request.method == "GET":
        uploads = Upload.objects.filter(
            uploaded_by=request.user,
            status=Upload.Status.READY,
        )
        return Response(
            {
                "results": UploadSerializer(
                    uploads,
                    many=True,
                    context={"request": request},
                ).data
            }
        )

    if not settings.R2_ENABLED:
        return Response(
            {"detail": "Direct uploads require R2_ENABLED."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    serializer = UploadCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    results = []
    for file_data in serializer.validated_data["files"]:
        mime_type = file_data["mime_type"]
        object_key = new_upload_key(request.user.pk, mime_type)
        upload = Upload.objects.create(
            object_key=object_key,
            mime_type=mime_type,
            size=file_data.get("size"),
            uploaded_by=request.user,
        )
        results.append(
            {
                "id": upload.pk,
                "object_key": object_key,
                "upload_url": presign_upload(object_key, mime_type),
                "mime_type": mime_type,
                "expires_in": UPLOAD_URL_EXPIRES_IN,
            }
        )
    return Response({"results": results}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_complete(request):
    if not settings.R2_ENABLED:
        return Response(
            {"detail": "Direct uploads require R2_ENABLED."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    serializer = UploadCompleteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    uploads = Upload.objects.filter(
        uploaded_by=request.user,
        pk__in=serializer.validated_data["upload_ids"],
    )
    uploads_by_id = {upload.pk: upload for upload in uploads}
    missing_ids = set(serializer.validated_data["upload_ids"]) - set(uploads_by_id)
    if missing_ids:
        raise NotFound(
            "Uploads not found: "
            + ", ".join(str(upload_id) for upload_id in sorted(missing_ids, key=str))
        )

    client = r2_client()
    completed_uploads = []
    for upload_id in serializer.validated_data["upload_ids"]:
        upload = uploads_by_id[upload_id]
        if upload.status == Upload.Status.READY:
            completed_uploads.append(upload)
            continue
        if upload.status != Upload.Status.PENDING:
            raise ValidationError(
                {"upload_ids": f"Upload {upload.pk} cannot be completed from {upload.status}."}
            )
        try:
            metadata = client.head_object(
                Bucket=settings.R2_BUCKET_NAME,
                Key=storage_key(upload.object_key),
            )
        except ClientError as exc:
            raise ValidationError(
                {"upload_ids": f"Upload {upload.pk} was not found in R2."}
            ) from exc
        if metadata["ContentLength"] > settings.MAX_IMAGE_UPLOAD_BYTES:
            client.delete_object(
                Bucket=settings.R2_BUCKET_NAME,
                Key=storage_key(upload.object_key),
            )
            upload.status = Upload.Status.FAILED
            upload.size = metadata["ContentLength"]
            upload.save(update_fields=("status", "size", "updated_at"))
            raise ValidationError({"upload_ids": f"Upload {upload.pk} is too large."})
        if metadata.get("ContentType") != upload.mime_type:
            raise ValidationError(
                {"upload_ids": f"Upload {upload.pk} content type does not match."}
            )
        upload.status = Upload.Status.READY
        upload.size = metadata["ContentLength"]
        upload.save(update_fields=("status", "size", "updated_at"))
        completed_uploads.append(upload)

    return Response(
        {
            "results": UploadSerializer(
                completed_uploads,
                many=True,
                context={"request": request},
            ).data,
            "completed_at": timezone.now(),
        }
    )
