from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework import serializers

from uploads.direct_uploads import ALLOWED_IMAGE_CONTENT_TYPES
from uploads.models import Upload


class UploadCreateItemSerializer(serializers.Serializer):
    mime_type = serializers.ChoiceField(choices=tuple(ALLOWED_IMAGE_CONTENT_TYPES))
    size = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        max_value=settings.MAX_IMAGE_UPLOAD_BYTES,
    )


class UploadCreateSerializer(serializers.Serializer):
    files = UploadCreateItemSerializer(many=True, allow_empty=False, max_length=20)


class UploadCompleteSerializer(serializers.Serializer):
    upload_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        max_length=20,
    )

    def validate_upload_ids(self, upload_ids):
        if len(upload_ids) != len(set(upload_ids)):
            raise serializers.ValidationError("Upload ids must be unique.")
        return upload_ids


class UploadSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Upload
        fields = (
            "id",
            "object_key",
            "mime_type",
            "size",
            "title",
            "status",
            "url",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_url(self, obj):
        if obj.status != Upload.Status.READY:
            return None
        url = default_storage.url(obj.object_key)
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request and url.startswith("/") else url
