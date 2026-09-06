import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import TimestampedModel


class OfferQuerySet(models.QuerySet):
    def active(self):
        now = timezone.now()

        return self.filter(
            is_active=True,
        ).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
            Q(expires_at__isnull=True) | Q(expires_at__gte=now),
        )


class Offer(TimestampedModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="offers",
    )

    title = models.CharField(
        max_length=150,
    )

    description = models.TextField(
        blank=True,
    )

    image = models.ImageField(
        upload_to="offers/",
        max_length=500,
        null=True,
        blank=True,
    )

    starts_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
        db_index=True,
    )
    terms = models.JSONField(
        blank=True,
        default=list
    )

    objects = OfferQuerySet.as_manager()

    class Meta:
        db_table = "offers"
        ordering = (
            "sort_order",
            "-created_at",
        )
        indexes = [
            models.Index(
                fields=["business", "is_active"],
                name="offer_business_active_idx",
            ),
            models.Index(
                fields=["business", "sort_order"],
                name="offer_business_sort_idx",
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()

        if (
            self.starts_at
            and self.expires_at
            and self.expires_at <= self.starts_at
        ):
            raise ValidationError({
                "expires_at": "Expiry time must be after the start time."
            })

    @property
    def status(self):
        if not self.is_active:
            return "disabled"

        now = timezone.now()

        if self.starts_at and self.starts_at > now:
            return "scheduled"

        if self.expires_at and self.expires_at < now:
            return "expired"

        return "active"

    @property
    def is_currently_active(self):
        return self.status == "active"
