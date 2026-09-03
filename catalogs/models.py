import uuid
import secrets
import string

from django.db import models
from django.db.models import Q
from django.core.validators import FileExtensionValidator
from django.core.validators import MinValueValidator
from django.core.validators import RegexValidator
from django.utils.text import slugify

from core.models import AutoSlugModel, TimestampedModel


PUBLIC_ID_ALPHABET = string.ascii_lowercase + string.digits


def generate_catalog_public_id():
    return "".join(secrets.choice(PUBLIC_ID_ALPHABET) for _ in range(8))


class CatalogCategory(AutoSlugModel, TimestampedModel):
    class TypeChoices(models.TextChoices):
        PRODUCT = "product", "Product"
        SPECIALTY = "specialty", "Specialty"
        PROPERTY = "property", "Property"
        SERVICE = "service", "Service"
        MENU = "menu", "Menu"
        PACKAGE = "package", "Package"
        OTHER = "other", "Other"

    name = models.CharField(
        max_length=150,
        db_index=True,
    )
    label = models.CharField(
        max_length=150,
        blank=True,
        help_text="Optional public-facing label. Falls back to name when blank.",
    )
    type = models.CharField(
        max_length=30,
        choices=TypeChoices.choices,
        default=TypeChoices.PRODUCT,
        db_index=True,
    )

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    aliases = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated alternate names/search terms.",
    )
    image = models.ImageField(
            upload_to="categories/catalogs/",
            null=True,
            blank=True,
            validators=[
                FileExtensionValidator(
                    ["jpg", "jpeg", "png", "webp"]
                )
            ],
        )


    sort_order = models.PositiveIntegerField(
        default=0,
        db_index=True,
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )
    is_featured = models.BooleanField(
        default=False,
        db_index=True,
    )
    is_display = models.BooleanField(
        default=True,
        db_index=True,
    )

    AUTO_SLUG_FIELD = "label"

    class Meta:
        db_table = "catalog_categories"
        ordering = ("sort_order", "name")

        constraints = [
            models.UniqueConstraint(
                fields=("type", "slug"),
                name="catalog_category_unique_type_slug",
            ),

            models.UniqueConstraint(
                fields=("type", "name"),
                name="catalog_category_unique_type_name",
            ),

            models.CheckConstraint(
                condition=~Q(parent=models.F("id")),
                name="catalog_category_parent_not_self",
            ),
        ]

        indexes = [
            models.Index(
                fields=("type", "is_active", "sort_order"),
                name="catalog_cat_type_active_idx",
            ),
            models.Index(
                fields=("type", "parent", "is_active"),
                name="catalog_cat_parent_idx",
            ),
            models.Index(
                fields=("type", "is_featured", "sort_order"),
                name="catalog_cat_featured_idx",
            ),
        ]

    def __str__(self):
        return self.label or self.name

    @property
    def display_name(self):
        return self.label or self.name

    def clean(self):
        super().clean()

        if self.parent:
            if self.parent_id == self.id:
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    "parent": "A category cannot be its own parent."
                })

            if self.parent.type != self.type:
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    "parent": "Parent category must have the same type."
                })


class Catalog(TimestampedModel):
    class TypeChoices(models.TextChoices):
        PRODUCT = "product", "Product"
        SERVICE = "service", "Service"
        DOCTOR = "doctor", "Doctor"
        PROPERTY = "property", "Property"
        MENU = "menu", "Menu"
        PACKAGE = "package", "Package"
        OTHER = "other", "Other"

    class PriceTypeChoices(models.TextChoices):
        FIXED = "fixed", "Fixed"
        STARTS_FROM = "starts_from", "Starts From"
        RANGE = "range", "Range"
        ASK = "ask", "Ask for Price"
        FREE = "free", "Free"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    public_id = models.CharField(
        max_length=8,
        unique=True,
        editable=False,
        default=generate_catalog_public_id,
        validators=[
            RegexValidator(
                regex=r"^[a-z0-9]{8}$",
                message="Public ID must contain exactly 8 alphanumeric characters.",
            )
        ],
    )
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.PROTECT,
        related_name="catalog_items",
        db_index=True,
    )
    type = models.CharField(
        max_length=20,
        choices=TypeChoices.choices,
        default=TypeChoices.PRODUCT,
        db_index=True,
    )
    name = models.CharField(
        max_length=200,
        db_index=True,
    )
    slug = models.SlugField(
        max_length=200,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
    )

    description = models.TextField(
        blank=True,
    )
    categories = models.ManyToManyField(
        "catalogs.CatalogCategory",
        blank=True,
        related_name="catalog_items",
    )
    price_type = models.CharField(
        max_length=20,
        choices=PriceTypeChoices.choices,
        default=PriceTypeChoices.FIXED,
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    max_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Used only when price_type is range.",
    )

    original_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Optional MRP/original price for display.",
    )

    variants = models.JSONField(
        default=list,
        blank=True,
        help_text="Display-only variant options such as size, color, weight or volume.",
    )

    specifications = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured type-specific data controlled by the application.",
    )

    custom_fields = models.JSONField(
        default=list,
        blank=True,
        help_text="User-defined title/value information for display.",
    )

    is_featured = models.BooleanField(
        default=False,
        db_index=True,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
        db_index=True,
    )

    class Meta:
        ordering = ("sort_order", "-created_at")

        indexes = [
            models.Index(
                fields=("business", "type", "is_active"),
                name="catalog_business_type_idx",
            ),
            models.Index(
                fields=("business", "is_featured", "is_active"),
                name="catalog_featured_idx",
            ),
            models.Index(
                fields=("type", "is_active"),
                name="catalog_type_active_idx",
            ),
        ]

    def __str__(self):
        return self.name

    def build_slug(self):
        suffix = f"-{self.public_id}"
        max_base_length = self._meta.get_field("slug").max_length - len(suffix)
        base = (slugify(self.name) or "item")[:max_base_length].rstrip("-")
        return f"{base}{suffix}"

    def save(self, *args, **kwargs):
        expected_suffix = f"-{self.public_id}"
        if not self.slug or not self.slug.endswith(expected_suffix):
            self.slug = self.build_slug()
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"slug"}
        return super().save(*args, **kwargs)


class CatalogImage(TimestampedModel):
    catalog = models.ForeignKey(
        "catalogs.Catalog",
        on_delete=models.CASCADE,
        related_name="images",
    )

    image = models.ImageField(
        upload_to="catalog/items/",
        validators=[
            FileExtensionValidator(
                ["jpg", "jpeg", "png", "webp"]
            )
        ],
    )

    alt_text = models.CharField(
        max_length=200,
        blank=True,
    )

    is_primary = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Primary/default image shown for the catalog item.",
    )

    sort_order = models.PositiveIntegerField(
        default=0,
        db_index=True,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    class Meta:
        db_table = "catalogimages"
        ordering = ("sort_order", "created_at")

        constraints = [
            models.UniqueConstraint(
                fields=("catalog",),
                condition=Q(is_primary=True),
                name="unique_primary_catalog_image",
            )
        ]


        indexes = [
            models.Index(
                fields=("catalog", "is_active", "sort_order"),
                name="catalog_img_active_idx",
            ),
        ]

    def __str__(self):
        return f"{self.catalog.name} - Image"

    def save(self, *args, **kwargs):
        if self.image and not getattr(self.image, "_committed", True):
            from core.image_service import compress_image

            self.image = compress_image(self.image, max_width=1024, quality=80)

            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"image"}

        return super().save(*args, **kwargs)
