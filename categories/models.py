from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

from core.models import AutoSlugModel, TimestampedModel


class BaseCategory(AutoSlugModel, TimestampedModel):
    name = models.CharField(max_length=200)
    label = models.CharField(
        max_length=200,
        blank=True,
        help_text="Plural form of the name.",
    )
    display_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional public label; name is used when blank.",
    )
    aliases = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated search terms.",
    )
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    slug_source_field = "label"

    class Meta:
        abstract = True

    @property
    def public_name(self):
        return self.display_name or self.name

    def get_slug_source(self):
        return self.label or self.name

    def _normalize_text(self):
        self.name = (self.name or "").strip()
        self.label = (self.label or "").strip()
        self.display_name = (self.display_name or "").strip()
        self.aliases = (self.aliases or "").strip()

    def clean(self):
        super().clean()
        self._normalize_text()

        if not self.name:
            raise ValidationError({
                "name": "Category name cannot be empty."
            })

    def save(self, *args, **kwargs):
        self._normalize_text()

        if not self.name:
            raise ValidationError({
                "name": "Category name cannot be empty."
            })

        # image = getattr(self, "image", None)
        # if image and not getattr(image, "_committed", True):
        #     from core.image_service import compress_image

        #     self.image = compress_image(image, quality=100)
        #     update_fields = kwargs.get("update_fields")
        #     if update_fields is not None:
        #         kwargs["update_fields"] = set(update_fields) | {"image"}

        return super().save(*args, **kwargs)

    def __str__(self):
        return self.public_name


class BusinessCategory(BaseCategory):
    image = models.ImageField(
        upload_to="categories/businesses/",
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(
                ["jpg", "jpeg", "png", "webp"]
            )
        ],
    )

    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "business_categories"
        ordering = ("sort_order", "name")
        verbose_name_plural = "Business Categories"

        indexes = [
            models.Index(
                fields=["is_active", "sort_order"]
            ),
        ]


class ProductCategory(BaseCategory):
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    image = models.ImageField(
        upload_to="categories/products/",
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(
                ["jpg", "jpeg", "png", "webp"]
            )
        ],
    )

    class Meta:
        db_table = "product_categories"
        verbose_name_plural = "Product Categories"