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


handle_validator = RegexValidator(
    regex=r"^[a-z0-9][a-z0-9_-]{2,49}$",
    message=(
        "Handle must be 3-50 characters and contain only "
        "lowercase letters, numbers, underscores, or hyphens."
    ),
)


class Business(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending review"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="businesses",
    )

    name = models.CharField(max_length=200)

    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
    )

    handle = models.CharField(
        max_length=50,
        validators=[handle_validator],
        unique=True,
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

    categories = models.ManyToManyField(
        "categories.BusinessCategory",
        through="BusinessCategoryAssignment",
        related_name="businesses",
        blank=True,
    )

    # Location
    address = models.CharField(max_length=300)

    landmark = models.CharField(
        max_length=200,
        blank=True,
        default="",
    )

    locality = models.CharField(
        max_length=200,
        blank=True,
        default="",
    )
    city = models.ForeignKey(
        "locations.City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="businesses",
    )

    postal_code = models.CharField(
        max_length=6,
        blank=True,
        default="",
        db_index=True,
    )

    location = gis_models.PointField(
        geography=True,
        srid=4326,
        null=True,
        blank=True,
        spatial_index=True,
        help_text="Exact business location (longitude, latitude).",
    )

    # Contact
    phone = models.CharField(
        max_length=16,
        blank=True,
        default="",
        validators=[phone_validator],
    )

    whatsapp = models.CharField(
        max_length=16,
        blank=True,
        default="",
        validators=[phone_validator],
    )

    email = models.EmailField(
        blank=True,
        default="",
    )

    website = models.URLField(
        blank=True,
        default="",
    )

    # Media
    thumbnail = models.ImageField(
        upload_to="businesses/thumbnails/",
        blank=True,
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png", "webp"])
        ],
    )

    # Publishing
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    is_active = models.BooleanField(
        default=False,
        db_index=True,
    )

    is_verified = models.BooleanField(
        default=False,
        db_index=True,
    )

    display_full_address = models.BooleanField(
        default=True,
        help_text=(
            "Show street address, landmark, postal code, "
            "and exact location publicly."
        ),
    )

    display_business_hours = models.BooleanField(
        default=True,
        help_text=(
            "Show current open, closing soon, "
            "or closed status publicly."
        ),
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    is_paid = models.BooleanField(
        default=False,
        blank=True,
    )
    payment_date = models.DateTimeField(
        null=True,
        blank=True,
    )
    paid_until = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "businesses"
        ordering = ("name", "id")

        constraints = [
            models.UniqueConstraint(
                Lower("handle"),
                name="business_handle_ci_unique",
            ),
        ]

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

        if self.handle:
            self.handle = self.handle.strip().lower()

        from businesses.services import normalize_business

        normalize_business(self)

    def save(self, *args, **kwargs):
        if self.handle:
            self.handle = self.handle.strip().lower()

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


class BusinessHoliday(TimestampedModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="business_holidays",
    )

    start_date = models.DateField()
    end_date = models.DateField()

    reason = models.CharField(
        max_length=200,
        blank=True,
        default="",
    )

    class Meta:
        db_table = "business_holidays"

        ordering = (
            "start_date",
            "id",
        )

        indexes = [
            models.Index(
                fields=(
                    "business",
                    "start_date",
                    "end_date",
                ),
                name="business_holiday_dates_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    end_date__gte=models.F("start_date")
                ),
                name="business_holiday_valid_dates",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            raise ValidationError(
                {
                    "end_date":
                        "End date must be on or after start date."
                }
            )

    def __str__(self):
        return (
            f"{self.business}: "
            f"{self.start_date} to {self.end_date}"
        )


class BusinessGalleryImage(TimestampedModel):
    """An ordered image displayed in the business gallery."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="gallery_images",
    )

    image = models.ImageField(
        upload_to="businesses/gallery/",
        max_length=500,
        validators=[
            FileExtensionValidator(
                ["jpg", "jpeg", "png", "webp"]
            )
        ],
    )

    sort_order = models.PositiveSmallIntegerField(
        default=0,
    )

    class Meta:
        db_table = "business_gallery_images"

        ordering = (
            "sort_order",
            "created_at",
            "id",
        )

        indexes = [
            models.Index(
                fields=("business", "sort_order"),
                name="business_gallery_order_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if (
            self.image
            and not getattr(
                self.image,
                "_committed",
                True,
            )
        ):
            from core.image_service import compress_image

            self.image = compress_image(self.image, max_width=1024)

            update_fields = kwargs.get("update_fields")

            if update_fields is not None:
                kwargs["update_fields"] = (
                    set(update_fields) | {"image"}
                )

        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.business}: {self.image.name}"


class BusinessGalleryUpload(TimestampedModel):
    class Kind(models.TextChoices):
        GALLERY = "gallery", "Business gallery"
        THUMBNAIL = "thumbnail", "Business thumbnail"
        OFFER = "offer", "Offer image"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending upload"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="gallery_uploads",
    )
    object_key = models.CharField(max_length=500, unique=True)
    content_type = models.CharField(max_length=32)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.GALLERY)
    target_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    error = models.CharField(max_length=500, blank=True, default="")
    gallery_image = models.OneToOneField(
        BusinessGalleryImage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="upload",
    )

    class Meta:
        db_table = "business_gallery_uploads"

    def __str__(self):
        return f"{self.business}: {self.status} ({self.id})"
