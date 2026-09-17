import uuid
import secrets
import string

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from core.models import TimestampedModel

PUBLIC_ID_ALPHABET = string.ascii_lowercase + string.digits


def generate_catalog_public_id():
    return "".join(
        secrets.choice(PUBLIC_ID_ALPHABET)
        for _ in range(8)
    )


class Catalog(TimestampedModel):
    class CatalogType(models.TextChoices):
        MENU = "menu", "Menu Item"
        PROPERTY = "property", "Property"
        PRICING = "pricing", "Pricing"
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.CharField(
        max_length=8,
        unique=True,
        default=generate_catalog_public_id,
        editable=False,
    )
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="catalogs",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=True)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=CatalogType.choices, default=CatalogType.MENU)
    images = models.ManyToManyField(
        "uploads.Upload",
        blank=True,
        related_name="catalogs",
    )
    custom_fields = models.JSONField(null=True, blank=True)

    is_active = models.BooleanField(db_index=True, default=True)
    is_available = models.BooleanField(db_index=True, default=True)

    class Meta:
        db_table = "catalogs"
        verbose_name = "Catalog"
        verbose_name_plural = "Catalogs"
        ordering = (
            "name",
            "-created_at",
        )
        indexes = [
            models.Index(
                fields=("business", "type", "is_active"),
                name="catalog_business_type_idx",
            ),
            models.Index(
                fields=("business", "is_available", "is_active"),
                name="catalog_availability_idx",
            ),
            models.Index(
                fields=("type", "is_active"),
                name="catalog_type_active_idx",
            ),
        ]

    def clean(self):
        super().clean()

        self.name = (self.name or "").strip()
        self.description = (self.description or "").strip()

        if not self.name:
            raise ValidationError({
                "name": "Catalog name cannot be empty."
            })

    def build_slug(self):
        suffix = f"-{self.public_id}"
        max_base_length = self._meta.get_field("slug").max_length - len(suffix)
        base = (slugify(self.name) or "catalog")[:max_base_length].rstrip("-")

        return f"{base}{suffix}"

    def save(self, *args, **kwargs):
        self.name = (self.name or "").strip()
        self.description = (self.description or "").strip()

        if not self.name:
            raise ValidationError({
                "name": "Catalog name cannot be empty."
            })

        self.slug = self.build_slug()

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"slug"}

        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name
