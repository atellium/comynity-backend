from django.contrib import admin

from uploads.models import Upload


@admin.register(Upload)
class UploadAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "mime_type",
        "size",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("status", "mime_type", "created_at")
    search_fields = ("id", "object_key", "uploaded_by__phone", "uploaded_by__email")
    readonly_fields = (
        "id",
        "object_key",
        "mime_type",
        "size",
        "title",
        "status",
        "uploaded_by",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)
