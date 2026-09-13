from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from core.models import AutoSlugModel, TimestampedModel
from products.product import Product, ProductImage


class ProductCategory(AutoSlugModel, TimestampedModel):
    name = models.CharField(max_length=200, help_text="Singular category name, e.g. Shirt, Saree, Mobile Phone.",)
    label = models.CharField(max_length=200, blank=True, help_text="Plural/public category label, e.g. Shirts, Sarees.",)
    display_name = models.CharField(max_length=100, blank=True, help_text="Optional shorter public-facing name.")
    aliases = models.CharField(max_length=500, blank=True, help_text="Comma-separated alternative search terms.",)

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
                allowed_extensions=[
                    "jpg",
                    "jpeg",
                    "png",
                    "webp",
                ]
            )
        ],
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    is_featured = models.BooleanField(
        default=False,
        db_index=True,
    )

    sort_order = models.PositiveIntegerField(
        default=100,
    )

    slug_source_field = "label"

    class Meta:
        db_table = "product_categories"

        verbose_name = "Product Category"
        verbose_name_plural = "Product Categories"

        ordering = (
            "sort_order",
            "name",
        )

        indexes = [
            models.Index(
                fields=["parent", "is_active", "sort_order"],
                name="prodcat_parent_active_idx",
            ),
            models.Index(
                fields=["is_featured", "is_active", "sort_order"],
                name="prodcat_featured_idx",
            ),
        ]

        constraints = [
            # Prevent duplicate names under the same parent.
            models.UniqueConstraint(
                Lower("name"),
                "parent",
                name="unique_product_category_parent_name",
            ),

            # Prevent duplicate top-level category names.
            models.UniqueConstraint(
                Lower("name"),
                condition=Q(parent__isnull=True),
                name="unique_root_product_category_name",
            ),
        ]

    @property
    def public_name(self):
        return self.display_name or self.name

    @property
    def is_root(self):
        return self.parent_id is None

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

        if self.parent_id and self.pk and self.parent_id == self.pk:
            raise ValidationError({
                "parent": "A category cannot be its own parent."
            })

        # Prevent circular category trees:
        #
        # Clothing
        # └── Men's Clothing
        #     └── Clothing  <-- invalid
        #
        if self.parent_id:
            ancestor = self.parent

            while ancestor:
                if self.pk and ancestor.pk == self.pk:
                    raise ValidationError({
                        "parent": (
                            "Circular category relationships are not allowed."
                        )
                    })

                ancestor = ancestor.parent

    def save(self, *args, **kwargs):
        self._normalize_text()

        if not self.name:
            raise ValidationError({
                "name": "Category name cannot be empty."
            })

        return super().save(*args, **kwargs)

    def __str__(self):
        if self.parent:
            return f"{self.parent.public_name} → {self.public_name}"

        return self.public_name
