import uuid

from django.conf import settings
from django.db import models

from core.models import TimestampedModel


class Upload(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    object_key = models.CharField(
        max_length=500,
        unique=True,
    )

    mime_type = models.CharField(
        max_length=100,
        blank=True,
    )

    size = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text="File size in bytes",
    )

    title = models.CharField(
        max_length=500,
        blank=True,
    ) 

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploads",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return "Upload " + str(self.id)
