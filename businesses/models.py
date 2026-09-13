import uuid

from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
from django.db.models.functions import Lower

from core.models import SEOModel, TimestampedModel

from businesses.validators import (
    phone_validator,
    validate_alternate_numbers,
    validate_business_days,
    validate_established_year,
    validate_social_urls,
)


class Business(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending review"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"

    #Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="businesses")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    categories = models.ManyToManyField(
        "categories.BusinessCategory",
        through="BusinessCategoryAssignment",
        related_name="businesses",
        blank=True,
    )

    # Location
    address = models.CharField(max_length=300)
    landmark = models.CharField(max_length=200, blank=True,default="")
    locality = models.CharField(max_length=200, blank=True, default="")
    city = models.ForeignKey(
        "locations.City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="businesses",
    )
    postal_code = models.CharField(max_length=6, blank=True, default="", db_index=True)
    location = gis_models.PointField(
        geography=True,
        srid=4326,
        null=True,
        blank=True,
        spatial_index=True,
        help_text="Exact business location (longitude, latitude).",
    )

    # Contact
    phone = models.CharField(max_length=16, blank=True, default="", validators=[phone_validator])
    whatsapp = models.CharField(max_length=16, blank=True, default="", validators=[phone_validator])
    email = models.EmailField(blank=True, default="")
    website = models.URLField(blank=True, default="")

    # Media
    cover_image  = models.ForeignKey(
        "uploads.Upload",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_cover_image",
    )
    gallery = models.ManyToManyField(
        "uploads.Upload",
        related_name="businesses",
        blank=True,
    )

    # Publishing
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    is_active = models.BooleanField(default=False, db_index=True)
    is_verified = models.BooleanField(default=False, db_index=True)

    #Display Options
    display_full_address = models.BooleanField(
        default=True,
        help_text=(  "Show street address, landmark, postal code,and exact location publicly.")
    )
    display_business_hours = models.BooleanField(
        default=True,
        help_text=("Show current open, closing soon, or closed status publicly.")
    )

    #Payment
    is_paid = models.BooleanField(default=False, blank=True)
    payment_date = models.DateTimeField(null=True, blank=True)
    paid_until = models.DateTimeField(null=True, blank=True)

    #misc
    sections = models.JSONField(
        default=list,
        blank=True,
    )
    established_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[validate_established_year],
    )

    offerings = models.JSONField(
        default=list,
        blank=True,
    )

    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "businesses"
        ordering = ("name", "id")

        indexes = [
            models.Index(
                fields=("locality", "status", "is_active"),
                name="business_locality_vis_idx",
            ),
            models.Index(
                fields=("status", "is_active", "published_at"),
                name="business_publish_idx",
            ),
            models.Index(
                fields=("owner", "status"),
                name="business_owner_status_idx",
            ),
        ]

    def clean(self):
        super().clean()

        from businesses.services import normalize_business

        normalize_business(self)

    def save(self, *args, **kwargs):

        from businesses.services import save_business

        return save_business(
            self,
            super().save,
            args,
            kwargs,
        )

    @property
    def latitude(self):
        return self.location.y if self.location else None

    @property
    def longitude(self):
        
        return self.location.x if self.location else None

    def __str__(self):
        return self.name


class BusinessCategoryAssignment(models.Model):
    """An ordered category assigned to a business."""

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="category_assignments",
    )

    category = models.ForeignKey(
        "categories.BusinessCategory",
        on_delete=models.CASCADE,
        related_name="business_assignments",
    )

    sort_order = models.PositiveSmallIntegerField(
        default=0,
    )

    class Meta:
        db_table = "business_category_assignments"
        ordering = ("sort_order", "id")

        constraints = [
            models.UniqueConstraint(
                fields=("business", "category"),
                name="business_category_assignment_unique",
            ),
            models.UniqueConstraint(
                fields=("business", "sort_order"),
                name="business_category_sort_order_unique",
            ),
        ]

    def __str__(self):
        return (
            f"{self.business}: "
            f"{self.category} ({self.sort_order})"
        )


class BusinessProfile(TimestampedModel, SEOModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    business = models.OneToOneField(
        Business,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    description = models.TextField(
        blank=True,
        default="",
    )

    social_urls = models.JSONField(
        default=dict,
        blank=True,
        validators=[validate_social_urls],
    )

    alternate_numbers = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_alternate_numbers],
    )

    services = models.JSONField(
        default=list,
        blank=True,
    )

    class Meta:
        db_table = "business_profiles"
        verbose_name_plural = "Business Profiles"

    def clean(self):
        super().clean()

        from businesses.services import normalize_business_profile

        normalize_business_profile(self)

    def save(self, *args, **kwargs):
        from businesses.services import normalize_business_profile

        normalize_business_profile(self)

        return super().save(*args, **kwargs)

    def __str__(self):
        return self.business.name


class BusinessHour(TimestampedModel):
    """One opening-time slot shared by one or more weekdays."""

    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="business_hours",
    )

    days = ArrayField(
        models.PositiveSmallIntegerField(
            choices=Weekday.choices,
        ),
        size=7,
        validators=[validate_business_days],
        help_text="Weekdays sharing this slot (Monday=0, Sunday=6).",
    )

    opens_at = models.TimeField()
    closes_at = models.TimeField()

    class Meta:
        db_table = "business_hours"

        ordering = (
            "business_id",
            "opens_at",
            "id",
        )

        indexes = [
            models.Index(
                fields=("business", "opens_at"),
                name="business_hours_open_idx",
            ),
            GinIndex(
                fields=("days",),
                name="business_hours_days_gin",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    closes_at__gt=models.F("opens_at")
                ),
                name="business_hour_closes_after_open",
            ),
            models.UniqueConstraint(
                fields=(
                    "business",
                    "days",
                    "opens_at",
                    "closes_at",
                ),
                name="business_hour_slot_unique",
            ),
        ]

    def clean(self):
        super().clean()

        validate_business_days(self.days)
        self.days = sorted(set(self.days))

        if (
            self.opens_at is not None
            and self.closes_at is not None
            and self.closes_at <= self.opens_at
        ):
            raise ValidationError(
                {
                    "closes_at":
                        "Closing time must be later than opening time."
                }
            )

        if (
            self.business_id
            and self.opens_at is not None
            and self.closes_at is not None
            and self.closes_at > self.opens_at
        ):
            overlaps = (
                type(self)
                .objects
                .filter(
                    business_id=self.business_id,
                    days__overlap=self.days,
                    opens_at__lt=self.closes_at,
                    closes_at__gt=self.opens_at,
                )
                .exclude(pk=self.pk)
            )

            if overlaps.exists():
                raise ValidationError(
                    "This slot overlaps existing business hours "
                    "on one or more selected days."
                )

    def save(self, *args, **kwargs):
        validate_business_days(self.days)
        self.days = sorted(set(self.days))

        update_fields = kwargs.get("update_fields")

        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"days"}

        return super().save(*args, **kwargs)

    @property
    def day_names(self):
        labels = dict(self.Weekday.choices)

        return [
            labels[day]
            for day in self.days
        ]

    def __str__(self):
        days = ", ".join(self.day_names)

        return (
            f"{self.business}: {days} "
            f"{self.opens_at:%H:%M}-"
            f"{self.closes_at:%H:%M}"
        )
